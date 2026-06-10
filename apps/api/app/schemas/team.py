"""Pydantic schemas for the Team management flow (F7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

TeamRole = Literal["admin", "editor", "viewer"]


class TeamCreateRequest(BaseModel):
    """POST /api/v1/team — create a new team."""

    name: str = Field(..., min_length=1, max_length=200)


class TeamUpdateRequest(BaseModel):
    """PATCH /api/v1/team — update team name."""

    name: str = Field(..., min_length=1, max_length=200)


class TeamResponse(BaseModel):
    """Team representation.

    ``member_count`` and ``current_user_role`` are populated by the
    service layer — they are not stored directly on the Team model.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    plan: str
    member_count: int = 0
    current_user_role: TeamRole | None = None
    created_at: datetime


class TeamInviteRequest(BaseModel):
    """POST /api/v1/team/invite — invite a user by email."""

    email: EmailStr
    role: TeamRole = "editor"


class TeamInvitationResponse(BaseModel):
    """A team invitation.

    The ``token`` field is only included in the creation response;
    subsequent GET responses MUST exclude it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: TeamRole
    token: str | None = None
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime


class TeamAcceptRequest(BaseModel):
    """POST /api/v1/team/accept — accept an invitation by token."""

    token: str = Field(..., min_length=1)


class TeamMemberResponse(BaseModel):
    """A single team member."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    role: TeamRole
    joined_at: datetime


class TeamMemberUpdateRequest(BaseModel):
    """PATCH /api/v1/team/members/{user_id} — change role."""

    role: TeamRole


class AuditLogResponse(BaseModel):
    """A single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    user_email: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: UUID | None = None
    metadata: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class PaginatedAuditLogResponse(BaseModel):
    """Paginated audit log response."""

    items: list[AuditLogResponse]
    total: int
    skip: int
    limit: int
