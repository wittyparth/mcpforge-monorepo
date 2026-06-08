"""SSEManager with Redis pub/sub for streaming build progress events.

Provides a fan-out mechanism where build progress events published
via Redis pub/sub are delivered to local asyncio.Queue instances for
SSE streaming to the frontend.

Architecture::

    Service code                  SSEManager                  Redis
    ───────────                  ──────────                  ─────
    publish(server_id, data)  →  pub/sub publish             channel
                                                              ↓
    subscribe(server_id)      →  pub/sub subscribe  ←────────┘
         │                        │
         ▼                        ▼
    asyncio.Queue ── listener fans out ── Redis message loop
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _decode(value: bytes | str) -> str:
    """Decode bytes to str, passing through str values unchanged."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


class SSEManager:
    """Manages Redis pub/sub fan-out for SSE events.

    Each server build publishes events to a Redis channel named
    ``sse:{server_id}``. The manager subscribes to all active channels
    in a single background listener task and fans out incoming messages
    to the local ``asyncio.Queue`` instances returned by ``subscribe()``.

    Usage::

        queue = await sse_manager.subscribe("server-abc")
        try:
            while True:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {data}\\n\\n"
        except asyncio.TimeoutError:
            pass
        finally:
            await sse_manager.unsubscribe("server-abc", queue)
    """

    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[str]]] = {}
        self._pubsub: Any = None  # redis.asyncio.client.PubSub (created lazily)
        self._redis_conn: Redis | None = None  # kept alive for the pubsub listener
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def _ensure_pubsub(self) -> Any:
        """Get or create the shared Redis pubsub connection.

        Creates the connection directly from the URL rather than from a
        shared pool.  A shared pool's connections are pinned to the event
        loop that created them, which breaks when ``asyncio.run()`` is
        called inside a Celery worker thread (different event loop).
        """
        if self._pubsub is None:
            self._redis_conn = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            self._pubsub = self._redis_conn.pubsub()
        return self._pubsub

    async def publish(self, server_id: str, event_dict: dict[str, Any]) -> None:
        """Publish an event to the Redis channel for a server build.

        Creates a dedicated Redis client from the URL rather than from a
        shared pool.  A shared pool's connections are pinned to the event
        loop that created them, which breaks when ``asyncio.run()`` is
        called inside a Celery worker thread (different event loop).

        Args:
            server_id: The server identifier.
            event_dict: The event data (will be JSON-encoded).
        """
        r = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        try:
            channel = f"sse:{server_id}"
            await r.publish(channel, json.dumps(event_dict))
        finally:
            await r.close()

    async def subscribe(self, server_id: str) -> asyncio.Queue[str]:
        """Subscribe to build progress events for a server.

        Registers a local ``asyncio.Queue`` and ensures the background
        listener task is running. If this is the first subscriber for
        this server_id, also subscribes to the Redis channel.

        Args:
            server_id: The server identifier.

        Returns:
            An ``asyncio.Queue`` that receives JSON-encoded event strings.
        """
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            is_new = server_id not in self._queues or not self._queues[server_id]
            if server_id not in self._queues:
                self._queues[server_id] = set()
            self._queues[server_id].add(queue)

            if is_new:
                pubsub = await self._ensure_pubsub()
                await pubsub.subscribe(f"sse:{server_id}")

            if self._task is None:
                self._task = asyncio.create_task(self._listener())
        return queue

    async def unsubscribe(self, server_id: str, queue: asyncio.Queue[str]) -> None:
        """Remove a subscriber queue for a server build.

        If no more subscribers remain for this server_id, also
        unsubscribes from the Redis channel.

        Args:
            server_id: The server identifier.
            queue: The queue to remove.
        """
        async with self._lock:
            if server_id not in self._queues:
                return
            self._queues[server_id].discard(queue)
            if not self._queues[server_id]:
                del self._queues[server_id]
                pubsub = await self._ensure_pubsub()
                await pubsub.unsubscribe(f"sse:{server_id}")

    async def shutdown(self) -> None:
        """Cancel the listener and clean up Redis resources.

        Called during application shutdown.
        """
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        if self._redis_conn is not None:
            await self._redis_conn.close()
            self._redis_conn = None
            self._pubsub = None

    async def _listener(self) -> None:
        """Background task: listen on Redis pub/sub and fan out to local queues.

        Subscribes to all currently tracked channels and forwards
        incoming messages to the corresponding local ``asyncio.Queue``
        instances. Automatically re-subscribes when new channels are
        added via ``subscribe()`` (``redis.asyncio.PubSub`` handles
        dynamic subscription changes).
        """
        pubsub = await self._ensure_pubsub()
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                channel = _decode(message["channel"])
                data = _decode(message["data"])

                server_id = channel.split(":", 1)[1] if ":" in channel else channel

                async with self._lock:
                    queues = self._queues.get(server_id, set()).copy()

                for queue in queues:
                    await queue.put(data)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("SSE listener crashed, will be restarted on next subscribe")
            self._task = None
            raise
        finally:
            self._task = None


# Singleton instance for use across the application.
sse_manager = SSEManager()
