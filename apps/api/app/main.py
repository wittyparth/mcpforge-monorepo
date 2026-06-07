"""FastAPI application factory for MCPForge.

Consolidates Main API routes, MCP Gateway endpoints, and WebSocket Playground
into one FastAPI app with different route prefixes.
# TODO(phase-2): Split into 3 separate services when traffic justifies independent scaling.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.database import check_db_health
from app.core.exceptions import (
    AppError,
    app_error_handler,
    unhandled_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.redis import check_redis_health, shutdown_redis
from app.gateway.mcp_server import router as mcp_router
from app.playground.ws import router as playground_router
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: setup logging, startup tasks, shutdown tasks."""
    # Startup
    setup_logging()
    logger = get_logger("app.main")
    logger.info(
        "Starting MCPForge API",
        environment=settings.ENVIRONMENT,
        version=settings.API_VERSION,
    )

    yield

    # Shutdown
    logger.info("Shutting down MCPForge API")
    await shutdown_redis()


app = FastAPI(
    title="MCPForge API",
    description="Convert OpenAPI specs into AI-optimized MCP servers",
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ──────────────────────────────────────────────────────────────

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Request ID middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Attach a unique request ID to each request and logger context."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Exception handlers ──────────────────────────────────────────────────────

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)


# ── Routes ──────────────────────────────────────────────────────────────────

app.include_router(v1_router)
app.include_router(mcp_router)
app.include_router(playground_router)


# ── Health check ────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Root health check endpoint.

    Checks database and Redis connectivity (best-effort).
    Returns ok even if dependencies are down — just marks them.
    """
    try:
        db_ok = await check_db_health()
    except Exception:
        db_ok = False

    try:
        redis_ok = await check_redis_health()
    except Exception:
        redis_ok = False

    return HealthResponse(
        status="ok",
        version=settings.API_VERSION,
        db="ok" if db_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
    )
