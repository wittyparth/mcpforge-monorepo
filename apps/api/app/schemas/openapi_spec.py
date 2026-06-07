"""Pydantic schemas for the OpenAPI spec ingestion flow (F1)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SpecFetchRequest(BaseModel):
    """Request body for POST /api/v1/specs/fetch."""

    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


class SpecUploadResponse(BaseModel):
    """Response for a successful spec upload/fetch."""

    spec_id: UUID
    title: str | None
    version: str | None
    openapi_version: str | None
    endpoint_count: int
    spec_size_bytes: int
    tools: list[ToolDefinition] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    """A single tool extracted from an OpenAPI operation.

    This is the *normalized* shape we feed into the MCP server builder.
    The original OpenAPI operation is stored alongside, accessible via
    `operation_id` for round-tripping.
    """

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Stable tool name, e.g., 'list_users'")
    description: str = Field(..., description="Description for LLM tool selection")
    input_schema: dict[str, Any] = Field(..., description="JSON Schema for tool arguments")
    http_method: str = Field(..., description="GET, POST, PUT, PATCH, DELETE")
    http_path: str = Field(..., description="Path with placeholders, e.g., '/users/{id}'")
    base_url_override: str | None = Field(default=None, description="Override the server base URL for this tool only")
    operation_id: str | None = Field(default=None, description="Original OpenAPI operationId, if any")


class SpecToolListResponse(BaseModel):
    """Response for GET /api/v1/specs/{spec_id}/tools."""

    spec_id: UUID
    tools: list[ToolDefinition]
