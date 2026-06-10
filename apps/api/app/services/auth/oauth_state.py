"""OAuth state management for CSRF protection.

Uses Redis to store single-use OAuth state tokens. The state parameter
prevents CSRF attacks on the OAuth callback: when the user starts the
OAuth flow, a random state is stored in Redis. The callback verifies
the state parameter matches and atomically consumes it, preventing
replay attacks.

Keys:
- ``oauth:state:<state>`` — marker; TTL = 600s (10 min), single-use via GETDEL.
"""

from __future__ import annotations

import secrets

from redis.asyncio import Redis

_OAUTH_STATE_PREFIX = "oauth:state:"
_STATE_TTL_SECONDS = 600  # 10 minutes


def generate_state() -> str:
    """Generate a cryptographically random state string.

    Returns:
        A URL-safe base64-encoded random string (32 bytes → 43 chars).
    """
    return secrets.token_urlsafe(32)


async def store_state(
    redis: Redis,
    state: str,
    ttl_seconds: int = _STATE_TTL_SECONDS,
) -> None:
    """Store an OAuth state token in Redis with a TTL.

    Args:
        redis: Redis client instance.
        state: The state string to store.
        ttl_seconds: Time-to-live in seconds (default 600).
    """
    key = f"{_OAUTH_STATE_PREFIX}{state}"
    await redis.setex(key, ttl_seconds, b"1")


async def verify_and_consume_state(redis: Redis, state: str) -> bool:
    """Atomically verify and consume an OAuth state token.

    Uses Redis GETDEL for atomic check-and-delete semantics. This prevents
    race conditions where the same state could be consumed twice.

    Args:
        redis: Redis client instance.
        state: The state string received from the OAuth callback.

    Returns:
        True if the state was valid and has been consumed (first use).
        False if the state was never issued, expired, or already consumed.
    """
    key = f"{_OAUTH_STATE_PREFIX}{state}"
    result = await redis.getdel(key)
    return result is not None
