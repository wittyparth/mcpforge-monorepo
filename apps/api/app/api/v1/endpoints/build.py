"""Build pipeline endpoints (F1 + F2) — route stubs.

Includes the SSE stream for build progress.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/servers/{server_id}", tags=["build"])


@router.post("/build", status_code=501)
async def start_build(server_id: UUID) -> None:
    """Start a build (AI enhancement + deploy prep). Pending F1 + F2."""
    raise NotImplementedFeatureError("Build pipeline: pending F1 + F2")


@router.get("/build-status", status_code=501)
async def build_status_sse(server_id: UUID) -> None:
    """SSE stream of build events. Pending F2."""
    raise NotImplementedFeatureError("Build pipeline: pending F2")


@router.post("/tools/accept", status_code=501)
async def accept_ai_enhancements(server_id: UUID) -> None:
    """Accept the AI's proposed descriptions. Pending F2."""
    raise NotImplementedFeatureError("AI Engine: pending F2")


@router.post("/deploy", status_code=501)
async def deploy_server(server_id: UUID) -> None:
    """Deploy the server (triggers security scan first). Pending F4 + F5."""
    raise NotImplementedFeatureError("Deploy: pending F4 + F5")
