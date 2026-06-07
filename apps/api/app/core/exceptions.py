"""Custom exception classes and FastAPI exception handlers.

All structured errors follow the format:
    {"error": {"code": "ERROR_CODE", "message": "Human-readable message"}}

The `NotImplementedFeatureError` is special: route stubs in the Wave 0
Skeleton return it with status 501 to signal "this endpoint exists in
the contract but the real implementation lands in a later feature
agent."  Future feature agents must REPLACE these stubs with real
logic and remove the error.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error with a machine-readable code."""

    def __init__(self, code: str, message: str, status_code: int = 500) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    """Resource not found (404)."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(code="NOT_FOUND", message=message, status_code=404)


class UnauthorizedError(AppError):
    """Authentication required (401)."""

    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(code="UNAUTHORIZED", message=message, status_code=401)


class ForbiddenError(AppError):
    """Insufficient permissions (403)."""

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(code="FORBIDDEN", message=message, status_code=403)


class ConflictError(AppError):
    """Resource already exists (409)."""

    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(code="CONFLICT", message=message, status_code=409)


class ValidationError(AppError):
    """Input validation failure (422)."""

    def __init__(self, message: str = "Validation error", field: str | None = None) -> None:
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=422)
        self.field = field


class RateLimitError(AppError):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
    ) -> None:
        super().__init__(code="RATE_LIMIT_EXCEEDED", message=message, status_code=429)
        self.retry_after = retry_after


class LockedError(AppError):
    """Account locked (423)."""

    def __init__(
        self,
        message: str = "Account temporarily locked",
        retry_after: int = 900,
    ) -> None:
        super().__init__(code="ACCOUNT_LOCKED", message=message, status_code=423)
        self.retry_after = retry_after


class UpstreamError(AppError):
    """External service failure (502)."""

    def __init__(self, message: str = "Upstream service error") -> None:
        super().__init__(code="UPSTREAM_ERROR", message=message, status_code=502)


class NotImplementedFeatureError(AppError):
    """A route stub that exists in the skeleton but has not been implemented yet.

    Feature agents must REPLACE every route raising this with real logic.
    Returning 501 lets clients distinguish "endpoint reserved, coming soon"
    from generic 404s while keeping the contract stable.
    """

    def __init__(self, message: str = "Not implemented") -> None:
        super().__init__(code="NOT_IMPLEMENTED", message=message, status_code=501)


class InvalidURLError(AppError):
    """URL is not valid (400)."""

    def __init__(self, message: str = "URL is not valid", suggestion: str | None = None) -> None:
        super().__init__(code="INVALID_URL", message=message, status_code=400)
        self.suggestion = suggestion


class SpecParseError(AppError):
    """Failed to parse OpenAPI spec (422)."""

    def __init__(
        self,
        message: str = "Failed to parse spec",
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(code="SPEC_PARSE_ERROR", message=message, status_code=422)
        self.line = line
        self.column = column


class SpecValidationError(AppError):
    """OpenAPI spec validation failure (422)."""

    def __init__(
        self,
        message: str = "Spec validation failed",
        details: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(code="SPEC_VALIDATION_ERROR", message=message, status_code=422)
        self.details = details or []


class SpecTooLargeError(AppError):
    """OpenAPI spec exceeds size limit (413)."""

    def __init__(self, message: str = "Spec exceeds maximum allowed size") -> None:
        super().__init__(code="SPEC_TOO_LARGE", message=message, status_code=413)


class FetchTimeoutError(AppError):
    """Timeout while fetching OpenAPI spec (504)."""

    def __init__(self, message: str = "Timeout while fetching spec") -> None:
        super().__init__(code="FETCH_TIMEOUT", message=message, status_code=504)


class UnsupportedSpecVersionError(AppError):
    """Unsupported OpenAPI spec version (422)."""

    def __init__(
        self,
        message: str = "Unsupported OpenAPI version",
        suggestion: str | None = None,
    ) -> None:
        super().__init__(code="UNSUPPORTED_SPEC_VERSION", message=message, status_code=422)
        self.suggestion = suggestion


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError subclasses."""
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitError | LockedError):
        headers["Retry-After"] = str(exc.retry_after)

    error_content: dict[str, str | int | list[dict[str, str]]] = {
        "code": exc.code,
        "message": exc.message,
    }

    suggestion = getattr(exc, "suggestion", None)
    if suggestion is not None:
        error_content["suggestion"] = suggestion

    details = getattr(exc, "details", None)
    if details:
        error_content["details"] = details

    line = getattr(exc, "line", None)
    if line is not None:
        error_content["line"] = line

    column = getattr(exc, "column", None)
    if column is not None:
        error_content["column"] = column

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_content},
        headers=headers or None,
    )


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard FastAPI HTTPException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
            }
        },
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any unhandled exception (500)."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )
