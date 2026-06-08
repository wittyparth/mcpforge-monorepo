"""Pydantic schemas for the MCP Gateway admin endpoints (F4).

These are the request/response models used by the gateway management REST
endpoints — not the MCP protocol messages themselves (see
``mcp_protocol.py`` for those).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectPanelResponse(BaseModel):
    """GET /api/v1/servers/{id}/connect — connection details for the gateway.

    Returned when a user views the "Connect" panel for their deployed MCP
    server.  Includes copy-ready config snippets for Claude Desktop and
    Cursor.
    """

    server_slug: str
    """URL-safe slug that identifies this server in the gateway."""

    gateway_url: str
    """Base URL of the MCP gateway (e.g. ``https://mcpforge-api.example.com``)."""

    transport_modes: list[Literal["sse", "streamable_http", "both"]] = Field(
        default_factory=lambda: ["sse", "streamable_http"]
    )
    """Supported transport modes for this server."""

    claude_desktop_config: dict[str, Any] = Field(default_factory=dict)
    """Pre-built JSON snippet ready to paste into Claude Desktop's config file."""

    cursor_config: dict[str, Any] = Field(default_factory=dict)
    """Pre-built JSON snippet ready to paste into Cursor's MCP settings."""

    test_connection_endpoint: str
    """URL of the test-connection endpoint for quick verification."""


class TestConnectionResponse(BaseModel):
    """POST /api/v1/servers/{id}/test-connection — result of a dry-run call.

    Unlike the credential test (which tests auth), this tests the full
    MCP tool invocation pipeline from gateway through upstream.
    """

    success: bool
    """Whether the test tool call completed without error."""

    response_time_ms: int
    """Round-trip time in milliseconds for the test call."""

    tools_count: int | None = None
    """Number of tools the server reported (available after a ``tools/list``)."""

    error: str | None = None
    """Human-readable error message when ``success`` is ``False``."""


class DeployRequest(BaseModel):
    """POST /api/v1/servers/{id}/deploy — deploy the server.

    The deploy pipeline fetches the OpenAPI spec, generates tools, runs
    a security scan (unless skipped), and activates the gateway.
    """

    skip_security_scan: bool = Field(
        default=False,
        description="If True, skip the security scan and deploy immediately",
    )


class PauseResponse(BaseModel):
    """Response from POST /api/v1/servers/{id}/pause and /resume."""

    model_config = ConfigDict(from_attributes=True)

    server_id: UUID
    """The server that was paused or resumed."""

    status: Literal["paused", "active"]
    """Current status of the server after the operation."""

    paused_at: datetime | None = None
    """When the server was paused (``None`` if the server is active)."""

    estimated_propagation_seconds: int = Field(
        default=5,
        description="Estimated time for the status change to propagate through the gateway",
    )
