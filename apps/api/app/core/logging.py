"""Structured logging setup using structlog.

Configures structlog with JSON rendering in production and
console rendering in development. Called from the app lifespan.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure structlog and standard library logging.

    Call once during application startup (lifespan).
    """
    if settings.is_production:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set the root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    # Quiet noisy third-party loggers
    for name in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Get a structlog logger instance.

    Args:
        name: Optional logger name (defaults to caller's module).

    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger(name or __name__)
