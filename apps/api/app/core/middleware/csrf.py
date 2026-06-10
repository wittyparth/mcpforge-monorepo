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

# Routes that are exempt from CSRF.
#
# Rationale: CSRF protects authenticated sessions. Unauthenticated endpoints
# (register, login, forgot/reset password) have no session to protect — the
# attacker can't forge a request because there's no auth cookie to exploit.
#
# - register, login:  unauthenticated, no session
# - forgot/reset:     unauthenticated, no session
# - logout:           optional auth, clears cookies (harmless to call twice)
# - refresh:          cookie-only, CSRF doesn't help (cookie is the credential)
# - github/callback:  external OAuth with its own state verification
# - billing/webhook:  Stripe-signed, independent verification
_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/github/callback",
        "/api/v1/auth/verify-email",
        "/api/v1/billing/webhook",
        "/api/v1/team",
        "/api/v1/team/invite",
        "/api/v1/team/accept",
        "/api/v1/team/members",
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
        secure=settings.is_production,  # Required for SameSite=None in modern browsers
        samesite="none" if settings.is_production else "lax",
        path="/",
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests missing a valid X-CSRF-Token header.

    Must be registered BEFORE the auth middleware so an unauthenticated
    malicious request can't even reach the auth check.
    """

    @staticmethod
    def _is_gateway_admin_path(path: str) -> bool:
        """Check if path is a gateway admin endpoint (JWT-protected, no CSRF needed).

        Matches: /api/v1/servers/{uuid}/{pause,resume,connect,connect/test,deploy}
        """
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            return False
        if parts[:3] != ["api", "v1", "servers"]:
            return False
        action = "/".join(parts[4:])  # everything after the UUID
        return action in ("pause", "resume", "connect", "connect/test", "deploy")

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in SAFE_METHODS:
            return await call_next(request)
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        if request.url.path.startswith("/mcp/") or request.url.path.startswith("/ws/"):
            return await call_next(request)
        # Gateway admin endpoints (JWT-authenticated, not browser forms).
        if self._is_gateway_admin_path(request.url.path):
            return await call_next(request)
        if not settings.is_production and settings.ENVIRONMENT == "testing":
            return await call_next(request)
        # API key auth — no CSRF needed (the key itself is the auth credential).
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer mcpforge_live_"):
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
