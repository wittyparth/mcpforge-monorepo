"""Tests for SSEManager — Redis pub/sub fan-out for SSE events.

The manager now uses ``Redis.from_url(settings.REDIS_URL)`` directly
rather than a shared pool, so we monkey-patch ``Redis.from_url`` with
a ``FakeAsyncRedis`` instance for hermetic tests.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from fakeredis import FakeAsyncRedis
from redis.asyncio import Redis

from app.core.sse import SSEManager


def _patch_redis(fake: FakeAsyncRedis) -> Any:
    """Return a context manager that replaces ``Redis.from_url`` with a
    callable that returns the supplied fake. Both ``publish`` (short-lived
    client) and ``_ensure_pubsub`` (long-lived pubsub) routes must hit
    the same fake instance, so the patched factory caches the first
    connection it returns.
    """
    cached: list[FakeAsyncRedis] = []

    def factory(*args: Any, **kwargs: Any) -> FakeAsyncRedis:
        if not cached:
            cached.append(fake)
        return cached[0]

    return patch.object(Redis, "from_url", side_effect=factory)


@pytest.fixture
def fake_redis() -> FakeAsyncRedis:
    """A fresh FakeAsyncRedis instance per test for isolation."""
    return FakeAsyncRedis(decode_responses=True)


@pytest.mark.asyncio
async def test_subscribe_returns_asyncio_queue(fake_redis: FakeAsyncRedis) -> None:
    """``subscribe()`` returns a fresh ``asyncio.Queue`` for the channel."""
    manager = SSEManager()
    with _patch_redis(fake_redis):
        queue = await manager.subscribe("server-1")

    assert isinstance(queue, asyncio.Queue)
    assert queue.qsize() == 0

    await manager.shutdown()


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber_queue(fake_redis: FakeAsyncRedis) -> None:
    """An event published after ``subscribe()`` arrives in the local queue."""
    manager = SSEManager()
    with _patch_redis(fake_redis):
        queue = await manager.subscribe("server-1")
        await manager.publish("server-1", {"event": "test", "data": "hello"})

        # Give the listener time to forward the message
        for _ in range(50):
            if queue.qsize() >= 1:
                break
            await asyncio.sleep(0.01)

        assert queue.qsize() >= 1
        msg = await queue.get()
        assert "test" in msg
        assert "hello" in msg

    await manager.shutdown()


@pytest.mark.asyncio
async def test_unsubscribe_removes_subscriber(fake_redis: FakeAsyncRedis) -> None:
    """After ``unsubscribe()``, the channel is no longer tracked."""
    manager = SSEManager()
    with _patch_redis(fake_redis):
        queue = await manager.subscribe("server-1")
        await manager.unsubscribe("server-1", queue)

        assert "server-1" not in manager._queues

    await manager.shutdown()


@pytest.mark.asyncio
async def test_multiple_subscribers_receive_same_event(fake_redis: FakeAsyncRedis) -> None:
    """Two subscribers on the same channel each get a copy of the event."""
    manager = SSEManager()
    with _patch_redis(fake_redis):
        queue1 = await manager.subscribe("server-1")
        queue2 = await manager.subscribe("server-1")

        await manager.publish("server-1", {"event": "broadcast", "value": 42})

        for _ in range(50):
            if queue1.qsize() >= 1 and queue2.qsize() >= 1:
                break
            await asyncio.sleep(0.01)

        assert queue1.qsize() >= 1, "Subscriber 1 did not receive the event"
        assert queue2.qsize() >= 1, "Subscriber 2 did not receive the event"

        msg1 = await queue1.get()
        msg2 = await queue2.get()
        assert "broadcast" in msg1
        assert "broadcast" in msg2

    await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_listener_task(fake_redis: FakeAsyncRedis) -> None:
    """``shutdown()`` cancels the listener and releases the pubsub handle."""
    manager = SSEManager()
    with _patch_redis(fake_redis):
        await manager.subscribe("server-1")
        assert manager._task is not None
        assert not manager._task.done()

        await manager.shutdown()

        assert manager._task is None
        assert manager._pubsub is None
        assert manager._redis_conn is None
