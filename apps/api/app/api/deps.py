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
from app.services.api_key_service import ApiKeyService

API_KEY_PREFIX = "mcpforge_live_"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session. Wraps core dependency for convenience."""
    async for session in _get_db():
        yield session


async def _authenticate_with_api_key(
    token: str,
    session: AsyncSession,
    request: Request,
) -> object:
    """Try API key authentication. Returns user or raises."""
    service = ApiKeyService(session)
    user = await service.authenticate(token)
    if user is None:
        raise UnauthorizedError("Invalid or revoked API key")
    # Look up the key to set on request.state for downstream scope checks
    key_hash = __import__("hashlib").sha256(token.encode()).hexdigest()
    from app.repositories.api_key_repo import ApiKeyRepository

    api_key = await ApiKeyRepository(session).get_by_hash(key_hash)
    request.state.api_key = api_key
    return user


def _get_bearer_token(
    authorization: str | None,
    access_token: str | None,
) -> str | None:
    """Extract a bearer token from Authorization header or cookie."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return access_token


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
) -> object:
    """Dependency that extracts and validates the current user.

    Authentication order:
    1. ``Authorization: Bearer mcpforge_live_...`` → API key auth
    2. ``Authorization: Bearer <jwt>`` → JWT auth
    3. ``access_token`` cookie → JWT auth

    When authenticated via API key, the ``ApiKey`` object is stored on
    ``request.state.api_key`` for downstream scope checks.
    """
    token = _get_bearer_token(authorization, access_token)

    if not token:
        raise UnauthorizedError("Not authenticated")

    # API key auth
    if token.startswith(API_KEY_PREFIX):
        return await _authenticate_with_api_key(token, session, request)

    # JWT auth
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
    token = _get_bearer_token(authorization, access_token)

    if not token:
        return None

    # API key auth
    if token.startswith(API_KEY_PREFIX):
        service = ApiKeyService(session)
        user = await service.authenticate(token)
        if user is not None:
            key_hash = __import__("hashlib").sha256(token.encode()).hexdigest()
            from app.repositories.api_key_repo import ApiKeyRepository

            api_key = await ApiKeyRepository(session).get_by_hash(key_hash)
            request.state.api_key = api_key
        return user

    # JWT auth
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


def get_current_api_key(request: Request) -> object | None:
    """Dependency that returns the current API key from request state.

    Returns the ApiKey object if the request was authenticated via API key,
    or None if JWT auth was used. Useful for scope-checking endpoints.
    """
    return getattr(request.state, "api_key", None)

