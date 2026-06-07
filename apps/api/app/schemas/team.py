"""Pydantic schemas for the Team management flow (F7)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TeamCreateRequest(BaseModel):
    """POST /api/v1/team — create a new team."""

    name: str = Field(..., min_length=1, max_length=200)


class TeamResponse(BaseModel):
    """Team representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    plan: str
    member_count: int = 0
    created_at: datetime


class TeamInviteRequest(BaseModel):
    """POST /api/v1/team/invite — invite a user by email."""

    email: EmailStr
    role: Literal["admin", "editor", "viewer"] = "editor"


class TeamMemberResponse(BaseModel):
    """A single team member."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    display_name: str | None
    role: Literal["admin", "editor", "viewer"]
    joined_at: datetime
    last_active_at: datetime | None = None


class TeamMemberUpdateRequest(BaseModel):
    """PATCH /api/v1/team/members/{user_id} — change role."""

    role: Literal["admin", "editor", "viewer"]


class AuditLogItem(BaseModel):
    """A single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: UUID | None
    ip_address: str | None
    created_at: datetime
