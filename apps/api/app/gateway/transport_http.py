"""StreamableHTTP transport for the MCP protocol (spec v2025-04-05).

Handles POST and GET requests to ``/mcp/v1/{slug}/`` for the StreamableHTTP
transport.  POST carries JSON-RPC request/response pairs; GET returns an
SSE heartbeat stream for server-initiated messages.

For v1.0, all responses are sent as complete JSON-RPC responses
(non-streaming).  Session tracking uses the ``MCP-Session-Id`` header.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request, Response
from redis.asyncio import Redis as AsyncRedis
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.redis import get_redis_pool
from app.gateway.session import MCPSession
from app.gateway.transport_sse import route_mcp_request, session_manager
from app.schemas.mcp_protocol import JSONRPCRequest
from app.services.server_config_cache import ServerConfigCache

logger = get_logger(__name__)


async def handle_http_request(
    slug: str,
    body: dict[str, Any] | None = None,
    request: Request | None = None,
) -> Response:
    """Handle a StreamableHTTP request.

    For ``GET`` requests an SSE event stream is returned with periodic
    heartbeats.  For ``POST`` requests the JSON-RPC body is routed through
    :func:`~app.gateway.transport_sse.route_mcp_request`.

    Args:
        slug: The MCP server slug identifying the target server config.
        body: The parsed JSON-RPC request body.  If ``None`` and a
            *request* is provided, the body is read from the request.
        request: Optional FastAPI ``Request`` used to read the body,
            extract the ``MCP-Session-Id`` header, and detect the HTTP
            method.

    Returns:
        A FastAPI ``Response`` — either a JSON-RPC response, a 202
        Accepted for notifications, or an ``EventSourceResponse`` for
        GET requests.

    Raises:
        NotFoundError: If no server exists for *slug* or the server
            status is not ``"active"``.
    """
    # ── GET → SSE heartbeat stream ────────────────────────────────────
    if request is not None and request.method == "GET":

        async def _heartbeat() -> AsyncGenerator[dict[str, str], None]:
            try:
                while True:
                    yield {"event": "heartbeat", "data": ""}
                    await asyncio.sleep(30)
            except asyncio.CancelledError:
                pass

        return EventSourceResponse(
            _heartbeat(),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── POST → JSON-RPC ───────────────────────────────────────────────
    if body is None and request is not None:
        body = await request.json()
    if body is None:
        body = {}

    # Resolve server configuration.
    pool = await get_redis_pool()
    redis = AsyncRedis.from_pool(pool)
    try:
        server_config = await ServerConfigCache.get(slug, redis)
    finally:
        await redis.close()

    if server_config is None:
        raise NotFoundError(f"Server '{slug}' not found")
    if server_config.get("status") != "active":
        raise NotFoundError(
            f"Server '{slug}' is not active (status: {server_config.get('status')})"
        )

    # ── Session management ────────────────────────────────────────────
    session_id: str | None = None
    if request is not None:
        session_id = request.headers.get("MCP-Session-Id")
    if session_id is None:
        session_id = str(uuid.uuid4())

    session = await session_manager.get(session_id)
    if session is None:
        session = MCPSession(
            session_id=session_id,
            server_id=server_config["server_id"],
            user_id=server_config["user_id"],
            slug=slug,
        )
        await session_manager.add(session)

    # ── Parse JSON-RPC request body ──────────────────────────────────
    try:
        request_obj = JSONRPCRequest(
            jsonrpc=body.get("jsonrpc", "2.0"),
            id=body.get("id", 1),
            method=body.get("method", ""),
            params=body.get("params"),
        )
    except Exception:
        logger.warning("invalid_jsonrpc_request", session_id=session_id)
        return Response(
            content=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Invalid JSON-RPC request",
                    },
                }
            ),
            media_type="application/json",
            headers={"MCP-Session-Id": session_id},
        )

    # ── Route and respond ─────────────────────────────────────────────
    response = await route_mcp_request(server_config, session, request_obj)

    headers = {"MCP-Session-Id": session_id}

    if response is None:
        # Notification → 202 Accepted with no body
        return Response(status_code=202, headers=headers)

    return Response(
        content=json.dumps(response),
        media_type="application/json",
        headers=headers,
    )
