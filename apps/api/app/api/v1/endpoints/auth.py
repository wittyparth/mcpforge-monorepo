"""Authentication endpoints: register, login, logout, refresh, me,
forgot-password, reset-password, verify-email, resend-verification."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, get_db
from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.middleware.csrf import issue_csrf_token, set_csrf_cookie
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services.auth.oauth_github import GitHubOAuth
from app.services.auth.oauth_state import generate_state, store_state, verify_and_consume_state
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
    _samesite: Literal["lax", "none"] = "none" if settings.is_production else "lax"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.is_production,
        samesite=_samesite,
        max_age=settings.JWT_ACCESS_TTL_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite=_samesite,
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
    current_user: object | None = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Log out: revoke all refresh tokens + clear auth cookies.

    Auth is optional: if the request is authenticated, we revoke the
    user's token family; if not, we just clear the cookies. This
    matches the legacy behavior (logout always returns 200) and the
    new hardening (authed requests get a full token-family revoke).
    """
    user_id_raw = getattr(current_user, "id", None) if current_user else None
    user_id: UUID | None = user_id_raw if isinstance(user_id_raw, UUID) else None
    svc = AuthService(session)
    await svc.logout(user_id)
    _clear_auth_cookies(response)
    response.delete_cookie("csrf_token", path="/")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: object = Depends(get_current_user),
) -> UserResponse:
    """Get the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ── F7: Email verification & password reset ──


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Request a password reset email.

    Always returns 200 with the same message, regardless of whether the
    email exists in the system (prevents user enumeration).  Rate-limited
    to 3 requests per email per hour.
    """
    svc = AuthService(session)
    await svc.request_password_reset(
        email=body.email,
        base_url=settings.APP_URL,
    )
    return MessageResponse(
        message="If an account with that email exists, a password reset link has been sent.",
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Reset a password using a token from the email.

    On success, all existing sessions are invalidated and the user must
    log in again.

    Raises:
        422: Token invalid/expired/used, or the password is in HIBP.
    """
    svc = AuthService(session)
    await svc.reset_password(token=body.token, new_password=body.password)
    return MessageResponse(message="Password reset. Please log in with your new password.")


@router.post("/verify-email", response_model=UserResponse)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db),
    current_user: object = Depends(get_current_user),
) -> UserResponse:
    """Verify the authenticated user's email using a verification token.

    The token was sent via email during registration (or via
    ``/resend-verification``).  Must be authenticated.

    Raises:
        422: Token invalid or expired.
    """
    svc = AuthService(session)
    user = await svc.verify_email(token=body.token)
    return UserResponse.model_validate(user)


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    session: AsyncSession = Depends(get_db),
    current_user: object = Depends(get_current_user),
) -> MessageResponse:
    """Resend the email-verification email.

    Must be authenticated.  Generates a fresh token and sends a new email.
    Does NOT invalidate any previously sent tokens (all remain valid until
    their 24-hour expiry or until the user verifies).
    """
    from app.models.user import User

    assert isinstance(current_user, User)
    svc = AuthService(session)
    await svc.resend_verification(current_user)
    return MessageResponse(message="Verification email sent.")


# ── F7: GitHub OAuth ──


def _get_redirect_uri(request: Request) -> str:
    """Determine the callback URL for GitHub OAuth.

    Uses the configured redirect URI if set, otherwise constructs it
    from the current request's base URL.
    """
    if settings.GITHUB_OAUTH_REDIRECT_URI:
        return settings.GITHUB_OAUTH_REDIRECT_URI
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/auth/github/callback"


def _oauth_error_redirect(error_code: str) -> RedirectResponse:
    """Build a redirect to the frontend with an OAuth error code."""
    frontend = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(url=f"{frontend}?oauth=error={error_code}")


@router.get("/github")
async def github_oauth_start(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Start GitHub OAuth 2.0 authorization code flow.

    Generates a CSRF-protecting state token, stores it in Redis, and
    redirects the user to GitHub's authorization page.

    Returns:
        302 redirect to ``https://github.com/login/oauth/authorize?...``.

    Raises:
        503: If GitHub OAuth is not configured (``GITHUB_OAUTH_CLIENT_ID``
            is empty).
    """
    if not settings.GITHUB_OAUTH_CLIENT_ID:
        raise ServiceUnavailableError(
            "GitHub OAuth not configured. Set GITHUB_OAUTH_CLIENT_ID "
            "and GITHUB_OAUTH_CLIENT_SECRET in your environment."
        )

    state = generate_state()
    await store_state(redis, state)

    redirect_uri = _get_redirect_uri(request)
    gh = GitHubOAuth()
    authorize_url = gh.get_authorization_url(state=state, redirect_uri=redirect_uri)

    return RedirectResponse(url=authorize_url)


@router.get("/github/callback")
async def github_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = Query(None),
    state: str | None = Query(None),
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the OAuth callback from GitHub.

    Verifies the CSRF state parameter, exchanges the authorization code
    for an access token, fetches the user's GitHub profile and verified
    email, and upserts the user in the database.

    On success, sets auth cookies and CSRF cookie, then redirects to
    ``FRONTEND_URL?oauth=success``. On failure, redirects with
    ``?oauth=error=<code>``.

    All errors result in a redirect (never raw JSON) because the user's
    browser is in the middle of the OAuth redirect chain — showing JSON
    would be a poor UX. The frontend parses the ``oauth`` query param
    and displays appropriate feedback.

    Raises:
        503: If GitHub OAuth is not configured.
    """
    if not settings.GITHUB_OAUTH_CLIENT_ID:
        raise ServiceUnavailableError(
            "GitHub OAuth not configured. Set GITHUB_OAUTH_CLIENT_ID "
            "and GITHUB_OAUTH_CLIENT_SECRET in your environment."
        )

    # 1. Validate authorization code
    if not code:
        return _oauth_error_redirect("missing_code")

    # 2. Verify and consume state (prevents CSRF + replay)
    if not state or not await verify_and_consume_state(redis, state):
        return _oauth_error_redirect("invalid_state")

    gh = GitHubOAuth()
    redirect_uri = _get_redirect_uri(request)

    # 3. Exchange code for access token
    try:
        token_response = await gh.exchange_code(code=code, redirect_uri=redirect_uri)
    except ServiceUnavailableError:
        raise
    except Exception:
        return _oauth_error_redirect("exchange_failed")

    access_token: str | None = token_response.get("access_token")
    if not access_token:
        return _oauth_error_redirect("exchange_failed")

    # 4. Fetch GitHub user profile
    try:
        github_user = await gh.get_github_user(access_token)
    except Exception:
        return _oauth_error_redirect("github_api_error")

    # 5. Fetch primary verified email
    email = await gh.get_primary_email(access_token)

    # Fallback: use public email from GitHub profile
    if not email:
        email = github_user.get("email")

    if not email:
        return _oauth_error_redirect("no_email")

    # 6. Upsert the user (create / link / update)
    try:
        user = await gh.upsert_user(
            session=session,
            github_user=github_user,
            email=email,
        )
    except ServiceUnavailableError:
        raise
    except Exception:
        return _oauth_error_redirect("email_conflict")

    # 7. Issue token pair and CSRF cookie
    access_token_jwt = create_access_token(subject=user.id)
    refresh_token_jwt = create_refresh_token(subject=user.id)

    redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL.rstrip('/')}?oauth=success"
    )
    _set_auth_cookies(redirect, access_token_jwt, refresh_token_jwt)
    set_csrf_cookie(redirect, issue_csrf_token())

    return redirect
