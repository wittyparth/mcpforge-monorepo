"""API key management endpoints (F7 — programmatic access)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from app.services.api_key_service import ApiKeyService

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("")
async def list_api_keys(
    request: Request,
    include_revoked: bool = False,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyListResponse:
    """List all API keys for the current user."""
    service = ApiKeyService(session)
    keys = await service.repo.list_for_user(
        user_id=current_user.id,
        include_revoked=include_revoked,
    )
    items = [ApiKeyResponse.model_validate(k) for k in keys]
    return ApiKeyListResponse(items=items, total=len(items))


@router.post("", status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyCreatedResponse:
    """Create a new API key. The plaintext key is returned ONCE."""
    service = ApiKeyService(session)
    api_key, plaintext = await service.create_key(
        user_id=current_user.id,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
    )
    return ApiKeyCreatedResponse(
        **ApiKeyResponse.model_validate(api_key).model_dump(),
        plaintext_key=plaintext,
    )


@router.delete("/{key_id}", status_code=204, response_model=None)
async def revoke_api_key(
    key_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Revoke an API key. Verifies ownership first."""
    service = ApiKeyService(session)
    await service.revoke_key(key_id=key_id, user_id=current_user.id)
