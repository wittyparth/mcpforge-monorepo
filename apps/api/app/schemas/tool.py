"""Pydantic schemas for the tools workspace (F1 + F2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolListItem(BaseModel):
    """A single tool as returned by GET /api/v1/servers/{id}/tools."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    input_schema: dict[str, Any]
    http_method: str
    http_path: str
    quality_score: int | None = Field(
        default=None, description="AI-scored quality (0-100), null if not scored"
    )
    quality_breakdown: dict[str, int] | None = Field(
        default=None, description="4-dimension quality scores"
    )
    enabled: bool = True
    last_enhanced_at: str | None = None


class ToolUpdateRequest(BaseModel):
    """PATCH /api/v1/servers/{id}/tools/{name} — user edits the description."""

    description: str | None = Field(default=None, min_length=1, max_length=2000)
    enabled: bool | None = None
    input_schema: dict[str, Any] | None = None


class ToolBulkUpdateRequest(BaseModel):
    """Body for bulk enable/disable + description changes."""

    updates: list[ToolUpdateRequest] = Field(..., min_length=1, max_length=500)


class ToolListResponse(BaseModel):
    """Response for GET /api/v1/servers/{id}/tools."""

    server_id: UUID
    tools: list[ToolListItem]
    total: int
