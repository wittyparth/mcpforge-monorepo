"""Pydantic schemas for the browser MCP Playground (F3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlaygroundSessionInfo(BaseModel):
    """Session info returned when a browser playground connection is established."""

    session_id: str
    server_id: UUID
    slug: str
    transport: Literal["websocket"]
    endpoint: str
    expires_at: datetime


class PlaygroundShareTestRequest(BaseModel):
    """POST /api/v1/servers/{id}/playground/share — create a shareable test link."""

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class PlaygroundShareTestResponse(BaseModel):
    """Response for a shareable test link."""

    share_id: str
    url: str
    expires_at: datetime
