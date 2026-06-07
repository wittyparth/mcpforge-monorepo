"""Shared FastAPI dependencies.

Provides get_current_user, get_optional_current_user, and get_db shorthand.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Cookie, Depends, Header, Request
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as _get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.repositories.user_repo import UserRepository


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session. Wraps core dependency for convenience."""
    async for session in _get_db():
        yield session


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
) -> object:
    """Dependency that extracts and validates the current user.

    Checks Authorization header first, then falls back to httpOnly cookie.
    """
    token: str | None = None

    # Try Authorization header first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    # Fall back to cookie
    if not token:
        token = access_token

    if not token:
        raise UnauthorizedError("Not authenticated")

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise UnauthorizedError("Invalid or expired token") from None

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedError("User not found")

    return user


async def get_optional_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
) -> object | None:
    """Like get_current_user but returns None instead of raising on unauthenticated."""
    token: str | None = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token:
        token = access_token

    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None

    user_repo = UserRepository(session)
    return await user_repo.get_by_id(user_id)


# Canonical alias used by route handlers. Defined at module bottom so the
# forward reference to get_optional_current_user resolves.
get_current_user_optional = get_optional_current_user

