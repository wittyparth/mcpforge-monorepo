"""Email verification token management.

Tokens are signed JWTs (``type=email_verify``) that expire in 24 hours.
The token encodes the user's UUID as the ``sub`` claim so the verification
endpoint can identify the user without additional parameters.

Flow:
    1. ``generate_verification_token(user_id) → str``
    2. Email sent with ``/verify-email?token=<token>`` link.
    3. ``verify_email_token(token) → user_id``
    4. ``verify_and_mark(user_id, session) → User``
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.email_service import send_verification_email

logger = get_logger(__name__)

_VERIFY_TOKEN_EXPIRE_HOURS = 24


def generate_verification_token(user_id: UUID) -> str:
    """Create a signed JWT for email verification.

    Args:
        user_id: The user's UUID.

    Returns:
        A signed JWT string with ``type=email_verify`` and 24-hour expiry.
    """
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "exp": now + timedelta(hours=_VERIFY_TOKEN_EXPIRE_HOURS),
        "iat": now,
        "type": "email_verify",
    }
    result = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert isinstance(result, str)
    return result


def verify_email_token(token: str) -> UUID:
    """Decode and validate an email verification token.

    Args:
        token: The JWT from the verification email.

    Returns:
        The user's UUID (``sub`` claim).

    Raises:
        ValidationError: If the token is invalid, expired, or has wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "email_verify":
            raise ValidationError("Invalid token type", field="token")
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError, AttributeError) as exc:
        raise ValidationError(
            "Invalid or expired verification token",
            field="token",
        ) from exc


async def send_verification(user: User, base_url: str) -> None:
    """Generate a verification token and dispatch the email.

    Logs errors but never raises, so callers can fire-and-forget.

    Args:
        user: The target user.
        base_url: Application base URL (e.g. ``http://localhost:3000``).
    """
    token = generate_verification_token(user.id)
    result = await send_verification_email(
        email=user.email,
        display_name=user.display_name or "",
        token=token,
        base_url=base_url,
    )
    if result.success:
        logger.info("verification_email_sent", user_id=str(user.id))
    else:
        logger.error(
            "verification_email_failed",
            user_id=str(user.id),
            error=result.error,
        )


async def verify_and_mark(user_id: UUID, session: AsyncSession) -> User:
    """Mark a user's email as verified.

    Args:
        user_id: The user's UUID (from the verified token).
        session: Active DB session.

    Returns:
        The updated ``User``.

    Raises:
        ValidationError: If the user does not exist.
    """
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise ValidationError("User not found", field="token")

    user.email_verified = True
    await session.flush()

    logger.info("email_verified", user_id=str(user.id))
    return user
