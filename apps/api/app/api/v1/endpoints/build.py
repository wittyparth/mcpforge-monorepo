"""Build pipeline endpoints (F1 + F2) — SSE stream for build progress."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AIDescriptionError, ForbiddenError, NotFoundError, NotImplementedFeatureError
from app.core.logging import get_logger
from app.core.sse import sse_manager
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.repositories.mcp_server_repo import MCPServerRepository
from app.schemas.ai_description import AIEnhancementResponse, BuildEvent, ToolAcceptRequest
from app.services.server_builder import ServerBuilder

logger = get_logger(__name__)

router = APIRouter(prefix="/servers/{server_id}", tags=["build"])


@router.post("/build", response_model=AIEnhancementResponse, status_code=200)
async def start_build(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIEnhancementResponse:
    """Start a build — runs the AI enhancement pipeline via ServerBuilder."""
    repo = MCPServerRepository(session)
    server = await repo.get_by_id(server_id)
    if not server:
        raise NotFoundError("Server not found")
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")

    builder = ServerBuilder(repo)
    estimated_cost = await builder.estimate_cost(server_id)
    response = builder.start_build(server_id, current_user.id)

    # Mark server as building
    await repo.update(server, status="building")
    await session.commit()

    logger.info(
        "build_started",
        server_id=str(server_id),
        user_id=str(current_user.id),
        estimated_cost_cents=estimated_cost,
    )

    return AIEnhancementResponse(
        job_id=response.job_id,
        estimated_cost_cents=estimated_cost,
        estimated_duration_seconds=response.estimated_duration_seconds,
        remaining_credits=response.remaining_credits,
    )


@router.get("/build-status")
async def build_status_sse(
    server_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    close_after_first: bool = False,
) -> StreamingResponse:
    """SSE stream of build events — real-time AI enhancement progress.

    Args:
        close_after_first: When ``True``, the stream emits only the
            initial ``connected`` event then closes. Used by integration
            tests to avoid hanging on the production heartbeat loop.
    """
    repo = MCPServerRepository(session)
    server = await repo.get_by_id(server_id)
    if not server:
        raise NotFoundError("Server not found")
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")

    async def event_generator() -> AsyncGenerator[str, None]:
        queue = await sse_manager.subscribe(str(server_id))
        try:
            # Send initial connected event
            connected = json.dumps({
                "event": "connected",
                "server_id": str(server_id),
            })
            yield f"event: connected\ndata: {connected}\n\n"

            if close_after_first:
                return

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    parsed = json.loads(data)
                    event_type = parsed.get("event", "message")
                    yield f"event: {event_type}\ndata: {data}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        except Exception:
            logger.exception(
                "sse_event_generator_error",
                server_id=str(server_id),
            )
        finally:
            await sse_manager.unsubscribe(str(server_id), queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/tools/accept")
async def accept_ai_enhancements(
    server_id: UUID,
    body: ToolAcceptRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Accept AI-proposed tool description enhancements."""
    repo = MCPServerRepository(session)
    server = await repo.get_by_id(server_id)
    if not server:
        raise NotFoundError("Server not found")
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")

    tools_config = server.tools_config
    tools: list[dict[str, Any]] = tools_config.get("tools", [])
    accepted_names = body.accepted_tools
    rejected_names = body.rejected_tools
    custom_edits: dict[str, dict[str, Any]] = body.custom_edits or {}

    for tool in tools:
        name = tool.get("name", "")

        # Apply custom edits first (overrides everything)
        if name in custom_edits:
            tool.update(custom_edits[name])

        # Accept AI enhancements for this tool
        if name in accepted_names:
            if tool.get("enhanced_description"):
                tool["description"] = tool["enhanced_description"]
            if tool.get("enhanced_name"):
                tool["name"] = tool["enhanced_name"]
            # Strip AI metadata fields after merging
            for key in (
                "enhanced_name",
                "enhanced_description",
                "enhanced_parameters",
                "enhanced_return_description",
                "quality_score",
                "improvements_made",
                "enhanced_by",
                "enhanced_at",
            ):
                tool.pop(key, None)

    # Restore rejected tools from pre-enhancement snapshot
    if rejected_names and server.original_tools_config:
        orig_tools: list[dict[str, Any]] = server.original_tools_config.get("tools", [])
        orig_by_name: dict[str, dict[str, Any]] = {
            t["name"]: t for t in orig_tools if t.get("name")
        }
        for tool in tools:
            name = tool.get("name", "")
            if name in rejected_names and name in orig_by_name:
                tool.clear()
                tool.update(orig_by_name[name])

    # Use a raw UPDATE to bypass SQLAlchemy's JSON mutation tracking
    await session.execute(
        update(MCPServer)
        .where(MCPServer.id == server_id)
        .values(
            tools_config=tools_config,
            description_review_status="accepted",
        )
    )
    await session.commit()

    logger.info(
        "enhancements_accepted",
        server_id=str(server_id),
        accepted=len(accepted_names),
        rejected=len(rejected_names),
    )

    return {
        "status": "accepted",
        "server_id": str(server_id),
        "tools_updated": len(accepted_names),
    }


@router.post("/deploy", response_model=dict[str, Any])
async def deploy_server(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Deploy the server (triggers security scan first)."""
    from app.repositories.security_repo import SecurityAckRepository, SecurityScanRepository
    from app.services.security_scanner.scanner import SecurityScanner

    repo = MCPServerRepository(session)
    server = await repo.get_by_id(server_id)
    if not server:
        raise NotFoundError("Server not found")
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")

    # Run security scan synchronously
    scanner = SecurityScanner(session)
    scan_result = await scanner.scan(server_id)
    # Persist scan result before checking — even if deploy is blocked,
    # the user should be able to view the findings via GET /security/latest.
    await session.commit()

    # Block deploy if CRITICAL findings
    if scan_result.critical_count > 0:
        critical_findings = [f for f in scan_result.findings if f.get("severity") == "critical"]
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Security scan found CRITICAL findings. Resolve them before deploying.",
                "code": "BLOCKED_BY_SCANNER",
                "critical_findings": critical_findings,
            },
        )

    # Proceed with deploy (mark as active)
    await repo.update(server, status="active")
    await session.commit()

    logger.info(
        "server_deployed",
        server_id=str(server_id),
        user_id=str(current_user.id),
    )

    return {"status": "deployed", "server_id": str(server_id)}
