"""Structured logging setup using structlog.

Configures structlog with JSON rendering in production and
console rendering in development. Called from the app lifespan.

The `strip_sensitive_processor` is appended to the processor chain to
redact any log field whose key contains sensitive substrings
(`authorization`, `api_key`, `password`, `secret`, `token`, `cookie`,
`bearer`). String values are also scanned recursively for those substrings
and the values are replaced with `[REDACTED]`.

This is the safety net for accidental credential leakage. The primary defense
is to NEVER log credentials, but if a developer slips up, the processor
catches it before the log line hits stdout.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from app.core.config import settings

_SENSITIVE_KEY_PATTERNS = (
    "authorization",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "bearer",
    "credential",
    "private_key",
)

_SENSITIVE_KEY_RE = re.compile(
    "|".join(re.escape(p) for p in _SENSITIVE_KEY_PATTERNS),
    re.IGNORECASE,
)
_VALUE_REDACTED = "[REDACTED]"


def _redact_value(value: Any) -> Any:
    """Recursively redact string values whose content looks like a credential."""
    if isinstance(value, str):
        if _SENSITIVE_KEY_RE.search(value):
            return _VALUE_REDACTED
        return value
    if isinstance(value, dict):
        return {k: strip_sensitive_processor(None, "", {k: v})[k] for k, v in value.items()}
    if isinstance(value, list | tuple):
        cleaned = [_redact_value(v) for v in value]
        return type(value)(cleaned) if isinstance(value, tuple) else cleaned
    return value


def strip_sensitive_processor(
    logger: Any,  # noqa: ARG001 — structlog signature
    method_name: str,  # noqa: ARG001
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Structlog processor that strips sensitive fields from log records.

    Behavior:
    - Drop any key whose lowercased name contains a sensitive substring.
    - For any remaining string value, if its content contains a sensitive
      substring (e.g., a Bearer token accidentally embedded in a URL), replace
      the value with `[REDACTED]`.
    - Recurse into nested dicts and lists.
    """
    for key in list(event_dict.keys()):
        if _SENSITIVE_KEY_RE.search(key):
            event_dict[key] = _VALUE_REDACTED
        else:
            event_dict[key] = _redact_value(event_dict[key])
    return event_dict


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
            strip_sensitive_processor,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())
    if not root_logger.handlers:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(settings.LOG_LEVEL.upper())
        root_logger.addHandler(stdout_handler)

    for name in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Get a structlog logger instance.

    Args:
        name: Optional logger name (defaults to caller's module).

    Returns:
        A bound structlog logger. The return type is `Any` because structlog's
        proxy is resolved lazily on first call.
    """
    return structlog.get_logger(name or __name__)
