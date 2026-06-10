"""Gateway admin endpoints — user-facing gateway management.

These endpoints allow users to connect to, test, pause, resume, and
manage their MCP servers. The *protocol-bearing* gateway routes (SSE,
message, StreamableHTTP) live in ``app.gateway.mcp_server``.
"""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.models.user import User as UserModel
from app.schemas.gateway import (
    ConnectPanelResponse,
    PauseResponse,
    TestConnectionResponse,
)
from app.services.mcp_server_service import MCPServerService

logger = get_logger(__name__)

router = APIRouter(prefix="/servers/{server_id}", tags=["gateway"])


@router.get("/connect", response_model=ConnectPanelResponse)
async def connect_panel(
    server_id: UUID,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConnectPanelResponse:
    """Get connection details for the gateway.

    Returns URLs and copy-ready config snippets for Claude Desktop and
    Cursor so the user can plug their MCP server into any MCP host.
    """
    svc = MCPServerService(session)
    server = await svc.get_server(server_id)

    # Verify ownership
    if server.user_id != current_user.id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("You do not own this server")

    slug = server.slug
    gateway_base = str(request.base_url).rstrip("/")
    gateway_url = f"{gateway_base}/mcp/v1/{slug}/"
    endpoint_url = f"{gateway_base}/mcp/v1/{slug}/sse"
    test_endpoint = f"/api/v1/servers/{server_id}/connect/test"

    return ConnectPanelResponse(
        server_slug=slug,
        gateway_url=gateway_url,
        transport_modes=["sse", "streamable_http"],
        claude_desktop_config={
            "mcpServers": {
                server.name: {
                    "url": endpoint_url,
                }
            }
        },
        cursor_config={
            "mcpServers": {
                server.name: {
                    "url": gateway_url,
                }
            }
        },
        test_connection_endpoint=test_endpoint,
    )


@router.post("/connect/test", response_model=TestConnectionResponse)
async def test_connection(
    server_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TestConnectionResponse:
    """Dry-run a connectivity check against the upstream server.

    Attempts an HTTP GET to the server's ``base_url`` to verify the
    upstream is reachable and measure round-trip latency. This is a
    lightweight connectivity test — the full MCP ``tools/list``
    handshake requires the gateway pipeline (Phase 2).
    """
    import time

    svc = MCPServerService(session)
    server = await svc.get_server(server_id)

    # Verify ownership
    if server.user_id != current_user.id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("You do not own this server")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(server.base_url)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code < 500:
                return TestConnectionResponse(
                    success=True,
                    response_time_ms=elapsed_ms,
                    tools_count=None,
                    error=None,
                )
            return TestConnectionResponse(
                success=False,
                response_time_ms=elapsed_ms,
                tools_count=None,
                error=f"Upstream returned HTTP {resp.status_code}",
            )
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return TestConnectionResponse(
            success=False,
            response_time_ms=elapsed_ms,
            tools_count=None,
            error="Connection timed out",
        )
    except httpx.RequestError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return TestConnectionResponse(
            success=False,
            response_time_ms=elapsed_ms,
            tools_count=None,
            error=f"Connection failed: {exc.__class__.__name__}",
        )


@router.post("/pause", response_model=PauseResponse)
async def pause_server(
    server_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PauseResponse:
    """Pause a server — stop accepting requests but retain config.

    The paused server will appear as ``paused`` in the dashboard and
    the gateway will reject incoming MCP requests until the server is
    resumed.
    """
    svc = MCPServerService(session)
    server = await svc.update_server(
        server_id,
        current_user.id,
        status="paused",
    )

    # Best-effort cache invalidation
    try:
        from redis.asyncio import Redis

        from app.core.redis import get_redis_pool
        from app.services.server_config_cache import ServerConfigCache

        pool = await get_redis_pool()
        redis = Redis.from_pool(pool)
        await ServerConfigCache.invalidate(server.slug, redis)
        await redis.close()
    except Exception:
        logger.warning("cache_invalidation_failed", server_id=str(server_id))

    return PauseResponse(
        server_id=server.id,
        status="paused",
        paused_at=None,
        estimated_propagation_seconds=5,
    )


@router.post("/resume", response_model=PauseResponse)
async def resume_server(
    server_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PauseResponse:
    """Resume a paused server — re-enable MCP requests.

    Restores the server to ``active`` status so the gateway once again
    accepts incoming MCP requests.
    """
    svc = MCPServerService(session)
    server = await svc.update_server(
        server_id,
        current_user.id,
        status="active",
    )

    # Best-effort cache invalidation
    try:
        from redis.asyncio import Redis

        from app.core.redis import get_redis_pool
        from app.services.server_config_cache import ServerConfigCache

        pool = await get_redis_pool()
        redis = Redis.from_pool(pool)
        await ServerConfigCache.invalidate(server.slug, redis)
        await redis.close()
    except Exception:
        logger.warning("cache_invalidation_failed", server_id=str(server_id))

    return PauseResponse(
        server_id=server.id,
        status="active",
        paused_at=None,
        estimated_propagation_seconds=5,
    )


