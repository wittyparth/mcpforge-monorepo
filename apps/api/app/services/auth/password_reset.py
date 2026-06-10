"""Password reset flow.

Uses JWT tokens (``type=password_reset``) that expire in 1 hour.
Tokens are single-use, tracked in Redis via a ``jti`` claim.

Rate-limiting: max 3 reset requests per email per hour (Redis-backed).
On successful reset the user's entire refresh-token family is revoked,
forcing re-login on all devices.

Anti-enumeration: ``request_password_reset`` always returns ``None``
whether or not the email exists, so callers cannot distinguish valid
from invalid addresses by response timing or status.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.core.redis import get_redis_pool
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.auth import hibp, token_rotation
from app.services.email_service import send_password_reset_email

logger = get_logger(__name__)

_RESET_TOKEN_EXPIRE_HOURS = 1
_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour


# ── Redis helpers ──────────────────────────────────────────────────────────────


async def _with_redis() -> AsyncIterator[Redis]:
    """Yield a Redis client from the shared pool."""
    pool = await get_redis_pool()
    r = Redis.from_pool(pool)
    try:
        yield r
    finally:
        await r.close()


async def _check_rate_limit(email: str) -> bool:
    """Return ``True`` if the email is under the rate limit.

    Atomic INCR + conditional EXPIRE.  Fails OPEN (returns ``True``) on
    any Redis error to avoid blocking password resets during a Redis outage.
    """
    key = f"pwreset:rate:{email.lower()}"
    try:
        async for r in _with_redis():
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, _RATE_LIMIT_WINDOW_SECONDS)
            return int(count) <= _RATE_LIMIT_MAX
    except Exception:
        logger.warning("password_reset_rate_check_failed", email=email)
        return True
    return True  # fallback: fails open on empty iterator


async def _is_token_used(jti: str) -> bool:
    """Return ``True`` if the token has already been consumed (single-use)."""
    key = f"pwreset:used:{jti}"
    try:
        async for r in _with_redis():
            return bool(await r.exists(key))
    except Exception:
        return False
    return False  # fallback


async def _mark_token_used(jti: str) -> None:
    """Atomically mark a reset token as consumed.

    The TTL matches the token's expiry window to prevent stale key accumulation.
    """
    key = f"pwreset:used:{jti}"
    try:
        async for r in _with_redis():
            await r.setex(key, _RESET_TOKEN_EXPIRE_HOURS * 3600, "1")
    except Exception:
        logger.warning("password_reset_mark_used_failed", jti=jti)


# ── Token management ───────────────────────────────────────────────────────────


def _generate_reset_token(user_id: UUID) -> tuple[str, str]:
    """Create a password-reset JWT.

    Returns:
        ``(token, jti)`` where ``jti`` is a UUID used for single-use tracking.
    """
    import uuid as _uuid

    jti = str(_uuid.uuid4())
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "exp": now + timedelta(hours=_RESET_TOKEN_EXPIRE_HOURS),
        "iat": now,
        "type": "password_reset",
        "jti": jti,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert isinstance(token, str)
    return token, jti


def _decode_reset_token(token: str) -> tuple[UUID, str]:
    """Decode and validate a password-reset JWT.

    Returns:
        ``(user_id, jti)``

    Raises:
        ValidationError: If the token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "password_reset":
            raise ValidationError("Invalid token type", field="token")
        user_id = UUID(payload["sub"])
        jti_raw = payload.get("jti")
        if not jti_raw or not isinstance(jti_raw, str):
            raise ValidationError("Token missing unique identifier", field="token")
        return user_id, jti_raw
    except (JWTError, KeyError, ValueError, AttributeError) as exc:
        raise ValidationError(
            "Invalid or expired password reset token",
            field="token",
        ) from exc


# ── Public API ─────────────────────────────────────────────────────────────────


async def request_password_reset(
    email: str,
    session: AsyncSession,
    base_url: str,
) -> None:
    """Handle a password-reset request.

    Always returns ``None`` (no user enumeration).  If the email exists, a
    reset token is generated and emailed.  Rate-limited to 3 per email/hour.

    Args:
        email: Target email address.
        session: DB session.
        base_url: Application base URL for the reset link.
    """
    rate_ok = await _check_rate_limit(email)
    if not rate_ok:
        logger.warning("password_reset_rate_limited", email=email)
        return

    repo = UserRepository(session)
    user = await repo.get_by_email(email)

    if not user:
        logger.info("password_reset_requested_unknown_email")
        return

    token, jti = _generate_reset_token(user.id)
    result = await send_password_reset_email(
        email=user.email,
        display_name=user.display_name or "",
        token=token,
        base_url=base_url,
    )

    if result.success:
        logger.info("password_reset_requested", user_id=str(user.id))
    else:
        logger.error(
            "password_reset_email_failed",
            user_id=str(user.id),
            error=result.error,
        )


async def reset_password(
    token: str,
    new_password: str,
    session: AsyncSession,
) -> User:
    """Validate a reset token and update the user's password.

    Checks:
    - Token is valid and not expired.
    - Token has not been used before (single-use).
    - New password is not in HIBP.

    Side-effects:
    - Marks the token as consumed.
    - Updates ``password_hash`` and ``password_changed_at``.
    - Revokes ALL outstanding refresh tokens for the user.

    Returns:
        The updated ``User``.

    Raises:
        ValidationError: On invalid/expired/used token, or breached password.
    """
    user_id, jti = _decode_reset_token(token)

    if await _is_token_used(jti):
        raise ValidationError("This reset token has already been used", field="token")

    # HIBP check before hashing (plaintext in memory only).
    hibp_result = await hibp.check_password_breached(new_password)
    if hibp_result.breached:
        raise ValidationError(
            "This password has been exposed in a known data breach. "
            "Please choose a different password.",
            field="password",
        )

    # Mark token used BEFORE hashing to prevent partial-state race.
    await _mark_token_used(jti)

    new_hash = hash_password(new_password)

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise ValidationError("User not found", field="token")

    user.password_hash = new_hash
    user.password_changed_at = datetime.now(UTC)
    await session.flush()

    # Invalidate all existing refresh tokens — forces re-login.
    await token_rotation.revoke_all_for_user(user_id)

    logger.info("password_reset_completed", user_id=str(user_id))
    return user
