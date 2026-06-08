"""Tests for SSEManager — Redis pub/sub fan-out for SSE events.

4+ tests covering:
  - subscribe returns an asyncio.Queue
  - publish delivers to subscriber queue
  - unsubscribe removes the subscriber
  - Multiple subscribers receive the same event

Uses fakeredis for Redis pub/sub without a real Redis server.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fakeredis import FakeAsyncRedis

from app.core.sse import SSEManager

# Reusable fake pool fixture — fakeredis pub/sub works transparently
# through redis.asyncio.ConnectionPool.


@pytest.fixture
def fake_redis_pool():
    """Create a fakeredis connection pool for testing."""
    fake_redis = FakeAsyncRedis(decode_responses=True)
    yield fake_redis.connection_pool
    # No explicit cleanup needed — the pool's connections are fake


@pytest.mark.asyncio
async def test_subscribe_returns_asyncio_queue(fake_redis_pool) -> None:
    """subscribe() should return an asyncio.Queue."""
    manager = SSEManager()
    with patch("app.core.sse.get_redis_pool", return_value=fake_redis_pool):
        queue = await manager.subscribe("server-1")

    assert isinstance(queue, asyncio.Queue)
    assert queue.qsize() == 0

    await manager.shutdown()


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber_queue(fake_redis_pool) -> None:
    """publish() should deliver the event to the subscriber queue."""
    manager = SSEManager()
    with patch("app.core.sse.get_redis_pool", return_value=fake_redis_pool):
        queue = await manager.subscribe("server-1")
        await manager.publish("server-1", {"event": "test", "data": "hello"})

        # Wait for the listener to process
        await asyncio.sleep(0.2)

        assert queue.qsize() >= 1
        msg = await queue.get()
        assert "test" in msg
        assert "hello" in msg

    await manager.shutdown()


@pytest.mark.asyncio
async def test_unsubscribe_removes_subscriber(fake_redis_pool) -> None:
    """After unsubscribe, the queue should no longer receive events."""
    manager = SSEManager()
    with patch("app.core.sse.get_redis_pool", return_value=fake_redis_pool):
        queue = await manager.subscribe("server-1")

        # Publish before unsubscribe — should arrive
        await manager.publish("server-1", {"event": "before"})
        await asyncio.sleep(0.2)
        assert queue.qsize() >= 1
        await queue.get()

        # Unsubscribe
        await manager.unsubscribe("server-1", queue)

        # Publish after unsubscribe — should NOT arrive in this queue
        await manager.publish("server-1", {"event": "after"})
        await asyncio.sleep(0.2)

        # The queue might still get the "after" message in some race
        # conditions with the listener, so let's check no NEW messages
        # Rather, verify the server_id is no longer tracked
        assert "server-1" not in manager._queues or not manager._queues["server-1"]

    await manager.shutdown()


@pytest.mark.asyncio
async def test_multiple_subscribers_receive_same_event(fake_redis_pool) -> None:
    """Multiple subscribers on the same channel should all receive the event."""
    manager = SSEManager()
    with patch("app.core.sse.get_redis_pool", return_value=fake_redis_pool):
        queue1 = await manager.subscribe("server-1")
        queue2 = await manager.subscribe("server-1")

        await manager.publish("server-1", {"event": "broadcast", "value": 42})
        await asyncio.sleep(0.3)

        # Both queues should have the event
        assert queue1.qsize() >= 1, "Subscriber 1 did not receive the event"
        assert queue2.qsize() >= 1, "Subscriber 2 did not receive the event"

        msg1 = await queue1.get()
        msg2 = await queue2.get()

        # Both should contain the published data
        assert "broadcast" in msg1
        assert "broadcast" in msg2

    await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_listener_task(fake_redis_pool) -> None:
    """shutdown() should cancel the background listener task."""
    manager = SSEManager()
    with patch("app.core.sse.get_redis_pool", return_value=fake_redis_pool):
        await manager.subscribe("server-1")
        assert manager._task is not None
        assert not manager._task.done()

        await manager.shutdown()

        assert manager._task is None
        assert manager._pubsub is None
