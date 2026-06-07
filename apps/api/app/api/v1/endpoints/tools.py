"""Tool workspace endpoints (F1 + F2) — route stubs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/servers/{server_id}/tools", tags=["tools"])


@router.get("", status_code=501)
async def list_tools(server_id: UUID) -> None:
    """List all tools for a server (with quality scores). Pending F1 + F2."""
    raise NotImplementedFeatureError("Tools: pending F1 + F2")


@router.patch("/{tool_name}", status_code=501)
async def update_tool(server_id: UUID, tool_name: str) -> None:
    """Update a single tool (description, enabled, schema). Pending F1 + F2."""
    raise NotImplementedFeatureError("Tools: pending F1 + F2")


@router.post("/enhance", status_code=501)
async def enhance_tools(server_id: UUID) -> None:
    """Re-run AI enhancement on the server's tools. Pending F2."""
    raise NotImplementedFeatureError("AI Engine: pending F2")
