"""Async Redis client via redis.asyncio.

Provides a lazy-init client and a FastAPI dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: ConnectionPool | None = None


async def get_redis_pool() -> ConnectionPool:
    """Get or create the global Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=10,
            decode_responses=True,
        )
    return _pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency providing an async Redis client.

    Yields a Redis connection from the shared pool.
    """
    pool = await get_redis_pool()
    redis = Redis.from_pool(pool)
    try:
        yield redis
    finally:
        await redis.close()


async def check_redis_health() -> bool:
    """Best-effort Redis connectivity check.

    Returns:
        True if connected, False otherwise (does NOT raise).
    """
    try:
        pool = await get_redis_pool()
        r = Redis.from_pool(pool)
        await r.ping()
        await r.close()
        return True
    except Exception:
        return False


async def shutdown_redis() -> None:
    """Close the global Redis pool on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
