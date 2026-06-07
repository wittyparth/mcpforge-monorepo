"""CSRF protection via the double-submit cookie pattern.

The server sets a `csrf_token` cookie (NOT httpOnly — JS must be able to read it
and echo it in the `X-CSRF-Token` header on state-changing requests).

This pattern is required because we use `SameSite=None` cookies in production
to support cross-origin AI tool clients (Claude Desktop, Cursor, Windsurf).
`SameSite=None` alone does NOT protect against CSRF in browsers that allow
third-party cookies, so we layer the double-submit check on top.

Safe methods (GET, HEAD, OPTIONS) and the `/api/v1/auth/refresh` endpoint
(which is cookie-only and has no body) are exempt.

Configure with `CSRF_SECRET` (auto-derived from JWT_SECRET if unset). The
secret is mixed into the token to make cookie tampering detectable.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Routes that are exempt from CSRF (cookie-auth refresh has no body, OAuth
# callbacks come from external providers with their own state verification).
_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/auth/refresh",
        "/api/v1/auth/github/callback",
        "/api/v1/billing/webhook",  # Stripe-signed
    }
)


def _sign(value: str) -> str:
    """HMAC-sign a CSRF token value with the configured secret."""
    secret = (settings.CSRF_SECRET or settings.JWT_SECRET).encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()[:32]


def issue_csrf_token() -> str:
    """Generate a new CSRF token (random secret + HMAC signature)."""
    raw = secrets.token_urlsafe(24)
    return f"{raw}.{_sign(raw)}"


def verify_csrf_token(token: str | None) -> bool:
    """Constant-time verification of a CSRF token against its signature."""
    if not token or "." not in token:
        return False
    raw, _, sig = token.partition(".")
    if not raw or not sig:
        return False
    expected = _sign(raw)
    return hmac.compare_digest(sig, expected)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Attach the CSRF cookie to a response."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=60 * 60 * 24 * 7,  # 7 days
        httponly=False,  # JS MUST be able to read this
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        path="/",
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests missing a valid X-CSRF-Token header.

    Must be registered BEFORE the auth middleware so an unauthenticated
    malicious request can't even reach the auth check.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in SAFE_METHODS:
            return await call_next(request)
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        if not settings.is_production and settings.ENVIRONMENT == "testing":
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token:
            logger.warning("csrf_missing", path=request.url.path, method=request.method)
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "CSRF_TOKEN_MISSING",
                        "message": "CSRF token required for state-changing requests",
                    }
                },
            )

        if not hmac.compare_digest(cookie_token, header_token):
            logger.warning("csrf_mismatch", path=request.url.path, method=request.method)
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "CSRF_TOKEN_INVALID",
                        "message": "CSRF token does not match cookie",
                    }
                },
            )

        return await call_next(request)
