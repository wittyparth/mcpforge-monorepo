"""Pydantic schemas for the MCP Gateway admin endpoints (F4)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectPanelResponse(BaseModel):
    """GET /api/v1/servers/{id}/connect — connection details for the gateway."""

    server_id: UUID
    slug: str
    transport: Literal["sse", "streamable_http"]
    sse_endpoint: str
    http_endpoint: str
    auth_required: bool
    auth_methods: list[Literal["jwt_cookie", "bearer_header", "api_key"]] = Field(default_factory=list)
    example_client_config: dict[str, str] = Field(default_factory=dict)


class TestConnectionRequest(BaseModel):
    """POST /api/v1/servers/{id}/test-connection — dry-run a tool call."""

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class TestConnectionResponse(BaseModel):
    """Result of a dry-run tool call."""

    success: bool
    status_code: int | None
    latency_ms: int
    response_excerpt: str | None = Field(default=None, description="First 1KB of response, or error message")
    error: str | None = None


class DeployRequest(BaseModel):
    """POST /api/v1/servers/{id}/deploy — deploy the server (triggers security scan first)."""

    run_security_scan: bool = Field(default=True)
    block_on_critical: bool = Field(default=True)


class DeployResponse(BaseModel):
    """Response from a deploy request."""

    server_id: UUID
    status: Literal["deploying", "active", "paused", "scan_failed", "error"]
    message: str
    scan_id: UUID | None = None
    deployed_at: datetime | None = None


class PauseResponse(BaseModel):
    """Response from POST /api/v1/servers/{id}/pause and /resume."""

    server_id: UUID
    status: str
    paused_at: datetime | None = None
    resumed_at: datetime | None = None
