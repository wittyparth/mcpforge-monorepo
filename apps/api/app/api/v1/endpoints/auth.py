"""Authentication endpoints: register, login, logout, refresh, me."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Set httpOnly cookies for access and refresh tokens."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TTL_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TTL_DAYS * 86400,
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


@router.post("/register", response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new user account."""
    svc = AuthService(session)
    result = await svc.register(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
    )
    _set_auth_cookies(response, result["access_token"], result["refresh_token"])

    user = result["user"]
    return AuthResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate and log in."""
    svc = AuthService(session)
    result = await svc.login(email=body.email, password=body.password)
    _set_auth_cookies(response, result["access_token"], result["refresh_token"])

    user = result["user"]
    return AuthResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> AuthResponse:
    """Refresh the access token using a refresh token from cookie."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    svc = AuthService(session)
    result = await svc.refresh(refresh_token)
    _set_auth_cookies(response, result["access_token"], result["refresh_token"])

    user = result["user"]
    return AuthResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Log out by clearing auth cookies."""
    _clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: object = Depends(get_current_user),
) -> UserResponse:
    """Get the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)
