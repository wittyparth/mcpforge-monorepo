"""Authentication business logic.

Handles registration, login, token creation, and token refresh.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.repositories.user_repo import UserRepository


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

        Returns:
            Dict with user info and token pair.

        Raises:
            ConflictError: If the email is already registered.
        """
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise ConflictError("Email already registered")

        password_hash = hash_password(password)
        user = await self.user_repo.create(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
        )

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate a user and return token pair.

        Raises:
            UnauthorizedError: If credentials are invalid.
        """
        user = await self.user_repo.get_by_email(email)
        if not user or not user.password_hash:
            raise UnauthorizedError("Invalid email or password")

        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def refresh(self, refresh_token_str: str) -> dict[str, Any]:
        """Validate a refresh token and issue new tokens.

        Raises:
            UnauthorizedError: If the token is invalid or expired.
        """
        try:
            payload = decode_token(refresh_token_str)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Invalid token type")
            user_id = UUID(payload["sub"])
        except (JWTError, KeyError, ValueError):
            raise UnauthorizedError("Invalid or expired refresh token") from None

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("User not found")

        access_token = create_access_token(subject=user.id)
        new_refresh_token = create_refresh_token(subject=user.id)

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
