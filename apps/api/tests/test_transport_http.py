"""Tests for the StreamableHTTP transport (transport_http.py).

Covers 8 scenarios:
1. test_post_initialize         — POST initialize returns capabilities + session ID header
2. test_post_tools_list         — POST tools/list returns tool list
3. test_post_tools_call         — POST tools/call returns tool result
4. test_notification_202        — POST notification returns 202 Accepted
5. test_get_sse_stream           — GET opens SSE event stream
6. test_mcp_session_id_header    — MCP-Session-Id header round-trip
7. test_invalid_session          — Unknown session ID creates a new session gracefully
8. test_wrong_owner              — Non-existent slug returns 404
"""

from __future__ import annotations

import json
import uuid
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

from app.gateway.transport_http import handle_http_request


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_ACTIVE_CONFIG = {
    "server_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-abc-123",
    "slug": "test-server",
    "status": "active",
    "plan": "free",
    "tools_config": {"tools": []},
    "base_url": "https://api.example.com",
}

_INIT_RESPONSE = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "protocolVersion": "2025-11-25",
        "capabilities": {"tools": {}},
        "serverInfo": {
            "name": "mcpforge-test-server",
            "version": "0.1.0",
        },
    },
}

_TOOLS_LIST_RESPONSE = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "tools": [
            {
                "name": "echo",
                "description": "Echoes back the input message.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message to echo back",
                        }
                    },
                    "required": ["message"],
                },
            }
        ],
    },
}

_TOOLS_CALL_RESPONSE = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [{"type": "text", "text": "hello"}],
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_redis_infra():
    """Mock Redis pool + client so tests never touch a real Redis instance."""
    with (
        patch("app.gateway.transport_http.get_redis_pool") as mock_pool,
        patch("app.gateway.transport_http.AsyncRedis.from_pool") as mock_from_pool,
    ):
        mock_pool.return_value = AsyncMock()
        mock_from_pool.return_value = AsyncMock()
        yield


@pytest.fixture(autouse=True)
def _clear_sessions():
    """Reset the shared session manager before every test."""
    from app.gateway.transport_sse import session_manager

    session_manager._sessions.clear()
    yield


def _mock_request(
    method: str = "POST",
    session_id: str | None = None,
) -> AsyncMock:
    """Build a minimal AsyncMock that quacks like a FastAPI Request."""
    req = AsyncMock(spec=Request)
    req.method = method
    headers = {}
    if session_id is not None:
        headers["MCP-Session-Id"] = session_id
    req.headers = headers
    return req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHandleHttpRequest:
    """Direct unit tests for handle_http_request()."""

    # ── 1. POST initialize ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_post_initialize(self) -> None:
        """POST with ``initialize`` returns capabilities and session header."""
        with patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=_ACTIVE_CONFIG,
        ):
            with patch(
                "app.gateway.transport_http.route_mcp_request",
                return_value=_INIT_RESPONSE,
            ):
                result = await handle_http_request(
                    slug="test-server",
                    body={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )

        assert result.status_code == 200
        body_bytes = cast(bytes, result.body)
        data = json.loads(body_bytes.decode())
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert "capabilities" in data["result"]
        assert data["result"]["protocolVersion"] == "2025-11-25"
        assert "MCP-Session-Id" in result.headers
        sid = result.headers["MCP-Session-Id"]
        # Verify it's a valid UUID
        uuid.UUID(sid)

    # ── 2. POST tools/list ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_post_tools_list(self) -> None:
        """POST with ``tools/list`` returns the tool list."""
        with patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=_ACTIVE_CONFIG,
        ):
            with patch(
                "app.gateway.transport_http.route_mcp_request",
                return_value=_TOOLS_LIST_RESPONSE,
            ):
                result = await handle_http_request(
                    slug="test-server",
                    body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                )

        assert result.status_code == 200
        body_bytes = cast(bytes, result.body)
        data = json.loads(body_bytes.decode())
        assert "result" in data
        assert "tools" in data["result"]
        tools = data["result"]["tools"]
        assert isinstance(tools, list)
        assert len(tools) >= 1
        assert tools[0]["name"] == "echo"

    # ── 3. POST tools/call ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_post_tools_call(self) -> None:
        """POST with ``tools/call`` returns the tool execution result."""
        with patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=_ACTIVE_CONFIG,
        ):
            with patch(
                "app.gateway.transport_http.route_mcp_request",
                return_value=_TOOLS_CALL_RESPONSE,
            ):
                result = await handle_http_request(
                    slug="test-server",
                    body={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "echo",
                            "arguments": {"message": "hello"},
                        },
                    },
                )

        assert result.status_code == 200
        body_bytes = cast(bytes, result.body)
        data = json.loads(body_bytes.decode())
        assert "result" in data
        assert "content" in data["result"]
        assert data["result"]["content"][0]["text"] == "hello"

    # ── 4. POST notification → 202 ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_notification_202(self) -> None:
        """A notification (no ``id``) returns 202 Accepted with no body."""
        with patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=_ACTIVE_CONFIG,
        ):
            with patch(
                "app.gateway.transport_http.route_mcp_request",
                return_value=None,  # ← notification produces no response
            ):
                result = await handle_http_request(
                    slug="test-server",
                    body={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    },
                )

        assert result.status_code == 202
        assert result.body == b""
        assert "MCP-Session-Id" in result.headers

    # ── 5. GET → SSE stream ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_sse_stream(self) -> None:
        """GET request returns an SSE event stream (heartbeat)."""
        # No body needed — GET returns a streaming response directly
        req = _mock_request(method="GET")
        result = await handle_http_request(
            slug="test-server",
            request=req,
        )

        assert result.status_code == 200
        assert result.media_type == "text/event-stream"

    # ── 6. MCP-Session-Id header round-trip ────────────────────────────

    @pytest.mark.asyncio
    async def test_mcp_session_id_header(self) -> None:
        """The ``MCP-Session-Id`` provided in the request is echoed back."""
        supplied_sid = str(uuid.uuid4())
        req = _mock_request(method="POST", session_id=supplied_sid)

        with patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=_ACTIVE_CONFIG,
        ):
            with patch(
                "app.gateway.transport_http.route_mcp_request",
                return_value=_INIT_RESPONSE,
            ):
                result = await handle_http_request(
                    slug="test-server",
                    body={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                    request=req,
                )

        assert result.headers.get("MCP-Session-Id") == supplied_sid

    # ── 7. Invalid (non-existent) session ──────────────────────────────

    @pytest.mark.asyncio
    async def test_invalid_session(self) -> None:
        """A session ID that does not exist creates a new session gracefully."""
        unknown_sid = "i-do-not-exist"
        req = _mock_request(method="POST", session_id=unknown_sid)

        with patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=_ACTIVE_CONFIG,
        ):
            with patch(
                "app.gateway.transport_http.route_mcp_request",
                return_value=_INIT_RESPONSE,
            ):
                result = await handle_http_request(
                    slug="test-server",
                    body={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                    request=req,
                )

        # Should succeed and return a new session ID (the unknown one
        # was overwritten with a fresh session).
        assert result.status_code == 200
        sid = result.headers["MCP-Session-Id"]
        assert sid == unknown_sid  # We keep the client-provided ID

        # Verify the session was actually created in the manager
        from app.gateway.transport_sse import session_manager

        session = await session_manager.get(unknown_sid)
        assert session is not None
        assert session.slug == "test-server"

    # ── 8. Wrong owner / non-existent server ───────────────────────────

    @pytest.mark.asyncio
    async def test_wrong_owner(self) -> None:
        """A non-existent slug raises NotFoundError (→ 404)."""
        from app.core.exceptions import NotFoundError

        with patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=None,  # ← no server found
        ):
            with pytest.raises(NotFoundError) as exc:
                await handle_http_request(
                    slug="non-existent-slug",
                    body={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
        assert "non-existent-slug" in str(exc.value)
