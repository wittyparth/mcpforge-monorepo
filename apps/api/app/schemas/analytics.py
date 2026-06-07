"""Pydantic schemas for the Analytics Dashboard (F6)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsOverview(BaseModel):
    """GET /api/v1/servers/{id}/analytics — top-line numbers."""

    server_id: UUID
    range: str = Field(..., description="e.g., '7d', '30d', '90d'")
    total_calls: int
    total_errors: int
    error_rate: float = Field(..., ge=0.0, le=1.0)
    unique_clients: int
    avg_latency_ms: float
    p95_latency_ms: float


class ToolBreakdownItem(BaseModel):
    """A single row in the tool-call breakdown table."""

    model_config = ConfigDict(from_attributes=True)

    tool_name: str
    call_count: int
    error_count: int
    avg_latency_ms: float
    selection_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of sessions that called this tool"
    )


class ErrorLogItem(BaseModel):
    """A single row in the error log."""

    model_config = ConfigDict(from_attributes=True)

    called_at: datetime
    tool_name: str
    error_type: str
    error_msg: str
    client_name: str | None


class TimeSeriesPoint(BaseModel):
    """A single point in the time-series chart."""

    bucket_start: datetime
    call_count: int
    error_count: int
    avg_latency_ms: float | None


class ClientBreakdownItem(BaseModel):
    """A single row in the client breakdown table."""

    client_name: str
    call_count: int
    last_seen: datetime
