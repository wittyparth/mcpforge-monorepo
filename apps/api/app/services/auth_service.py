"""Authentication business logic.

Handles registration, login, token creation, and token refresh.

Wave 0 additions:
- HIBP password-breach check on register (rejects known-breached passwords).
- Account lockout: 5 failed logins = 15-minute lock (Redis-backed).
- Refresh token rotation: jti is recorded in Redis on first use; a second
  use of the same jti revokes the user's entire token family (theft signal).
- Argon2id is the primary hashing scheme; legacy bcrypt hashes are rehashed
  to Argon2id on successful login.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    LockedError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    needs_rehash,
    verify_password,
)
from app.repositories.user_repo import UserRepository
from app.services.auth import hibp, lockout, token_rotation


class AuthService:
    """Service-layer logic for authentication flows."""

    def __init__(self, session: AsyncSession) -> None:
        self.user_repo = UserRepository(session)

    async def register(
        self,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Register a new user.

        Rejects:
        - Email already registered (409 ConflictError)
        - Password present in HIBP (422 ValidationError, code=PASSWORD_BREACHED)

        Returns:
            Dict with user info and token pair.

        Raises:
            ConflictError: If the email is already registered.
            ValidationError: If the password is in a known breach.
        """
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise ConflictError("Email already registered")

        # Reject passwords found in HIBP. We do this BEFORE hashing so
        # the plaintext password is only ever in memory, never in a log
        # line or DB row.
        hibp_result = await hibp.check_password_breached(password)
        if hibp_result.breached:
            raise ValidationError(
                "This password has been exposed in a known data breach. "
                "Please choose a different password.",
                field="password",
            )

        from app.core.security import hash_password  # local import to avoid cycle

        password_hash = hash_password(password)
        user = await self.user_repo.create(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
        )

        access_token = create_access_token(subject=user.id)
        refresh_token, _ = self._issue_refresh_token(user.id)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate a user and return token pair.

        Side effects:
        - On success, resets the per-email failure counter in Redis.
        - On failure, increments the per-email failure counter; if the
          threshold is hit, the account is locked for LOCKOUT_DURATION_MINUTES.

        Raises:
            UnauthorizedError: If credentials are invalid.
            LockedError: If the account is currently locked out.
        """
        if await lockout.is_locked(email):
            status = await lockout.get_status(email)
            raise LockedError(
                "Account temporarily locked due to too many failed login attempts",
                retry_after=status.retry_after,
            )

        user = await self.user_repo.get_by_email(email)
        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            await lockout.record_failure(email)
            raise UnauthorizedError("Invalid email or password")

        await lockout.record_success(email)

        # Rehash to Argon2id if this is a legacy bcrypt hash.
        if needs_rehash(user.password_hash):
            from app.services.auth.password import rehash_user_with_plaintext
            await rehash_user_with_plaintext(self.user_repo.session, user, password)

        access_token = create_access_token(subject=user.id)
        refresh_token, _ = self._issue_refresh_token(user.id)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def refresh(self, refresh_token_str: str) -> dict[str, Any]:
        """Validate a refresh token and issue a new token pair.

        Rotation flow:
        1. Decode the JWT and extract the `jti` claim.
        2. Atomically mark the jti as used in Redis.
        3. If the jti was already used (replay), revoke the user's entire
           token family and return 401.
        4. Otherwise, issue new access + refresh tokens with a fresh jti.

        Raises:
            UnauthorizedError: If the token is invalid, expired, or replayed.
        """
        try:
            payload = decode_token(refresh_token_str)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Invalid token type")
            jti = payload.get("jti")
            user_id = UUID(payload["sub"])
            if not jti:
                raise UnauthorizedError("Refresh token missing jti")
        except (JWTError, KeyError, ValueError):
            raise UnauthorizedError("Invalid or expired refresh token") from None

        rotation = await token_rotation.check_and_mark_jti(user_id, jti)
        if not rotation.ok:
            # Replay detected — the entire family has been revoked.
            raise UnauthorizedError("Refresh token replay detected; sessions revoked")

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("User not found")

        access_token = create_access_token(subject=user.id)
        new_refresh_token, _ = self._issue_refresh_token(user.id)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": new_refresh_token,
        }

    async def get_current_user(self, user_id: UUID) -> object:
        """Retrieve a user by ID (for dependency injection)."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("User not found")
        return user

    async def logout(self, user_id: UUID) -> None:
        """Revoke all outstanding refresh tokens for the user."""
        await token_rotation.revoke_all_for_user(user_id)

    @staticmethod
    def _issue_refresh_token(user_id: UUID) -> tuple[str, str]:
        """Issue a refresh token, returning (token, jti)."""
        import uuid as _uuid
        jti = str(_uuid.uuid4())
        token = create_refresh_token(subject=user_id, jti=jti)
        return token, jti
