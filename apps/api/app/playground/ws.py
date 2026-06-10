"""WebSocket playground handler — full MCP-over-WebSocket with JSON-RPC 2.0.

Provides a browser-accessible WebSocket endpoint for testing MCP servers
before and after deployment. The handler supports both:

  - **Pre-deployment mode** (server status != ``"active"``): loads the
    draft ``tools_config`` directly from the database so users can test
    in-progress changes without deploying.
  - **Post-deployment mode** (server status == ``"active"``): uses the
    cached server configuration (which includes AI-enhanced tool
    descriptions if the AI Description Engine has been run).

Auth: clients pass a JWT access token via the ``?token=<jwt>`` query
parameter.  The token is validated **once** on connection.  On failure
the WebSocket is closed with code 1008 (policy violation) and a
JSON-RPC error frame is sent first.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.redis import get_redis_pool
from app.core.security import decode_token
from app.gateway.tool_dispatcher import ToolDispatcher
from app.repositories.mcp_server_repo import MCPServerRepository
from app.schemas.mcp_protocol import MCPErrorCode
from app.services.server_config_cache import ServerConfigCache

logger = get_logger(__name__)

router = APIRouter()

# ── In-memory session store ──────────────────────────────────────────────
# Ephemeral: never persisted to DB or Redis.  Sessions live for the duration
# of the WebSocket connection and are cleaned up on disconnect.

_sessions: dict[str, PlaygroundSession] = {}


class PlaygroundSession:
    """An ephemeral in-memory session for a single WebSocket playground connection.

    Attributes:
        session_id: Unique UUID string for this session.
        server_slug: The slug of the MCP server being tested.
        user_id: The authenticated user's UUID string.
        server_config: The server configuration dict (from cache or DB).
        created_at: UTC timestamp when the session was created.
        call_count: Number of successful ``tools/call`` invocations.
        last_activity: UTC timestamp of the last message received.
        dispatcher: A ``ToolDispatcher`` instance for executing tool calls.
    """

    def __init__(
        self,
        session_id: str,
        server_slug: str,
        user_id: str,
        server_config: dict[str, Any],
    ) -> None:
        self.session_id = session_id
        self.server_slug = server_slug
        self.user_id = user_id
        self.server_config = server_config
        self.created_at = datetime.now(UTC)
        self.call_count = 0
        self.last_activity = datetime.now(UTC)
        self.dispatcher = ToolDispatcher()

    @property
    def is_pre_deployment(self) -> bool:
        """True if the server has not been deployed (status != ``"active"``)."""
        return self.server_config.get("status") != "active"

    def touch(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now(UTC)


# ═══════════════════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════════════════


async def _authenticate_ws(token: str | None) -> str:
    """Validate a JWT access token from the WebSocket query string.

    Args:
        token: The raw JWT string (or ``None``).

    Returns:
        The ``user_id`` (UUID string) extracted from the token payload.

    Raises:
        UnauthorizedError: If the token is missing, invalid, or expired.
    """
    if not token:
        raise UnauthorizedError("Missing token query parameter")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        return str(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


# ═══════════════════════════════════════════════════════════════════════════
# Server config helpers
# ═══════════════════════════════════════════════════════════════════════════


async def _load_server_draft(
    slug: str,
    user_id: str,
    session: AsyncSession,
) -> dict[str, Any] | None:
    """Load a server configuration directly from the database.

    Used as a fallback when the server is not in the Redis cache
    (pre-deployment mode, or cache miss).  Builds a config dict
    consistent with ``ServerConfigCache._build_config``.

    Args:
        slug: The server's unique slug.
        user_id: The authenticated user's UUID string (for ownership check).
        session: An async SQLAlchemy session.

    Returns:
        A server configuration dict, or ``None`` if the slug is not found.
    """
    repo = MCPServerRepository(session)
    server = await repo.get_by_slug(slug)
    if server is None:
        return None

    return {
        "server_id": str(server.id),
        "user_id": str(server.user_id),
        "slug": server.slug,
        "name": server.name,
        "base_url": server.base_url,
        "auth_scheme": server.auth_scheme,
        "auth_header_name": server.auth_header_name,
        "tools_config": server.tools_config,
        "status": server.status,
        "plan": "free",
    }


# ═══════════════════════════════════════════════════════════════════════════
# JSON-RPC helpers
# ═══════════════════════════════════════════════════════════════════════════


def _jsonrpc_error(
    request_id: str | int | None,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response dictionary.

    Args:
        request_id: Echoed back from the request (may be ``None``).
        code: JSON-RPC error code (see ``MCPErrorCode``).
        message: Human-readable error description.
        data: Optional structured payload with additional context.

    Returns:
        A dict ready to be serialised as JSON.
    """
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _jsonrpc_result(
    request_id: str | int | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 success response dictionary.

    Args:
        request_id: Echoed back from the request.
        result: The method result.

    Returns:
        A dict ready to be serialised as JSON.
    """
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


async def _send_json(websocket: WebSocket, data: dict[str, Any]) -> None:
    """Serialise a dict as JSON and send it over the WebSocket."""
    await websocket.send_text(json.dumps(data))


# ═══════════════════════════════════════════════════════════════════════════
# Tool helpers
# ═══════════════════════════════════════════════════════════════════════════


def _build_tool_list(server_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the MCP ``tools`` array from the server's ``tools_config``.

    Uses ``ai_enhanced_name`` / ``ai_enhanced_description`` when available,
    falling back to the original ``name`` / ``description``.

    Args:
        server_config: The server configuration dict (must contain
            ``tools_config.tools``).

    Returns:
        A list of MCP tool definition dicts, each with ``name``,
        ``description``, and ``inputSchema`` keys.
    """
    tools_config = server_config.get("tools_config", {})
    raw_tools: list[dict[str, Any]] = tools_config.get("tools", [])

    mcp_tools: list[dict[str, Any]] = []
    for tool in raw_tools:
        name: str = tool.get("ai_enhanced_name") or tool.get("name", "unknown")
        description: str = tool.get("ai_enhanced_description") or tool.get("description", "")
        input_schema: dict[str, Any] = tool.get(
            "inputSchema",
            tool.get("input_schema", {"type": "object", "properties": {}}),
        )

        mcp_tools.append(
            {
                "name": name,
                "description": description,
                "inputSchema": input_schema,
            }
        )

    return mcp_tools


def _find_tool(
    server_config: dict[str, Any],
    tool_name: str,
) -> dict[str, Any] | None:
    """Find a tool definition by name in the server's ``tools_config``.

    Checks ``ai_enhanced_name`` first, then falls back to the original
    ``name``.

    Args:
        server_config: The server configuration dict.
        tool_name: The name of the tool to find.

    Returns:
        The raw tool definition dict, or ``None`` if no match.
    """
    tools_config = server_config.get("tools_config", {})
    raw_tools: list[dict[str, Any]] = tools_config.get("tools", [])

    for tool in raw_tools:
        ai_name = tool.get("ai_enhanced_name")
        original_name = tool.get("name")
        if ai_name == tool_name or original_name == tool_name:
            return tool

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Message handlers
# ═══════════════════════════════════════════════════════════════════════════


async def _send_tools_list(
    websocket: WebSocket,
    session: PlaygroundSession,
) -> None:
    """Send a ``tools/list`` result to the client immediately after connect."""
    tools = _build_tool_list(session.server_config)
    response = _jsonrpc_result(0, {"tools": tools})
    await _send_json(websocket, response)


async def _handle_tools_call(
    websocket: WebSocket,
    session: PlaygroundSession,
    message: dict[str, Any],
) -> None:
    """Handle a ``tools/call`` request — dispatch via ``ToolDispatcher``.

    Args:
        websocket: The active WebSocket connection.
        session: The current playground session.
        message: The parsed JSON-RPC 2.0 request dict.
    """
    request_id: str | int | None = message.get("id", 0)
    params: dict[str, Any] = message.get("params", {})
    tool_name: str = params.get("name", "")
    arguments: dict[str, object] = params.get("arguments", {})

    if not tool_name:
        error = _jsonrpc_error(
            request_id,
            MCPErrorCode.INVALID_PARAMS,
            "Tool name is required",
        )
        await _send_json(websocket, error)
        return

    tool_config = _find_tool(session.server_config, tool_name)
    if tool_config is None:
        error = _jsonrpc_error(
            request_id,
            MCPErrorCode.TOOL_NOT_FOUND,
            f"Tool not found: {tool_name}",
        )
        await _send_json(websocket, error)
        return

    start_time = time.monotonic()
    try:
        result = await session.dispatcher.dispatch(
            server_config=session.server_config,
            tool_config=tool_config,
            arguments=arguments,
            credential_value=None,  # credentials not supported in playground (yet)
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "tool_dispatch_error",
            tool_name=tool_name,
            error=str(exc),
            session_id=session.session_id,
        )
        error = _jsonrpc_error(
            request_id,
            MCPErrorCode.INTERNAL_ERROR,
            str(exc),
            data={"elapsed_ms": elapsed_ms},
        )
        await _send_json(websocket, error)
        return

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    session.call_count += 1
    session.touch()

    # Attach execution timing metadata
    result["_meta"] = {"elapsed_ms": elapsed_ms}

    response = _jsonrpc_result(request_id, result)
    await _send_json(websocket, response)

    logger.info(
        "tool_call_completed",
        tool_name=tool_name,
        elapsed_ms=elapsed_ms,
        session_id=session.session_id,
        slug=session.server_slug,
    )


async def _handle_message(
    websocket: WebSocket,
    session: PlaygroundSession,
    message: dict[str, Any],
) -> None:
    """Route an incoming JSON-RPC 2.0 message to the correct handler.

    Supported methods:
        - ``tools/list`` — return the list of available tools.
        - ``tools/call`` — execute a tool via ``ToolDispatcher``.
        - ``ping`` — return a ``"pong"`` string.

    All other methods receive a ``METHOD_NOT_FOUND`` error.
    """
    method: str | None = message.get("method")
    request_id: str | int | None = message.get("id")

    if not method:
        error = _jsonrpc_error(
            request_id,
            MCPErrorCode.INVALID_REQUEST,
            "Request missing 'method' field",
        )
        await _send_json(websocket, error)
        return

    if method == "tools/call":
        await _handle_tools_call(websocket, session, message)
    elif method == "tools/list":
        await _send_tools_list(websocket, session)
    elif method == "ping":
        await _send_json(websocket, _jsonrpc_result(request_id, {}))
    else:
        error = _jsonrpc_error(
            request_id,
            MCPErrorCode.METHOD_NOT_FOUND,
            f"Method '{method}' not found",
        )
        await _send_json(websocket, error)


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket endpoint
# ═══════════════════════════════════════════════════════════════════════════


@router.websocket("/ws/playground/{slug}")
async def playground_websocket(
    websocket: WebSocket,
    slug: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for the MCP Playground (auth required).

    Connection flow:
        1. Accept the WebSocket upgrade.
        2. Authenticate via ``?token=<jwt>`` (JWT access token).
        3. Load server config (from Redis cache or, for pre-deployment,
           directly from the database).
        4. Verify the authenticated user owns the server.
        5. Create an ephemeral ``PlaygroundSession`` and store it in memory.
        6. Send an initial ``tools/list`` response.
        7. Enter the message loop, handling ``tools/call``, ``tools/list``,
           ``ping``, and unknown methods.
        8. On disconnect, clean up the session and close the ToolDispatcher's
           HTTP client.

    Args:
        websocket: The active WebSocket connection.
        slug: The server slug from the URL path.
        token: JWT access token from the ``?token=`` query parameter.
        db: Async database session (injected via Depends).
    """
    session_id = str(uuid.uuid4())
    pg_session: PlaygroundSession | None = None

    # ── 1. Accept ───────────────────────────────────────────────────────
    await websocket.accept()

    # ── 2. Authenticate ─────────────────────────────────────────────────
    try:
        user_id = await _authenticate_ws(token)
    except UnauthorizedError as exc:
        logger.warning("playground_auth_failed", slug=slug, reason=exc.message)
        await _send_json(
            websocket,
            _jsonrpc_error(
                0,
                MCPErrorCode.TOOL_NOT_FOUND,
                exc.message,
            ),
        )
        await websocket.close(code=1008, reason=exc.message)
        return

    # ── 3. Load server config ───────────────────────────────────────────
    # Try the Redis cache first (post-deployment path).  If the server is
    # not yet active or the cache misses, fall back to a direct DB load.
    redis: Redis | None = None
    try:
        redis_pool = await get_redis_pool()
        redis = Redis.from_pool(redis_pool)
        server_config = await ServerConfigCache.get(slug, redis)
    except Exception:
        server_config = None
        logger.warning("playground_redis_unavailable", slug=slug)
    finally:
        if redis is not None:
            await redis.close()

    is_pre_deployment = False
    if server_config is None:
        # Fallback: load directly from DB (pre-deployment / cache miss)
        server_config = await _load_server_draft(slug, user_id, db)
        if server_config is None:
            logger.warning("playground_server_not_found", slug=slug)
            await _send_json(
                websocket,
                _jsonrpc_error(
                    0,
                    MCPErrorCode.TOOL_NOT_FOUND,
                    f"Server not found: {slug}",
                ),
            )
            await websocket.close(code=1008, reason="Server not found")
            return
        is_pre_deployment = True

    # ── 4. Verify ownership ─────────────────────────────────────────────
    config_user_id = server_config.get("user_id")
    if config_user_id is not None and str(config_user_id) != user_id:
        logger.warning(
            "playground_ownership_mismatch",
            slug=slug,
            config_user_id=str(config_user_id),
            request_user_id=user_id,
        )
        await _send_json(
            websocket,
            _jsonrpc_error(0, MCPErrorCode.TOOL_NOT_FOUND, "Server not found"),
        )
        await websocket.close(code=1008, reason="Server not found")
        return

    # ── 5. Create session ───────────────────────────────────────────────
    pg_session = PlaygroundSession(
        session_id=session_id,
        server_slug=slug,
        user_id=user_id,
        server_config=server_config,
    )
    _sessions[session_id] = pg_session

    logger.info(
        "playground_session_started",
        session_id=session_id,
        slug=slug,
        user_id=user_id,
        is_pre_deployment=is_pre_deployment,
    )

    # ── 6. Send initial tools/list ──────────────────────────────────────
    await _send_tools_list(websocket, pg_session)

    # ── 7. Message loop ─────────────────────────────────────────────────
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message: Any = json.loads(data)
            except json.JSONDecodeError:
                error = _jsonrpc_error(
                    None,
                    MCPErrorCode.PARSE_ERROR,
                    "Invalid JSON",
                )
                await _send_json(websocket, error)
                continue

            if not isinstance(message, dict):
                error = _jsonrpc_error(
                    None,
                    MCPErrorCode.INVALID_REQUEST,
                    "Request must be a JSON object",
                )
                await _send_json(websocket, error)
                continue

            await _handle_message(websocket, pg_session, message)

    except WebSocketDisconnect:
        logger.info(
            "playground_client_disconnected",
            session_id=session_id,
            slug=slug,
            call_count=pg_session.call_count if pg_session else 0,
        )
    except Exception:
        logger.exception(
            "playground_unexpected_error",
            session_id=session_id,
            slug=slug,
        )
    finally:
        # ── 8. Cleanup ──────────────────────────────────────────────────
        if pg_session is not None:
            _sessions.pop(session_id, None)
            await pg_session.dispatcher.client.aclose()
            logger.info(
                "playground_session_ended",
                session_id=session_id,
                slug=slug,
                call_count=pg_session.call_count,
            )
