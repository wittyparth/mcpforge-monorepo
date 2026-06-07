"""Refresh token rotation tracking via Redis.

Each issued refresh token carries a unique `jti` (UUID v4) claim. On use:

1. The token's `jti` is checked against the Redis blacklist.
2. If found (replay), the entire user's token family is revoked — a strong
   signal that the refresh token was stolen.
3. Otherwise, the old `jti` is blacklisted (TTL = refresh token lifetime)
   and a new token is issued with a fresh `jti`.

Keys:
- `rt:used:<jti>` — marker; TTL = JWT_REFRESH_TTL_DAYS
- `rt:family:<user_id>` — set of all jti's issued in this session family;
  used for family-wide revocation on reuse.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_pool

logger = get_logger(__name__)

_KEY_USED = "rt:used:{jti}"
_KEY_FAMILY = "rt:family:{user_id}"
_TTL_SECONDS = settings.JWT_REFRESH_TTL_DAYS * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class RotationResult:
    """Outcome of validating a refresh token's jti.

    Attributes:
        ok: True if the jti is fresh and may be used.
        replay_detected: True if the jti was already used (token theft signal).
    """

    ok: bool
    replay_detected: bool


async def _with_redis() -> AsyncIterator[Redis]:
    pool = await get_redis_pool()
    redis = Redis.from_pool(pool)
    try:
        yield redis
    finally:
        await redis.close()


async def is_jti_used(jti: str) -> bool:
    """Return True if a jti has already been used (and is blacklisted)."""
    async for r in _with_redis():
        return bool(await r.exists(_KEY_USED.format(jti=jti)))
    return False


async def check_and_mark_jti(user_id: UUID, jti: str) -> RotationResult:
    """Atomically check if a jti is fresh, and if so mark it used.

    On replay (jti already used), the user's entire family is revoked
    to invalidate any other outstanding refresh tokens for that user.

    Returns:
        RotationResult.ok=True if the jti is fresh and was just marked used.
        RotationResult.replay_detected=True if the jti was a replay.
    """
    used_key = _KEY_USED.format(jti=jti)
    family_key = _KEY_FAMILY.format(user_id=str(user_id))

    async for r in _with_redis():
        # SETNX semantics: returns True if the key did not exist (fresh jti),
        # None if it did (replay).
        fresh = await r.set(used_key, b"1", ex=_TTL_SECONDS, nx=True)
        if fresh is None or not fresh:
            # Replay detected. Revoke the whole family.
            revoked = await _revoke_family(r, user_id)
            logger.error(
                "refresh_token_replay_detected",
                user_id=str(user_id),
                jti=jti,
                revoked_count=revoked,
            )
            return RotationResult(ok=False, replay_detected=True)

        # Fresh jti — track it in the user's family.
        await r.sadd(family_key, jti)  # type: ignore[misc]
        await r.expire(family_key, _TTL_SECONDS)
        return RotationResult(ok=True, replay_detected=False)
    return RotationResult(ok=False, replay_detected=False)


async def _revoke_family(r: Redis, user_id: UUID) -> int:
    """Mark every jti in the user's family as revoked.

    Returns:
        Number of jti's revoked.
    """
    family_key = _KEY_FAMILY.format(user_id=str(user_id))
    raw_members: set[Any] = await r.smembers(family_key)  # type: ignore[misc]
    members: set[bytes] = {m for m in raw_members if isinstance(m, bytes | bytearray)}
    if not members:
        return 0
    pipe = await r.pipeline()  # type: ignore[misc]
    for jti in members:
        jti_str = jti.decode() if isinstance(jti, bytes | bytearray) else jti
        pipe.set(_KEY_USED.format(jti=jti_str), b"1", ex=_TTL_SECONDS)
    pipe.delete(family_key)
    await pipe.execute()
    return len(members)


async def revoke_all_for_user(user_id: UUID) -> int:
    """Public API to revoke every outstanding refresh token for a user.

    Used by `/auth/logout` and by the replay-detection flow above.
    """
    async for r in _with_redis():
        return await _revoke_family(r, user_id)
    return 0

