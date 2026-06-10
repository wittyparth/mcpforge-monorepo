"""SSE (Server-Sent Events) transport for the MCP protocol.

Handles SSE connections and JSON-RPC message processing for the MCP
gateway.  Uses ``sse-starlette``'s ``EventSourceResponse`` for
standards-compliant SSE streaming.

MCP protocol methods handled
----------------------------
* ``initialize`` — returns server capabilities and protocol version
* ``notifications/initialized`` — no-op notification
* ``ping`` — health check keepalive
* ``tools/list`` — returns the server's available tools
* ``tools/call`` — dispatches a tool invocation with rate limiting
* ``notifications/cancelled`` — no-op notification

Every other method receives a ``method_not_found`` JSON-RPC error.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import Request
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.gateway.analytics_bridge import classify_dispatch_status, emit_tool_call
from app.gateway.errors import (
    method_not_found_error,
    rate_limit_error,
    server_disabled_error,
    tool_not_found_error,
    upstream_error,
)
from app.gateway.rate_limiter import GatewayRateLimiter, RateLimitResult
from app.gateway.session import MCPSession, SessionManager
from app.gateway.tool_dispatcher import ToolDispatcher
from app.schemas.mcp_protocol import JSONRPCRequest, MCPErrorCode
from app.services.credential_service import CredentialService
from app.services.server_config_cache import ServerConfigCache

logger = get_logger(__name__)

session_manager = SessionManager()


@dataclass
class SSESession:
    """Represents an active SSE-based MCP session.

    Attributes:
        session_id: Unique identifier for the session.
        server_id: The UUID of the target MCP server.
        user_id: The UUID of the owning user.
        slug: Server slug (used for routing in gateway URLs).
        initialized: Whether the MCP handshake (initialize) has completed.
        client_name: Optional client-provided name (e.g. "Claude Desktop").
        created_at: When the session was created (UTC).
    """

    session_id: str
    server_id: str
    user_id: str
    slug: str
    initialized: bool = False
    client_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


async def _load_server_config(slug: str) -> dict[str, Any]:
    """Load and return a server configuration by slug.

    Uses ``get_redis`` (an async generator) to obtain a Redis client,
    then fetches the cached config.  The Redis connection is released
    when the generator exits.

    Returns:
        The server configuration dict.

    Raises:
        NotFoundError: If no server exists for the slug or the server
            is not in ``active`` status.
    """
    server_config: dict[str, Any] | None = None
    async for redis in get_redis():
        server_config = await ServerConfigCache.get(slug, redis)
        break

    if server_config is None:
        raise NotFoundError(f"Server '{slug}' not found")

    return server_config


async def handle_sse_connection(
    slug: str,
    request: Request,
    current_user: Any = None,
) -> EventSourceResponse:
    """Handle an incoming SSE connection for an MCP server.

    Implements the MCP-over-SSE lifecycle:
    1. Look up server config from Redis-backed cache.
    2. Verify the server exists and is in ``active`` status.
    3. Create a session and register it with the session manager.
    4. Return an ``EventSourceResponse`` that:
       - Sends an ``endpoint`` event with the message URL and session ID.
       - Maintains the connection with 15-second heartbeat pings.
       - Detects client disconnect and cleans up the session.

    Args:
        slug: The server slug identifying the target MCP server.
        request: The incoming FastAPI ``Request`` (used for disconnect
            detection).
        current_user: The authenticated user (optional -- auth is enforced
            by the route dependency).

    Returns:
        An ``EventSourceResponse`` that streams SSE events to the client.

    Raises:
        NotFoundError: If the server slug does not exist or is not active.
    """
    server_config = await _load_server_config(slug)

    if server_config.get("status") != "active":
        raise NotFoundError(f"Server '{slug}' is not active")

    session_id = str(uuid.uuid4())

    await session_manager.add(
        MCPSession(
            session_id=session_id,
            server_id=server_config["server_id"],
            user_id=server_config["user_id"],
            slug=slug,
        )
    )

    async def _event_generator():
        try:
            yield {
                "event": "endpoint",
                "data": json.dumps(
                    {
                        "sessionId": session_id,
                        "messageUrl": (
                            f"/mcp/v1/{slug}/message"
                            f"?session_id={session_id}"
                        ),
                    }
                ),
            }

            while True:
                if await request.is_disconnected():
                    logger.info(
                        "sse_client_disconnected",
                        slug=slug,
                        session_id=session_id,
                    )
                    break
                yield {"event": "ping", "data": ""}
                await asyncio.sleep(15)
        except Exception:
            logger.exception(
                "sse_generator_error",
                slug=slug,
                session_id=session_id,
            )
        finally:
            await session_manager.remove(session_id)
            logger.info(
                "sse_session_cleaned_up",
                slug=slug,
                session_id=session_id,
            )

    return EventSourceResponse(
        _event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "MCP-Session-Id": session_id,
        },
    )


async def handle_message(
    slug: str,
    session_id: str,
    body: dict[str, Any],
    request: Request | None = None,
    current_user: Any = None,
) -> dict[str, Any]:
    """Handle an incoming JSON-RPC message via the message endpoint.

    Looks up the server configuration, validates or creates a session,
    parses the JSON-RPC request body, and routes to the appropriate
    handler via :func:`route_mcp_request`.

    Args:
        slug: The server slug.
        session_id: The SSE session ID (or ``"http"`` for
            StreamableHTTP).
        body: The raw JSON-RPC request body as a dict.
        request: The optional FastAPI request object.
        current_user: The optional authenticated user.

    Returns:
        A JSON-RPC response dict (success or error).
    """
    server_config = await _load_server_config(slug)

    session = await session_manager.get(session_id)
    if session is None:
        session = MCPSession(
            session_id=session_id,
            server_id=server_config["server_id"],
            user_id=server_config["user_id"],
            slug=slug,
        )
        await session_manager.add(session)

    try:
        request_obj = JSONRPCRequest(
            jsonrpc=body.get("jsonrpc", "2.0"),
            id=body.get("id", 1),
            method=body.get("method", ""),
            params=body.get("params"),
        )
    except Exception:
        logger.warning("invalid_jsonrpc_request", session_id=session_id)
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {
                "code": MCPErrorCode.INVALID_REQUEST,
                "message": "Invalid JSON-RPC request",
            },
        }

    result = await route_mcp_request(server_config, session, request_obj)

    if result is None:
        return {
            "jsonrpc": "2.0",
            "id": request_obj.id,
            "result": {},
        }

    return result


async def route_mcp_request(
    server_config: dict[str, Any],
    session: MCPSession,
    request_obj: JSONRPCRequest,
) -> dict[str, Any] | None:
    """Route a parsed JSON-RPC request to the appropriate handler.

    Dispatches based on ``request_obj.method``:

    * ``initialize`` -- returns server capabilities with
      ``protocolVersion`` ``"2025-11-25"`` and stores the client name.
    * ``notifications/initialized`` -- acknowledges (returns ``None``).
    * ``ping`` -- returns an empty result (keepalive).
    * ``tools/list`` -- returns the tools from the server config.
    * ``tools/call`` -- rate-checks, finds the tool, decrypts
      credentials, dispatches, and returns the result.
    * ``notifications/cancelled`` -- acknowledges (returns ``None``).
    * Anything else -- returns ``method_not_found_error``.

    Args:
        server_config: The server configuration dict.
        session: The active ``MCPSession`` for this connection.
        request_obj: The parsed ``JSONRPCRequest``.

    Returns:
        A JSON-RPC result or error dict, or ``None`` for notifications
        that do not produce a response.
    """
    # If the server is paused, return ServerDisabled error for all methods
    if server_config.get("status") != "active":
        return server_disabled_error(request_obj.id)

    method = request_obj.method
    req_id: str | int | None = request_obj.id

    # -- initialize --------------------------------------------------------
    if method == "initialize":
        params = request_obj.params or {}
        client_info = params.get("clientInfo", {})
        session.client_name = client_info.get("name")
        session.initialized = True
        await session_manager.add(session)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-11-25",
                "capabilities": {
                    "tools": {},
                    "experimental": {},
                },
                "serverInfo": {
                    "name": (
                        f"mcpforge-"
                        f"{server_config.get('slug', 'unknown')}"
                    ),
                    "version": "0.1.0",
                },
            },
        }

    # -- notifications/initialized -----------------------------------------
    if method == "notifications/initialized":
        logger.info(
            "client_initialized",
            session_id=session.session_id,
            client_name=session.client_name,
        )
        return None

    # -- ping --------------------------------------------------------------
    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    # -- tools/list --------------------------------------------------------
    if method == "tools/list":
        raw_tools_config = server_config.get("tools_config", {})
        tools = raw_tools_config.get("tools", [])

        formatted_tools: list[dict[str, Any]] = []
        for tool in tools:
            formatted_tools.append(
                {
                    "name": tool.get(
                        "ai_enhanced_name", tool.get("name", "")
                    ),
                    "description": tool.get(
                        "ai_enhanced_description",
                        tool.get("description", ""),
                    ),
                    "inputSchema": tool.get(
                        "inputSchema",
                        {"type": "object", "properties": {}},
                    ),
                }
            )

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": formatted_tools,
            },
        }

    # -- tools/call --------------------------------------------------------
    if method == "tools/call":
        params = request_obj.params or {}
        tool_name: str = params.get("name", "")
        arguments: dict[str, Any] = params.get("arguments", {})

        # 1. Rate limit check
        rate_result: RateLimitResult | None = None
        async for redis in get_redis():
            rate_limiter = GatewayRateLimiter(redis)
            plan: str = server_config.get("plan", "free")
            server_id_str: str = server_config["server_id"]
            rate_result = await rate_limiter.check(
                UUID(server_id_str), plan
            )
            break

        if rate_result is None or not rate_result.allowed:
            return rate_limit_error(req_id, retry_after=3600)

        # 2. Find the tool in the tools config
        raw_tools_config = server_config.get("tools_config", {})
        tools = raw_tools_config.get("tools", [])
        tool_config: dict[str, Any] | None = None
        for t in tools:
            t_name = t.get("name", "")
            t_enhanced = t.get("ai_enhanced_name", "")
            if t_name == tool_name or t_enhanced == tool_name:
                tool_config = t
                break

        if tool_config is None:
            return tool_not_found_error(req_id, tool_name)

        # 3. Decrypt credential if available
        credential_value: str | None = None
        try:
            credential_value = await CredentialService.decrypt_or_none(
                UUID(server_config["server_id"])
            )
        except Exception:
            logger.warning(
                "credential_decrypt_failed",
                server_id=server_config["server_id"],
            )

        # 4. Dispatch the tool call
        dispatcher = ToolDispatcher()
        started_at = time.monotonic()
        try:
            result = await dispatcher.dispatch(
                server_config,
                tool_config,
                arguments,
                credential_value,
            )
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            response_size = sum(
                len(str(b.get("text", "")).encode("utf-8"))
                for b in result.get("content", [])
                if isinstance(b, dict)
            )
            status, error_type, error_msg = classify_dispatch_status(result)
            emit_tool_call(
                server_id=server_config["server_id"],
                tool_name=tool_name,
                status=status,
                latency_ms=elapsed_ms,
                response_size_bytes=response_size,
                error_type=error_type,
                error_msg=error_msg,
                client_name=session.client_name,
            )

            logger.info(
                "tool_call_succeeded",
                tool_name=tool_name,
                session_id=session.session_id,
                latency_ms=elapsed_ms,
            )

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            emit_tool_call(
                server_id=server_config["server_id"],
                tool_name=tool_name,
                status="error",
                latency_ms=elapsed_ms,
                response_size_bytes=None,
                error_type=type(exc).__name__,
                error_msg=str(exc)[:500],
                client_name=session.client_name,
            )
            logger.exception(
                "tool_call_failed",
                tool_name=tool_name,
            )
            return upstream_error(req_id, str(exc))

    # -- notifications/cancelled -------------------------------------------
    if method == "notifications/cancelled":
        logger.info(
            "request_cancelled",
            session_id=session.session_id,
        )
        return None

    # -- Default: unknown method -------------------------------------------
    logger.warning(
        "unknown_method",
        method=method,
        session_id=session.session_id,
    )
    return method_not_found_error(req_id, method)
