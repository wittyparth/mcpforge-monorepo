"""JWT token handling and password hashing utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Use bcrypt hashing (argon2 requires extra deps; bcrypt is simpler for Phase 1)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    result = pwd_context.verify(plain_password, hashed_password)
    assert isinstance(result, bool)
    return result


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    result = pwd_context.hash(password)
    assert isinstance(result, str)
    return result


def create_access_token(
    subject: UUID | str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a short-lived JWT access token.

    Args:
        subject: The user ID (or other identifier) to embed in the token.
        extra_claims: Optional additional claims to include.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.JWT_ACCESS_TTL_MINUTES
    )
    claims: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)
    result = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert isinstance(result, str)
    return result


def create_refresh_token(subject: UUID | str) -> str:
    """Create a long-lived JWT refresh token.

    Args:
        subject: The user ID to embed.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(UTC) + timedelta(
        days=settings.JWT_REFRESH_TTL_DAYS
    )
    claims: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    result = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert isinstance(result, str)
    return result


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT string to decode.

    Returns:
        Decoded payload dictionary.

    Raises:
        JWTError: If the token is invalid or expired.
    """
    result = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert isinstance(result, dict)
    return result
