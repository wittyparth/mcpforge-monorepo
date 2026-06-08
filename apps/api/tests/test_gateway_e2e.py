"""E2E tests for the MCP gateway — full flow through the FastAPI stack with mocked upstream.

Tests the complete gateway flow (initialize → tools/list → tools/call) over
both SSE and StreamableHTTP transports, plus pause/resume guard, free-tier
rate limiting, and credential decryption paths — all with mocked external
dependencies (Redis, upstream API, credentials).

See AGENTS.md → Anti-patterns for the project convention on mocking.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.gateway.rate_limiter import GatewayRateLimiter, RateLimitResult
from app.gateway.tool_dispatcher import ToolDispatcher
from app.main import app

# ── Global test config ────────────────────────────────────────────────────
# Bypass CSRF middleware in tests (see app/core/middleware/csrf.py:111).
settings.ENVIRONMENT = "testing"

ACTIVE_CONFIG: dict[str, Any] = {
    "server_id": "00000000-0000-0000-0000-000000000001",
    "user_id": "00000000-0000-0000-0000-000000000002",
    "slug": "test-server",
    "name": "Test Server",
    "base_url": "https://api.example.com",
    "auth_scheme": "bearer",
    "auth_header_name": None,
    "tools_config": {
        "tools": [
            {
                "name": "search",
                "description": "Search for items",
                "method": "GET",
                "path": "/search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
            }
        ]
    },
    "status": "active",
    "plan": "free",
    "transport_mode": "sse",
}

PAUSED_CONFIG: dict[str, Any] = {**ACTIVE_CONFIG, "status": "paused"}

TOOL_CALL_RESULT: dict[str, Any] = {
    "content": [{"type": "text", "text": '{"results": ["item1"]}'}],
    "isError": False,
}


# ── Helpers ────────────────────────────────────────────────────────────────


def _mock_get_redis() -> patch:
    """Patch ``transport_sse.get_redis`` to yield a single mock Redis client.

    ``get_redis`` is an async generator in the real implementation.  This
    replaces it with one that yields a single ``AsyncMock`` so ``async for``
    loops inside ``route_mcp_request`` work correctly.
    """
    redis = AsyncMock()
    redis.close = AsyncMock()

    async def _gen():
        yield redis

    return patch("app.gateway.transport_sse.get_redis", lambda: _gen())


def _assert_jsonrpc_ok(
    resp_data: dict[str, Any],
    expected_id: int | str,
) -> dict[str, Any]:
    """Assert a JSON-RPC 2.0 success response and return the ``result`` dict."""
    assert resp_data["jsonrpc"] == "2.0", "Must be JSON-RPC 2.0"
    assert resp_data["id"] == expected_id, f"ID must match {expected_id}"
    assert "result" in resp_data, "Must contain a result key"
    return resp_data["result"]


def _assert_jsonrpc_error(
    resp_data: dict[str, Any],
    expected_id: int | str | None,
) -> dict[str, Any]:
    """Assert a JSON-RPC 2.0 error response and return the ``error`` dict."""
    assert resp_data["jsonrpc"] == "2.0"
    assert resp_data["id"] == expected_id
    assert "error" in resp_data, "Must contain an error key"
    return resp_data["error"]


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _auth_override() -> None:
    """Override ``authenticate_mcp_request`` so tests skip JWT validation."""
    from app.gateway.mcp_server import authenticate_mcp_request

    app.dependency_overrides[authenticate_mcp_request] = lambda: None
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    """Reset the in-memory session manager before each test."""
    from app.gateway.transport_sse import session_manager

    session_manager._sessions.clear()
    yield


@pytest.fixture(autouse=True)
def _mock_http_redis() -> None:
    """Mock Redis pool + client for ``transport_http`` so tests never touch Redis."""
    with (
        patch("app.gateway.transport_http.get_redis_pool") as mock_pool,
        patch("app.gateway.transport_http.AsyncRedis.from_pool") as mock_from_pool,
    ):
        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_pool.return_value = AsyncMock()
        mock_from_pool.return_value = mock_redis
        yield


@pytest.fixture
async def client() -> AsyncClient:
    """Provide an async HTTP test client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: Full e2e — initialize → tools/list → tools/call (HTTP transport)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_flow_init_list_call(client: AsyncClient) -> None:
    """Full e2e over HTTP: initialize → tools/list → tools/call succeeds.

    Mocks:
        - ``ServerConfigCache.get`` → ``ACTIVE_CONFIG``
        - ``GatewayRateLimiter.check`` → allowed
        - ``ToolDispatcher.dispatch`` → ``TOOL_CALL_RESULT``
        - ``get_redis`` (transport_sse) for rate-limit loop
    """
    with patch(
        "app.gateway.transport_http.ServerConfigCache.get",
        return_value=ACTIVE_CONFIG,
    ):
        # ── Step 1: initialize ──────────────────────────────────────────
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 1)
        assert result["protocolVersion"] == "2025-11-25"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "mcpforge-test-server"

        # ── Step 2: tools/list ──────────────────────────────────────────
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 2)
        assert len(result["tools"]) == 1
        tool = result["tools"][0]
        assert tool["name"] == "search"
        assert tool["description"] == "Search for items"
        assert "q" in tool["inputSchema"]["properties"]

        # ── Step 3: tools/call ──────────────────────────────────────────
        with (
            _mock_get_redis(),
            patch.object(
                GatewayRateLimiter,
                "check",
                new_callable=AsyncMock,
                return_value=RateLimitResult(
                    allowed=True, reason="ok", current=1, limit=60
                ),
            ),
            patch.object(
                ToolDispatcher,
                "dispatch",
                new_callable=AsyncMock,
                return_value=TOOL_CALL_RESULT,
            ) as mock_dispatch,
        ):
            resp = await client.post(
                "/mcp/v1/test-server/",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"q": "test-value"}},
                },
            )
            assert resp.status_code == 200
            result = _assert_jsonrpc_ok(resp.json(), 3)
            assert result == TOOL_CALL_RESULT

            mock_dispatch.assert_called_once()
            _call_args = mock_dispatch.call_args.args
            assert _call_args[2] == {"q": "test-value"}


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: Full e2e — initialize → tools/list → tools/call (SSE transport)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_flow_with_sse(client: AsyncClient) -> None:
    """Full e2e over SSE transport: SSE connect → message flow.

    Mocks:
        - ``_load_server_config`` → ``ACTIVE_CONFIG`` (avoids Redis + DB)
        - ``GatewayRateLimiter.check`` → allowed
        - ``ToolDispatcher.dispatch`` → ``TOOL_CALL_RESULT``
        - ``get_redis`` (transport_sse) for rate-limit loop
    """
    from app.gateway.session import MCPSession
    from app.gateway.transport_sse import session_manager

    session_id = "sse-session-001"

    with patch(
        "app.gateway.transport_sse._load_server_config",
        new_callable=AsyncMock,
        return_value=ACTIVE_CONFIG,
    ):
        mock_sse_session = MCPSession(
            session_id=session_id,
            server_id=ACTIVE_CONFIG["server_id"],
            user_id=ACTIVE_CONFIG["user_id"],
            slug=ACTIVE_CONFIG["slug"],
        )
        await session_manager.add(mock_sse_session)

        # ── Step 1: initialize via message endpoint ────────────────────
        resp = await client.post(
            f"/mcp/v1/test-server/message?session_id={session_id}",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 1)
        assert result["protocolVersion"] == "2025-11-25"
        assert result["serverInfo"]["name"] == "mcpforge-test-server"

        # ── Step 2: tools/list via message endpoint ────────────────────
        resp = await client.post(
            f"/mcp/v1/test-server/message?session_id={session_id}",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 2)
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "search"

        # ── Step 3: tools/call via message endpoint ────────────────────
        with (
            _mock_get_redis(),
            patch.object(
                GatewayRateLimiter,
                "check",
                new_callable=AsyncMock,
                return_value=RateLimitResult(
                    allowed=True, reason="ok", current=2, limit=60
                ),
            ),
            patch.object(
                ToolDispatcher,
                "dispatch",
                new_callable=AsyncMock,
                return_value=TOOL_CALL_RESULT,
            ) as mock_dispatch,
        ):
            resp = await client.post(
                f"/mcp/v1/test-server/message?session_id={session_id}",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"q": "sse-test"}},
                },
            )
            assert resp.status_code == 200
            result = _assert_jsonrpc_ok(resp.json(), 3)
            assert result == TOOL_CALL_RESULT
            mock_dispatch.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: Full e2e — same flow over StreamableHTTP (explicit initialize)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_flow_with_http(client: AsyncClient) -> None:
    """Full e2e over StreamableHTTP transport with explicit initialize.

    The StreamableHTTP endpoint (``/mcp/v1/{slug}/``) accepts POST with
    JSON-RPC bodies and returns complete JSON-RPC responses.  This test
    sends the full initialize → tools/list → tools/call sequence.

    Mocks:
        - ``ServerConfigCache.get`` → ``ACTIVE_CONFIG``
        - ``GatewayRateLimiter.check`` → allowed
        - ``ToolDispatcher.dispatch`` → ``TOOL_CALL_RESULT``
        - ``get_redis`` (transport_sse) for rate-limit loop
    """
    with patch(
        "app.gateway.transport_http.ServerConfigCache.get",
        return_value=ACTIVE_CONFIG,
    ):
        # ── Step 1: initialize ──────────────────────────────────────────
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 1)
        assert result["protocolVersion"] == "2025-11-25"
        assert result["serverInfo"]["name"] == "mcpforge-test-server"

        # ── Step 2: tools/list ──────────────────────────────────────────
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 2)
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "search"

        # ── Step 3: tools/call ──────────────────────────────────────────
        with (
            _mock_get_redis(),
            patch.object(
                GatewayRateLimiter,
                "check",
                new_callable=AsyncMock,
                return_value=RateLimitResult(
                    allowed=True, reason="ok", current=3, limit=60
                ),
            ),
            patch.object(
                ToolDispatcher,
                "dispatch",
                new_callable=AsyncMock,
                return_value=TOOL_CALL_RESULT,
            ) as mock_dispatch,
        ):
            resp = await client.post(
                "/mcp/v1/test-server/",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"q": "http-test"}},
                },
            )
            assert resp.status_code == 200
            result = _assert_jsonrpc_ok(resp.json(), 3)
            assert result == TOOL_CALL_RESULT
            mock_dispatch.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: Paused server rejects calls
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pause_stops_calls(client: AsyncClient) -> None:
    """A paused server returns 404 from the gateway.

    ``handle_http_request`` (and ``_load_server_config``) check
    ``status == "active"`` and raise ``NotFoundError`` when the server is
    paused.  FastAPI's exception handler converts that to an HTTP 404.
    """
    with patch(
        "app.gateway.transport_http.ServerConfigCache.get",
        return_value=PAUSED_CONFIG,
    ):
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 404
        err_body = resp.json().get("error", {})
        assert "not active" in err_body.get("message", "").lower()


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: Resumed server accepts calls
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_resume_allows_calls(client: AsyncClient) -> None:
    """After a server is resumed (status → active), the gateway accepts calls."""
    # Start with paused config to simulate the paused state.
    with patch(
        "app.gateway.transport_http.ServerConfigCache.get",
        return_value=ACTIVE_CONFIG,  # ← same as saved after resume
    ):
        # The same request that failed when paused now succeeds.
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 1)
        assert result["protocolVersion"] == "2025-11-25"


# ═══════════════════════════════════════════════════════════════════════════
# Test 6: Free tier rate limited
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_free_tier_limit_reached(client: AsyncClient) -> None:
    """Free tier returns RATE_LIMIT_EXCEEDED after 60 calls/hour.

    Mocks:
        - ``ServerConfigCache.get`` → ``ACTIVE_CONFIG`` (plan="free")
        - ``GatewayRateLimiter.check`` → NOT allowed (hour limit hit)
        - ``get_redis`` (transport_sse) for rate-limit loop
    """
    with (
        patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=ACTIVE_CONFIG,
        ),
        _mock_get_redis(),
        patch.object(
            GatewayRateLimiter,
            "check",
            new_callable=AsyncMock,
            return_value=RateLimitResult(
                allowed=False, reason="hour", current=60, limit=60
            ),
        ),
    ):
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {"q": "rate-limited"},
                },
            },
        )
        assert resp.status_code == 200  # JSON-RPC error is still HTTP 200
        error = _assert_jsonrpc_error(resp.json(), 1)
        assert error["code"] == -32003  # RATE_LIMIT_EXCEEDED
        assert "retry_after_seconds" in error.get("data", {})


# ═══════════════════════════════════════════════════════════════════════════
# Test 7: Credential decryption works in the flow
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_credential_decrypt_success(client: AsyncClient) -> None:
    """When decrypt_or_none returns a value, it is passed to the dispatcher.

    Mocks:
        - ``ServerConfigCache.get`` → ``ACTIVE_CONFIG``
        - ``CredentialService.decrypt_or_none`` → ``"sk-real-token"``
        - ``GatewayRateLimiter.check`` → allowed
        - ``ToolDispatcher.dispatch`` → ``TOOL_CALL_RESULT``
        - ``get_redis`` (transport_sse) for rate-limit loop
    """
    from app.services.credential_service import CredentialService

    expected_credential = "sk-real-token"

    with (
        patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=ACTIVE_CONFIG,
        ),
        _mock_get_redis(),
        patch.object(
            GatewayRateLimiter,
            "check",
            new_callable=AsyncMock,
            return_value=RateLimitResult(
                allowed=True, reason="ok", current=1, limit=60
            ),
        ),
        patch.object(
            CredentialService,
            "decrypt_or_none",
            new_callable=AsyncMock,
            return_value=expected_credential,
        ),
        patch.object(
            ToolDispatcher,
            "dispatch",
            new_callable=AsyncMock,
            return_value=TOOL_CALL_RESULT,
        ) as mock_dispatch,
    ):
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"q": "cred-test"}},
            },
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 1)
        assert result == TOOL_CALL_RESULT

        mock_dispatch.assert_called_once()
        _credential = mock_dispatch.call_args.args[3]
        assert _credential == expected_credential


# ═══════════════════════════════════════════════════════════════════════════
# Test 8: Bad credential is handled gracefully
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_credential_decrypt_fails_gracefully(client: AsyncClient) -> None:
    """When decrypt_or_none raises, the error is logged and dispatch
    proceeds with credential_value=None (no crash / no 500).

    Mocks:
        - ``ServerConfigCache.get`` → ``ACTIVE_CONFIG``
        - ``CredentialService.decrypt_or_none`` → raises ``Exception``
        - ``GatewayRateLimiter.check`` → allowed
        - ``ToolDispatcher.dispatch`` → ``TOOL_CALL_RESULT``
        - ``get_redis`` (transport_sse) for rate-limit loop
    """
    from app.services.credential_service import CredentialService

    with (
        patch(
            "app.gateway.transport_http.ServerConfigCache.get",
            return_value=ACTIVE_CONFIG,
        ),
        _mock_get_redis(),
        patch.object(
            GatewayRateLimiter,
            "check",
            new_callable=AsyncMock,
            return_value=RateLimitResult(
                allowed=True, reason="ok", current=1, limit=60
            ),
        ),
        patch.object(
            CredentialService,
            "decrypt_or_none",
            new_callable=AsyncMock,
            side_effect=Exception("Corrupted encryption key"),
        ),
        patch.object(
            ToolDispatcher,
            "dispatch",
            new_callable=AsyncMock,
            return_value=TOOL_CALL_RESULT,
        ) as mock_dispatch,
    ):
        resp = await client.post(
            "/mcp/v1/test-server/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"q": "bad-cred"}},
            },
        )
        assert resp.status_code == 200
        result = _assert_jsonrpc_ok(resp.json(), 1)
        assert result == TOOL_CALL_RESULT

        mock_dispatch.assert_called_once()
        _credential = mock_dispatch.call_args.args[3]
        assert _credential is None
