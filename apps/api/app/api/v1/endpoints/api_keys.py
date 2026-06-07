"""API key management endpoints (F7) — route stubs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", status_code=501)
async def list_api_keys() -> None:
    """List all API keys for the user/team. Pending F7."""
    raise NotImplementedFeatureError("API Keys: pending F7")


@router.post("", status_code=501)
async def create_api_key() -> None:
    """Create a new API key (returns plaintext once). Pending F7."""
    raise NotImplementedFeatureError("API Keys: pending F7")


@router.delete("/{key_id}", status_code=501)
async def revoke_api_key(key_id: UUID) -> None:
    """Revoke an API key. Pending F7."""
    raise NotImplementedFeatureError("API Keys: pending F7")
