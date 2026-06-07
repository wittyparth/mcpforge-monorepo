"""FastAPI application factory for MCPForge.

Consolidates Main API routes, MCP Gateway endpoints, and WebSocket Playground
into one FastAPI app with different route prefixes.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.types import Event, Hint

from app.api.v1.router import router as v1_router
from app.core.celery_app import ping_workers
from app.core.config import settings
from app.core.database import check_db_health
from app.core.exceptions import (
    AppError,
    app_error_handler,
    unhandled_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware.csrf import CSRFMiddleware, issue_csrf_token, set_csrf_cookie
from app.core.middleware.rate_limit import RateLimitMiddleware
from app.core.middleware.request_id import RequestIDMiddleware
from app.core.redis import check_redis_health, shutdown_redis
from app.gateway.mcp_server import router as mcp_router
from app.playground.ws import router as playground_router
from app.schemas.common import HealthResponse

# ── Sentry init (must run before app creation) ──────────────────────────────


def _init_sentry() -> None:
    """Initialize Sentry if SENTRY_DSN is set.

    Sample rate: 100% in dev, configurable (default 10%) in prod.
    `before_send` redacts `Authorization` headers and request bodies for
    credential routes so secrets never leave the process.
    """
    if not settings.SENTRY_DSN:
        return

    def _sanitize(event: Event, hint: Hint) -> Event | None:
        # Strip Authorization headers
        request: dict[str, object] = event.get("request") or {}
        if not request:
            return event
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                k: ("[REDACTED]" if k.lower() == "authorization" else v)
                for k, v in headers.items()
            }
        # Strip bodies for credential routes
        url = str(request.get("url", "") or "")
        if "/credentials" in url or "/auth" in url:
            request["data"] = "[REDACTED]"
        return event

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.sentry_sample_rate,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
        ],
        before_send=_sanitize,
        send_default_pii=False,
    )


_init_sentry()


# ── Lifespan ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: setup logging, startup tasks, shutdown tasks."""
    setup_logging()
    logger = get_logger("app.main")
    logger.info(
        "Starting MCPForge API",
        environment=settings.ENVIRONMENT,
        version=settings.API_VERSION,
    )

    yield

    logger.info("Shutting down MCPForge API")
    await shutdown_redis()


# ── App factory ─────────────────────────────────────────────────────────────


app = FastAPI(
    title="MCPForge API",
    description="Convert OpenAPI specs into AI-optimized MCP servers",
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ─────────────────────────────────────────────────────────────
# Starlette builds middleware in REVERSE order of `user_middleware` (last
# added = outermost). So add middlewares INNERMOST first, OUTERMOST last.
#
# Known issue with ordering: if CORS is INSIDE CSRF, then when CSRF rejects
# a request (no CSRF token), the response never passes through CORS and the
# browser gets no Access-Control-Allow-Origin header. Therefore CORS must
# be OUTER to CSRF (added after CSRF).
#
# Execution order on incoming request (outermost → innermost):
#   AttachCSRFCookie → CORS → RateLimit → CSRF → RequestID → route handler

# 1. Request ID — innermost. Every middleware/handler benefits from having
#    request_id available via contextvars.
app.add_middleware(RequestIDMiddleware)

# 2. CSRF — rejects state-changing requests without a valid CSRF token.
app.add_middleware(CSRFMiddleware)

# 3. Rate limit — per-IP fixed window. Does not count CSRF-rejected reqs.
app.add_middleware(RateLimitMiddleware)

# 4. CORS — must be OUTER to CSRF + RateLimit so their rejection responses
#    get Access-Control-Allow-Origin headers (browsers need these on errors).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
)


# ── Exception handlers ──────────────────────────────────────────────────────

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)


# ── Routes ──────────────────────────────────────────────────────────────────

app.include_router(v1_router)
app.include_router(mcp_router)
app.include_router(playground_router)


# ── CSRF token issuance hook ────────────────────────────────────────────────


@app.middleware("http")
async def attach_csrf_cookie(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Ensure every response carries a CSRF cookie (issues one if missing)."""
    response = await call_next(request)
    if not request.cookies.get("csrf_token"):
        token = issue_csrf_token()
        set_csrf_cookie(response, token)
    return response


# ── Health check ────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Root health check.

    Pings Postgres, Redis, and (best-effort) the Celery worker pool. A
    failure in any dependency is reported as `"unavailable"`/`"down"` in
    the response; the endpoint itself returns 200 to keep load balancers
    happy (use 503-style probing for actual readiness).
    """
    try:
        db_ok = await check_db_health()
    except Exception:
        db_ok = False

    try:
        redis_ok = await check_redis_health()
    except Exception:
        redis_ok = False

    worker_ok = ping_workers(timeout=2.0)

    return HealthResponse(
        status="ok",
        version=settings.API_VERSION,
        db="ok" if db_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
        worker="ok" if worker_ok else "down",
    )
