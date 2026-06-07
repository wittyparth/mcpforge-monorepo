"""Credential management endpoints (F1 + F4) — real implementations."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.credential import (
    CredentialCreateRequest,
    CredentialListResponse,
    CredentialResponse,
    CredentialTestRequest,
    CredentialTestResponse,
)
from app.services.credential_service import CredentialService

logger = get_logger(__name__)

router = APIRouter(prefix="/servers/{server_id}/credentials", tags=["credentials"])


@router.get("", response_model=CredentialListResponse)
async def list_credentials(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CredentialListResponse:
    """List all credentials for a server (never returns values)."""
    svc = CredentialService(session)
    creds = await svc.list_credentials(server_id=server_id, user_id=current_user.id)
    logger.info(
        "credentials_listed",
        server_id=str(server_id),
        user_id=str(current_user.id),
        count=len(creds),
    )
    return CredentialListResponse(
        server_id=server_id,
        credentials=[CredentialResponse.model_validate(c) for c in creds],
        total=len(creds),
    )


@router.post("", response_model=CredentialResponse, status_code=201)
async def add_credential(
    server_id: UUID,
    body: CredentialCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CredentialResponse:
    """Add a credential for a server (encrypted at rest)."""
    svc = CredentialService(session)
    credential = await svc.add_credential(
        server_id=server_id,
        user_id=current_user.id,
        env_var_name=body.env_var_name,
        value=body.value,
        auth_scheme=body.auth_scheme,
        auth_header_name=body.auth_header_name,
    )
    logger.info(
        "credential_added",
        server_id=str(server_id),
        env_var_name=body.env_var_name,
        user_id=str(current_user.id),
    )
    return CredentialResponse.model_validate(credential)


@router.post("/test", response_model=CredentialTestResponse)
async def test_credential(
    server_id: UUID,
    body: CredentialTestRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CredentialTestResponse:
    """Dry-run a request using the stored credential."""
    svc = CredentialService(session)
    result = await svc.test_credential(
        server_id=server_id,
        user_id=current_user.id,
        env_var_name=body.env_var_name,
        test_value=body.test_value,
    )
    logger.info(
        "credential_tested",
        server_id=str(server_id),
        env_var_name=body.env_var_name,
        user_id=str(current_user.id),
        success=result.success,
    )
    return result


@router.delete("/{env_var_name}", status_code=204, response_model=None)
async def delete_credential(
    server_id: UUID,
    env_var_name: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a credential."""
    svc = CredentialService(session)
    await svc.delete_credential(
        server_id=server_id,
        env_var_name=env_var_name,
        user_id=current_user.id,
    )
    logger.info(
        "credential_deleted",
        server_id=str(server_id),
        env_var_name=env_var_name,
        user_id=str(current_user.id),
    )
