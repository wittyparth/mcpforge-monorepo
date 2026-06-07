"""Gateway admin endpoints (F4) — route stubs.

These are the *user-facing* gateway management endpoints. The
*protocol-bearing* gateway routes (SSE, message, StreamableHTTP) live
in `app.gateway.mcp_server` and require auth (added in Wave 0).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/servers/{server_id}", tags=["gateway"])


@router.post("/connect", status_code=501)
async def connect_panel(server_id: UUID) -> None:
    """Get connection details for the gateway (URLs, auth methods). Pending F4."""
    raise NotImplementedFeatureError("Gateway: pending F4")


@router.post("/test-connection", status_code=501)
async def test_connection(server_id: UUID) -> None:
    """Dry-run a tool call through the gateway. Pending F4."""
    raise NotImplementedFeatureError("Gateway: pending F4")


@router.post("/pause", status_code=501)
async def pause_server(server_id: UUID) -> None:
    """Pause a server (stops accepting requests, retains config). Pending F4."""
    raise NotImplementedFeatureError("Gateway: pending F4")


@router.post("/resume", status_code=501)
async def resume_server(server_id: UUID) -> None:
    """Resume a paused server. Pending F4."""
    raise NotImplementedFeatureError("Gateway: pending F4")


@router.post("/rollback", status_code=501)
async def rollback_server(server_id: UUID) -> None:
    """Roll back to a previous version. Pending F4."""
    raise NotImplementedFeatureError("Gateway: pending F4")


@router.get("/versions", status_code=501)
async def list_versions(server_id: UUID) -> None:
    """List version history. Pending F4."""
    raise NotImplementedFeatureError("Gateway: pending F4")
