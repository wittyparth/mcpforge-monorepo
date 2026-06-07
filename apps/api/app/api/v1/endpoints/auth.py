"""Authentication endpoints: register, login, logout, refresh, me."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.middleware.csrf import issue_csrf_token, set_csrf_cookie
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Set httpOnly cookies for access and refresh tokens.

    Uses SameSite=None in production (cross-origin: Vercel frontend -> Render
    backend) and SameSite=Lax in development (same-origin: localhost).
    """
    samesite: str = "none" if settings.is_production else "lax"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.is_production,  # required when SameSite=None
        samesite=samesite,
        max_age=settings.JWT_ACCESS_TTL_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite=samesite,
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
    """Register a new user account.

    Raises:
        409: Email already registered.
        422: Password appears in HIBP.
    """
    svc = AuthService(session)
    result = await svc.register(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
    )
    _set_auth_cookies(response, result["access_token"], result["refresh_token"])
    set_csrf_cookie(response, issue_csrf_token())

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
    """Authenticate and log in.

    Raises:
        401: Invalid credentials.
        423: Account locked (too many failed attempts).
    """
    svc = AuthService(session)
    result = await svc.login(email=body.email, password=body.password)
    _set_auth_cookies(response, result["access_token"], result["refresh_token"])
    set_csrf_cookie(response, issue_csrf_token())

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
    """Refresh the access token using a refresh token from cookie.

    Exempt from CSRF (the cookie carries the credential; the body is empty).
    Implements refresh token rotation with replay detection: reusing an
    already-used jti revokes the user's entire token family.
    """
    if not refresh_token:
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError("No refresh token provided")

    svc = AuthService(session)
    result = await svc.refresh(refresh_token)
    _set_auth_cookies(response, result["access_token"], result["refresh_token"])
    set_csrf_cookie(response, issue_csrf_token())

    user = result["user"]
    return AuthResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: object = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Log out: revoke all refresh tokens + clear auth cookies.

    Requires authentication so we can identify which user to revoke.
    """
    svc = AuthService(session)
    await svc.logout(getattr(current_user, "id", None))
    _clear_auth_cookies(response)
    response.delete_cookie("csrf_token", path="/")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: object = Depends(get_current_user),
) -> UserResponse:
    """Get the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ── Wave 0 Skeleton: F7 auth flows (return 501 until F7 implements) ──


@router.post("/forgot-password", status_code=501)
async def forgot_password() -> None:
    """Request a password reset email. Pending F7."""
    from app.core.exceptions import NotImplementedFeatureError
    raise NotImplementedFeatureError("Password reset: pending F7")


@router.post("/reset-password", status_code=501)
async def reset_password() -> None:
    """Reset password using a token from the email. Pending F7."""
    from app.core.exceptions import NotImplementedFeatureError
    raise NotImplementedFeatureError("Password reset: pending F7")


@router.post("/verify-email", status_code=501)
async def verify_email() -> None:
    """Verify an email using a token. Pending F7."""
    from app.core.exceptions import NotImplementedFeatureError
    raise NotImplementedFeatureError("Email verification: pending F7")


@router.get("/github", status_code=501)
async def github_oauth_start() -> None:
    """Redirect to GitHub OAuth. Pending F7."""
    from app.core.exceptions import NotImplementedFeatureError
    raise NotImplementedFeatureError("GitHub OAuth: pending F7")


@router.get("/github/callback", status_code=501)
async def github_oauth_callback() -> None:
    """Handle GitHub OAuth callback. Pending F7."""
    from app.core.exceptions import NotImplementedFeatureError
    raise NotImplementedFeatureError("GitHub OAuth: pending F7")
