"""Redis-backed account lockout.

After `LOCKOUT_MAX_ATTEMPTS` consecutive failed logins (default 5), the
account is locked for `LOCKOUT_DURATION_MINUTES` minutes (default 15).
Successful logins clear the failure counter.

Keys:
- `lockout:fail:<email>` — INCR'd on each failed login; TTL = window
- `lockout:locked:<email>` — marker indicating the account is currently
  locked; TTL = lockout duration
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_pool

logger = get_logger(__name__)

_KEY_FAIL = "lockout:fail:{key}"
_KEY_LOCKED = "lockout:locked:{key}"


@dataclass(frozen=True, slots=True)
class LockoutStatus:
    """Current lockout status for a user.

    Attributes:
        locked: True if the user is currently locked.
        attempts: Number of consecutive failed attempts (0 if locked).
        retry_after: Seconds until the user can try again (0 if not locked).
    """

    locked: bool
    attempts: int
    retry_after: int


async def _with_redis() -> AsyncIterator[Redis]:
    """Async iterator that yields a Redis client from the shared pool.

    Used as `async for r in _with_redis():` — gives a single-iteration
    scope that closes the client on exit. Works around the lack of
    `async with` for async generators in older typing setups.
    """
    pool = await get_redis_pool()
    redis = Redis.from_pool(pool)
    try:
        yield redis
    finally:
        await redis.close()


async def _key_for_email_or_userid(identifier: str | UUID) -> str:
    """Normalize identifier to a string for use as a Redis key suffix."""
    return str(identifier).lower() if isinstance(identifier, str) else str(identifier)


async def _run_redis(
    method: str | None = None,
    *args: object,
    redis_func: Any = None,
    default_return: Any = None,
) -> Any:
    """Execute a Redis operation, failing OPEN on connection errors.

    The default_return is returned on any Redis exception, ensuring the
    rest of the application is not blocked by a Redis outage.
    """
    try:
        async for r in _with_redis():
            if redis_func is not None:
                return await redis_func(r)
            if method is not None:
                return await getattr(r, method)(*args)
            return default_return
        return default_return
    except Exception as exc:
        logger.warning("redis_operation_failed", method=method or "unknown", error=str(exc))
        return default_return


async def is_locked(identifier: str | UUID) -> bool:
    """Return True if the user is currently locked out."""
    key_id = await _key_for_email_or_userid(identifier)
    async def _check(r):
        return bool(await r.exists(_KEY_LOCKED.format(key=key_id)))
    return await _run_redis(default_return=False, redis_func=_check)


async def get_status(identifier: str | UUID) -> LockoutStatus:
    """Return the current lockout status for a user."""
    key_id = await _key_for_email_or_userid(identifier)

    async def _get(r):
        locked_ttl = await r.ttl(_KEY_LOCKED.format(key=key_id))
        if locked_ttl and locked_ttl > 0:
            return LockoutStatus(locked=True, attempts=0, retry_after=int(locked_ttl))
        fail_raw = await r.get(_KEY_FAIL.format(key=key_id))
        attempts = int(fail_raw) if fail_raw else 0
        return LockoutStatus(locked=False, attempts=attempts, retry_after=0)

    return await _run_redis(redis_func=_get, default_return=LockoutStatus(locked=False, attempts=0, retry_after=0))


async def record_failure(identifier: str | UUID) -> LockoutStatus:
    """Record a failed login attempt; lock the account if the threshold is hit.

    Returns:
        The new lockout status. If `locked=True`, the account is now locked.
    """
    key_id = await _key_for_email_or_userid(identifier)
    fail_key = _KEY_FAIL.format(key=key_id)
    locked_key = _KEY_LOCKED.format(key=key_id)
    max_attempts = settings.LOCKOUT_MAX_ATTEMPTS
    duration = settings.LOCKOUT_DURATION_MINUTES * 60

    async def _record(r):
        count = await r.incr(fail_key)
        await r.expire(fail_key, duration)
        if count >= max_attempts:
            await r.setex(locked_key, duration, b"1")
            await r.delete(fail_key)
            logger.warning(
                "account_locked", identifier=key_id, attempts=count, duration_seconds=duration,
            )
            return LockoutStatus(locked=True, attempts=count, retry_after=duration)
        return LockoutStatus(locked=False, attempts=count, retry_after=0)

    return await _run_redis(redis_func=_record, default_return=LockoutStatus(locked=False, attempts=0, retry_after=0))


async def record_success(identifier: str | UUID) -> None:
    """Clear the failure counter and any active lockout on successful login."""
    key_id = await _key_for_email_or_userid(identifier)

    async def _clear(r):
        await r.delete(_KEY_FAIL.format(key=key_id))
        await r.delete(_KEY_LOCKED.format(key=key_id))

    await _run_redis(redis_func=_clear)

