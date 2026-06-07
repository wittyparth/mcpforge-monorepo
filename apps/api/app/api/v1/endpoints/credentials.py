"""Credential management endpoints (F1 + F4) — route stubs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/servers/{server_id}/credentials", tags=["credentials"])


@router.get("", status_code=501)
async def list_credentials(server_id: UUID) -> None:
    """List credentials for a server (NEVER returns values). Pending F1."""
    raise NotImplementedFeatureError("Credentials: pending F1")


@router.post("", status_code=501)
async def add_credential(server_id: UUID) -> None:
    """Add or update a credential (encrypted at rest). Pending F1."""
    raise NotImplementedFeatureError("Credentials: pending F1")


@router.post("/test", status_code=501)
async def test_credential(server_id: UUID) -> None:
    """Dry-run a request using the stored credential. Pending F1 + F4."""
    raise NotImplementedFeatureError("Credentials: pending F1 + F4")


@router.delete("/{env_var_name}", status_code=501)
async def delete_credential(server_id: UUID, env_var_name: str) -> None:
    """Delete a credential. Pending F1."""
    raise NotImplementedFeatureError("Credentials: pending F1")
