"""JWT token handling and password hashing utilities.

Argon2id is the primary password hashing algorithm (per PRD § 13). For
backwards compatibility with users created during Phase 1 (bcrypt), we
maintain a dual-hash CryptContext: on verification, if a stored hash is
bcrypt, we verify against bcrypt and rehash to Argon2id on successful
login. New hashes are always Argon2id.

Refresh tokens carry a `jti` (UUID v4) claim. Token rotation (see
`app.services.auth.token_rotation`) tracks used jti values in Redis to
detect refresh-token reuse — a signal of token theft.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_argon2_hasher = PasswordHasher(
    time_cost=3,        # iterations
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Dual-context: argon2 is primary, bcrypt is the legacy fallback. We keep
# bcrypt in the context so passlib can verify existing Phase 1 hashes
# (the `deprecated="auto"` setting means newly issued hashes are always
# argon2id — the first scheme listed).
_pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated=["bcrypt"],
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: Plain-text password (min length enforced at the schema layer).

    Returns:
        Argon2id PHC string (e.g., `$argon2id$v=19$m=65536,...`).
    """
    result = _pwd_context.hash(password)
    assert isinstance(result, str)
    return result


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored Argon2id or legacy bcrypt hash.

    Returns:
        True if the password matches the hash.

    Note:
        This function NEVER raises. Invalid hash format, algorithm mismatch,
        or corrupt hash strings all return False. Use `needs_rehash` to
        detect when a legacy bcrypt hash should be upgraded.
    """
    try:
        result = _pwd_context.verify(plain_password, hashed_password)
        assert isinstance(result, bool)
        return result
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Return True if the hash should be upgraded (e.g., legacy bcrypt)."""
    try:
        result = _pwd_context.needs_update(hashed_password)
        assert isinstance(result, bool)
        return result
    except Exception:
        return False


def rehash_password(plain_password: str) -> str:
    """Re-hash a password with the current (Argon2id) algorithm."""
    return hash_password(plain_password)


# ── JWT helpers ──────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _new_jti() -> str:
    """Generate a unique JWT ID for refresh token rotation tracking."""
    return str(uuid.uuid4())


def create_access_token(
    subject: uuid.UUID | str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a short-lived JWT access token (15 min default).

    Args:
        subject: User ID (UUID or string).
        extra_claims: Optional extra claims to embed.

    Returns:
        Encoded JWT string with `type=access`.
    """
    expire = _now() + timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES)
    claims: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": _now(),
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)
    result = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert isinstance(result, str)
    return result


def create_refresh_token(
    subject: uuid.UUID | str,
    jti: str | None = None,
) -> str:
    """Create a long-lived JWT refresh token (7 days default) with a `jti` claim.

    The `jti` claim is the rotation primitive. The first time a refresh token
    is used, its jti is recorded in Redis. A second use of the same jti
    indicates token theft and triggers a full revocation of the user's
    sessions.

    Args:
        subject: User ID.
        jti: Optional explicit jti; auto-generated UUID v4 if omitted.

    Returns:
        Encoded JWT string with `type=refresh` and a unique `jti` claim.
    """
    expire = _now() + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
    claims: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": _now(),
        "type": "refresh",
        "jti": jti or _new_jti(),
    }
    result = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert isinstance(result, str)
    return result


def generate_csrf_secret() -> str:
    """Generate a fresh CSRF secret (for tests / startup)."""
    return secrets.token_urlsafe(32)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT string to decode.

    Returns:
        Decoded payload dictionary.

    Raises:
        JWTError: If the token is invalid or expired.
    """
    result = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert isinstance(result, dict)
    return result


__all__ = [
    "JWTError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_csrf_secret",
    "hash_password",
    "needs_rehash",
    "rehash_password",
    "verify_password",
]
