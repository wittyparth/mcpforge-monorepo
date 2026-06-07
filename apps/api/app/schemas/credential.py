"""Pydantic schemas for the credential encryption flow (F1/F4)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CredentialCreateRequest(BaseModel):
    """Request body for POST /api/v1/servers/{id}/credentials."""

    env_var_name: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    value: str = Field(..., min_length=1, max_length=4096)
    auth_scheme: str = Field(default="bearer", pattern=r"^(bearer|api_key|basic|oauth2|header)$")


class CredentialResponse(BaseModel):
    """Response when listing credentials. NEVER returns the value."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    env_var_name: str
    auth_scheme: str
    encryption_key_id: str | None
    rotated_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class CredentialTestRequest(BaseModel):
    """Request body for POST /api/v1/servers/{id}/credentials/test."""

    dry_run: bool = True
    target_url: str | None = None


class CredentialTestResponse(BaseModel):
    """Response for a credential test request."""

    success: bool
    status_code: int | None
    latency_ms: int | None
    error: str | None = None
