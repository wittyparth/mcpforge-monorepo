"""Tests for the SSE transport layer (``transport_sse.py``).

Covers MCP protocol methods over SSE transport: ``initialize``,
``tools/list``, ``tools/call``, tool-not-found, session validation,
heartbeat keepalive, disconnect cleanup, and rate limiting.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateway.rate_limiter import GatewayRateLimiter, RateLimitResult
from app.gateway.session import MCPSession
from app.gateway.tool_dispatcher import ToolDispatcher
from app.schemas.mcp_protocol import JSONRPCRequest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server_config() -> dict[str, Any]:
    """A minimal active server configuration fixture."""
    return {
        "server_id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "slug": "test-server",
        "name": "Test Server",
        "base_url": "https://api.example.com",
        "auth_scheme": None,
        "auth_header_name": None,
        "tools_config": {
            "tools": [
                {
                    "name": "echo",
                    "description": "Echo back a message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"}
                        },
                        "required": ["message"],
                    },
                },
                {
                    "name": "weather",
                    "description": "Get weather for a city",
                    "ai_enhanced_name": "get_weather",
                    "ai_enhanced_description": (
                        "Retrieve current weather conditions "
                        "for any city worldwide"
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"}
                        },
                        "required": ["city"],
                    },
                },
            ]
        },
        "status": "active",
        "plan": "free",
        "transport_mode": "sse",
    }


@pytest.fixture
def mock_session() -> MCPSession:
    """A pre-built MCP session for handler tests."""
    return MCPSession(
        session_id="sess-test-001",
        server_id="550e8400-e29b-41d4-a716-446655440000",
        user_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        slug="test-server",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_get_redis(return_client: Any = None):
    """Return a ``patch`` context for ``transport_sse.get_redis``.

    ``get_redis`` is an async generator in the real implementation.
    This helper replaces it with one that yields a single mock Redis
    instance so ``async for`` loops inside the transport code work
    correctly.

    Args:
        return_client: The object to yield (defaults to an
            ``AsyncMock`` with a no-op ``close``).
    """
    redis = return_client if return_client is not None else AsyncMock()
    if not hasattr(redis, "close"):
        redis.close = AsyncMock()

    async def _gen():
        yield redis

    return patch("app.gateway.transport_sse.get_redis", lambda: _gen())


def _patch_config(config: dict[str, Any] | None):
    """Patch ``_load_server_config`` so tests do not hit Redis.

    Args:
        config: The server config dict to return, or ``None`` to
            simulate a missing server.
    """
    return patch(
        "app.gateway.transport_sse._load_server_config",
        AsyncMock(return_value=config),
    )


# ---------------------------------------------------------------------------
# Test 1: initialize — returns capabilities
# ---------------------------------------------------------------------------


class TestInitialize:
    """``initialize`` handshake returns protocol version and capabilities."""

    @pytest.mark.asyncio
    async def test_initialize_returns_capabilities(
        self,
        server_config: dict[str, Any],
        mock_session: MCPSession,
    ) -> None:
        """A valid initialize request returns capabilities and records
        client info on the session."""
        from app.gateway.transport_sse import route_mcp_request

        request_obj = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="initialize",
            params={
                "protocolVersion": "2025-11-25",
                "clientInfo": {
                    "name": "claude-desktop",
                    "version": "1.0.0",
                },
            },
        )

        result = await route_mcp_request(
            server_config, mock_session, request_obj
        )

        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1

        inner = result["result"]
        assert inner["protocolVersion"] == "2025-11-25"
        assert "tools" in inner["capabilities"]
        assert "experimental" in inner["capabilities"]
        assert inner["serverInfo"]["name"] == "mcpforge-test-server"
        assert inner["serverInfo"]["version"] == "0.1.0"

        assert mock_session.initialized is True
        assert mock_session.client_name == "claude-desktop"


# ---------------------------------------------------------------------------
# Test 2: tools/list — returns tools
# ---------------------------------------------------------------------------


class TestToolsList:
    """``tools/list`` returns the server's tool catalog."""

    @pytest.mark.asyncio
    async def test_tools_list_returns_tools(
        self,
        server_config: dict[str, Any],
        mock_session: MCPSession,
    ) -> None:
        """tools/list returns all tools with AI-enhanced name/description
        preferred when present."""
        from app.gateway.transport_sse import route_mcp_request

        request_obj = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="tools/list"
        )

        result = await route_mcp_request(
            server_config, mock_session, request_obj
        )

        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 2

        tools = result["result"]["tools"]
        assert len(tools) == 2

        # Basic name
        assert tools[0]["name"] == "echo"
        assert tools[0]["description"] == "Echo back a message"

        # AI-enhanced fields preferred
        assert tools[1]["name"] == "get_weather"
        assert tools[1]["description"] == (
            "Retrieve current weather conditions "
            "for any city worldwide"
        )


# ---------------------------------------------------------------------------
# Test 3: tools/call — dispatch success
# ---------------------------------------------------------------------------


class TestToolsCallSuccess:
    """``tools/call`` — successful dispatch."""

    @pytest.mark.asyncio
    async def test_tools_call_success(
        self,
        server_config: dict[str, Any],
        mock_session: MCPSession,
    ) -> None:
        """A valid tools/call dispatches via ToolDispatcher and returns
        the result."""
        from app.gateway.transport_sse import route_mcp_request

        request_obj = JSONRPCRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/call",
            params={
                "name": "echo",
                "arguments": {"message": "Hello world"},
            },
        )

        fake_result = {
            "content": [{"type": "text", "text": "Hello world"}]
        }

        with (
            _mock_get_redis(),
            patch.object(
                GatewayRateLimiter,
                "check",
                AsyncMock(
                    return_value=RateLimitResult(
                        allowed=True, reason="ok", current=1, limit=1000,
                    )
                ),
            ),
            patch.object(
                ToolDispatcher,
                "dispatch",
                AsyncMock(return_value=fake_result),
            ) as mock_dispatch,
        ):
            result = await route_mcp_request(
                server_config, mock_session, request_obj
            )

        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 3
        assert result["result"] == fake_result

        mock_dispatch.assert_called_once_with(
            server_config,
            server_config["tools_config"]["tools"][0],
            {"message": "Hello world"},
            None,
        )


# ---------------------------------------------------------------------------
# Test 4: tool not found
# ---------------------------------------------------------------------------


class TestToolNotFound:
    """``tools/call`` with an unknown tool name."""

    @pytest.mark.asyncio
    async def test_tool_not_found(
        self,
        server_config: dict[str, Any],
        mock_session: MCPSession,
    ) -> None:
        """tools/call for an unknown tool returns a JSON-RPC error with
        TOOL_NOT_FOUND code."""
        from app.gateway.transport_sse import route_mcp_request

        request_obj = JSONRPCRequest(
            jsonrpc="2.0",
            id=4,
            method="tools/call",
            params={
                "name": "nonexistent_tool",
                "arguments": {},
            },
        )

        with (
            _mock_get_redis(),
            patch.object(
                GatewayRateLimiter,
                "check",
                AsyncMock(
                    return_value=RateLimitResult(
                        allowed=True, reason="ok", current=1, limit=1000,
                    )
                ),
            ),
        ):
            result = await route_mcp_request(
                server_config, mock_session, request_obj
            )

        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 4
        assert "error" in result
        assert result["error"]["code"] == -32001  # TOOL_NOT_FOUND
        assert "nonexistent_tool" in result["error"]["message"]


# ---------------------------------------------------------------------------
# Test 5: session validation — handle_message creates session if missing
# ---------------------------------------------------------------------------


class TestSessionValidation:
    """Session creation on first message (lenient v1.0 behaviour)."""

    @pytest.mark.asyncio
    async def test_session_created_when_missing(
        self,
        server_config: dict[str, Any],
    ) -> None:
        """handle_message creates a new MCPSession and adds it to the
        session manager when the session_id does not exist yet."""
        from app.gateway.transport_sse import (
            handle_message,
            session_manager,
        )

        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "ping",
        }

        with _patch_config(server_config):
            result = await handle_message(
                "test-server", "sess-new-001", body
            )

        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["result"] == {}

        # The session should have been created and stored
        session = await session_manager.get("sess-new-001")
        assert session is not None
        assert session.session_id == "sess-new-001"
        assert session.slug == "test-server"


# ---------------------------------------------------------------------------
# Test 6: heartbeat — connection stays alive
# ---------------------------------------------------------------------------


class TestHeartbeat:
    """SSE connection heartbeat."""

    @pytest.mark.asyncio
    async def test_heartbeat(
        self,
        server_config: dict[str, Any],
    ) -> None:
        """The SSE stream sends an ``endpoint`` event first, followed by
        a ``ping`` event."""
        request = MagicMock()
        request.is_disconnected = AsyncMock(side_effect=[False, True])

        from app.gateway.transport_sse import handle_sse_connection

        with _patch_config(server_config):
            response = await handle_sse_connection(
                "test-server", request
            )

        # Collect the first two SSE events (body_iterator yields raw dicts)
        event_count = 0
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            if event_count == 0:
                assert chunk["event"] == "endpoint"
                payload = json.loads(chunk["data"])
                assert "sessionId" in payload
                assert payload["messageUrl"].startswith(
                    "/mcp/v1/test-server/message"
                )
            elif event_count == 1:
                assert chunk["event"] == "ping"
            else:
                break
            event_count += 1


# ---------------------------------------------------------------------------
# Test 7: disconnect cleanup — session removed
# ---------------------------------------------------------------------------


class TestDisconnectCleanup:
    """Session cleanup on client disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(
        self,
        server_config: dict[str, Any],
    ) -> None:
        """When the client disconnects, the session is removed from the
        session manager."""
        request = MagicMock()
        request.is_disconnected = AsyncMock(return_value=True)

        from app.gateway.transport_sse import (
            handle_sse_connection,
            session_manager,
        )

        with (
            _patch_config(server_config),
            patch.object(session_manager, "remove", AsyncMock()) as mock_remove,
        ):
            response = await handle_sse_connection(
                "test-server", request
            )

            # Exhaust the generator (triggers finally block)
            async for _ in response.body_iterator:
                pass

        # session_manager.remove should have been called
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[0][0]
        assert isinstance(call_args, str)
        assert len(call_args) > 0  # valid UUID string


# ---------------------------------------------------------------------------
# Test 8: rate limit exceeded
# ---------------------------------------------------------------------------


class TestRateLimit:
    """Rate limit exceeded returns a JSON-RPC error."""

    @pytest.mark.asyncio
    async def test_rate_limit(
        self,
        server_config: dict[str, Any],
        mock_session: MCPSession,
    ) -> None:
        """When the rate limiter denies a request, a rate_limit_error is
        returned instead of dispatching the tool."""
        from app.gateway.transport_sse import route_mcp_request

        request_obj = JSONRPCRequest(
            jsonrpc="2.0",
            id=6,
            method="tools/call",
            params={
                "name": "echo",
                "arguments": {"message": "should be rate limited"},
            },
        )

        with (
            _mock_get_redis(),
            patch.object(
                GatewayRateLimiter,
                "check",
                AsyncMock(
                    return_value=RateLimitResult(
                        allowed=False, reason="hour", current=60, limit=60,
                    )
                ),
            ),
        ):
            result = await route_mcp_request(
                server_config, mock_session, request_obj
            )

        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 6
        assert "error" in result
        assert result["error"]["code"] == -32003  # RATE_LIMIT_EXCEEDED
        assert "retry_after_seconds" in result["error"].get("data", {})
