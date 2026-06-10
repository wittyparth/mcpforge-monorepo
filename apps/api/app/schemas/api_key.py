"""Pydantic schemas for the API Keys flow (F7)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreateRequest(BaseModel):
    """POST /api/v1/api-keys — create a new API key."""

    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(
        default_factory=lambda: ["servers:read"],
        description="Permission scopes; see PRD § 13 for the full list.",
    )
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    """Response for listing API keys. NEVER returns the plaintext."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response for POST /api/v1/api-keys — includes the plaintext ONCE.

    The plaintext is shown in the UI one time and never again. After
    creation, only `ApiKeyResponse` (no `plaintext_key`) is returned.
    """

    plaintext_key: str = Field(..., description="Shown ONCE at creation. Store securely.")


class ApiKeyListResponse(BaseModel):
    """Response for GET /api/v1/api-keys — list of keys."""

    items: list[ApiKeyResponse]
    total: int
