"""Request-ID middleware.

Generates (or accepts) a per-request UUID v4, stores it in a `contextvars.ContextVar`
so any structlog log record emitted during the request is automatically tagged,
and echoes it back as the `X-Request-ID` response header.

Why a ContextVar and not request.state? The structlog context-vars processor
already binds via `contextvars`, so we share the same mechanism. This makes
the request_id visible to:
- All structlog log records (via `merge_contextvars` processor)
- Celery tasks kicked off in the request (passed explicitly as `request_id=...`)
- Any code that imports `get_request_id()` from this module
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"


def get_request_id() -> str | None:
    """Return the request_id bound to the current async context, or None."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Bind a request_id to the current async context."""
    _request_id_var.set(request_id)
    structlog.contextvars.bind_contextvars(request_id=request_id)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that attaches a UUID v4 request_id to every request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and _is_safe_request_id(incoming) else str(uuid.uuid4())
        set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _is_safe_request_id(value: str) -> bool:
    """Allow only safe chars in client-supplied request IDs (defense in depth)."""
    if not value or len(value) > 128:
        return False
    return all(c.isalnum() or c in "-_." for c in value)
