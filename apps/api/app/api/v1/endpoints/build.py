"""Build pipeline endpoints (F1 + F2) — route stubs.

Includes the SSE stream for build progress.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenError, NotImplementedFeatureError
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.mcp_server import MCPServerResponse
from app.services.mcp_server_service import MCPServerService

logger = get_logger(__name__)

router = APIRouter(prefix="/servers/{server_id}", tags=["build"])


@router.post("/build", response_model=MCPServerResponse, status_code=200)
async def start_build(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """Start a build (F1 minimal: marks server active)."""
    svc = MCPServerService(session)
    server = await svc.get_server(server_id)
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")
    updated = await svc.update_server(
        server_id=server_id,
        user_id=current_user.id,
        status="active",
    )
    logger.info("build_started", server_id=str(server_id), user_id=str(current_user.id))
    return MCPServerResponse.model_validate(updated)


@router.get("/build-status")
async def build_status_sse(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE stream of build events (F1 minimal: single event then close)."""
    svc = MCPServerService(session)
    server = await svc.get_server(server_id)
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")

    async def event_generator() -> AsyncGenerator[str, None]:
        payload = json.dumps({"stage": "parsing", "progress": 100, "message": "Parsing complete"})
        yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/tools/accept", status_code=501)
async def accept_ai_enhancements(server_id: UUID) -> None:
    """Accept the AI's proposed descriptions. Pending F2."""
    raise NotImplementedFeatureError("AI Engine: pending F2")


@router.post("/deploy", status_code=501)
async def deploy_server(server_id: UUID) -> None:
    """Deploy the server (triggers security scan first). Pending F4 + F5."""
    raise NotImplementedFeatureError("Deploy: pending F4 + F5")
