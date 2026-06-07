"""Common Pydantic schemas shared across endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response from the root health check endpoint."""

    status: str = "ok"
    version: str = "0.1.0"
    db: str = "ok"
    redis: str = "ok"
    worker: str = "down"  # ok | down — Celery worker liveness


class APIHealthResponse(BaseModel):
    """Response from the API v1 health check."""

    status: str = "ok"
    version: str = "0.1.0"
    environment: str = "development"


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    """Structured error response."""

    error: ErrorDetail


class ErrorDetail(BaseModel):
    code: str
    message: str


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""

    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20


class TimestampSchema(BaseModel):
    """Shared timestamp fields for response schemas."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime | None = None
