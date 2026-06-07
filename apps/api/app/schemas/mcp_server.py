"""Pydantic schemas for MCPServer model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MCPServerCreate(BaseModel):
    """Request body for creating a new MCP server."""

    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
        description="Lowercase alphanumeric with hyphens, 3-50 chars",
    )
    description: str | None = Field(None, max_length=2000)
    base_url: str = Field(..., max_length=500)
    spec_url: str | None = Field(None, max_length=1000)
    auth_scheme: str = Field(default="none", pattern=r"^(none|api_key|bearer|basic|oauth2)$")
    auth_header_name: str | None = Field(None, max_length=100)
    tools_config: dict[str, Any] = Field(default_factory=dict)
    transport_mode: str = Field(default="sse", pattern=r"^(sse|streamable_http|both)$")


class MCPServerUpdate(BaseModel):
    """Request body for updating an MCP server."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    base_url: str | None = Field(None, max_length=500)
    auth_scheme: str | None = Field(
        None, pattern=r"^(none|api_key|bearer|basic|oauth2)$"
    )
    auth_header_name: str | None = Field(None, max_length=100)
    tools_config: dict[str, Any] | None = None
    transport_mode: str | None = Field(
        None, pattern=r"^(sse|streamable_http|both)$"
    )
    status: str | None = Field(
        None, pattern=r"^(building|active|paused|error)$"
    )


class ToolSelectionRequest(BaseModel):
    """Request body for POST /specs/{spec_id}/select-tools."""

    slug: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
        description="Lowercase alphanumeric with hyphens, 3-50 chars",
    )
    name: str = Field(..., min_length=1, max_length=200)
    base_url: str = Field(..., max_length=500)
    description: str | None = Field(None, max_length=2000)
    auth_scheme: str = Field(
        default="none",
        pattern=r"^(none|api_key|bearer|basic|oauth2)$",
    )
    auth_header_name: str | None = Field(None, max_length=100)
    selected_tool_names: list[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Names of tools the user selected to include",
    )
    customizations: dict[str, dict[str, Any]] | None = None
    transport_mode: str = Field(
        default="sse",
        pattern=r"^(sse|streamable_http|both)$",
    )


class MCPServerResponse(BaseModel):
    """Public MCP server response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    slug: str
    name: str
    description: str | None = None
    status: str = "building"
    spec_url: str | None = None
    base_url: str
    auth_scheme: str = "none"
    transport_mode: str = "sse"
    tools_config: dict[str, Any]
    total_calls: int = 0
    monthly_calls: int = 0
    last_call_at: datetime | None = None
    version: int = 1
    created_at: datetime
    updated_at: datetime | None = None


class ToolListResponse(BaseModel):
    """Response for GET /api/v1/servers/{id}/tools."""

    server_id: UUID
    tool_count: int
    tools: list[dict[str, Any]]


class ToolUpdateRequest(BaseModel):
    """Request body for PATCH /api/v1/servers/{id}/tools/{tool_name}.

    All fields are optional. Only non-None values are applied.
    """

    description: str | None = Field(None, min_length=1, max_length=2000)
    enabled: bool | None = None
    name: str | None = Field(
        None, min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$"
    )
