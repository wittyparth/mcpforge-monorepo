"""Pydantic schemas for User model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    """Public user profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    plan: str = "free"
    ai_enhancement_credits: int = 3
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class UserUpdateRequest(BaseModel):
    """Request body for updating user profile."""

    display_name: str | None = Field(None, max_length=100)
    avatar_url: str | None = Field(None, max_length=500)
