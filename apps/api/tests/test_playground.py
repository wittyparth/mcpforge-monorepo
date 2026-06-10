"""Playground endpoint tests.

Tests both:
  1. REST share-link API (POST …/playground/share)
  2. WebSocket MCP-over-WS handler (``/ws/playground/{slug}``)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_db
from app.core.config import settings
from app.gateway.tool_dispatcher import ToolDispatcher
from app.main import app
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.playground.ws import _sessions

# ═══════════════════════════════════════════════════════════════════════════
# REST share-link tests  (existing)
# ═══════════════════════════════════════════════════════════════════════════

SHARE_URL = "/api/v1/servers/{slug}/playground/share"
SENSITIVE_KEYS = {"api_key", "password", "token", "authorization"}
SENSITIVE_ARG_DATA: dict[str, object] = {
    "user_id": 42,
    "api_key": "sk-secret-123",
    "password": "hunter2",
    "format": "json",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _redis_ctx():
    """Context manager that patches both ``get_redis_pool`` and ``Redis.from_pool``.

    Yields ``(fake_pool, fake_redis)`` so callers can assert on the mocks.
    """
    fake_pool, fake_redis = AsyncMock(), AsyncMock()
    return (
        patch(
            "app.api.v1.endpoints.playground.get_redis_pool",
            return_value=fake_pool,
        ),
        patch(
            "app.api.v1.endpoints.playground.Redis.from_pool",
            return_value=fake_redis,
        ),
        fake_redis,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def owned_server(test_session: AsyncSession, auth_user: User) -> MCPServer:
    """Create a test MCP server owned by ``auth_user``."""
    server = MCPServer(
        user_id=auth_user.id,
        slug=f"test-server-{uuid4().hex[:6]}",
        name="Test Server",
        base_url="https://api.example.com",
        status="active",
    )
    test_session.add(server)
    await test_session.flush()
    return server


@pytest.fixture
async def other_user(test_session: AsyncSession) -> User:
    """Create a second test user who does NOT own ``owned_server``."""
    u = User(
        email=f"other-{uuid4().hex[:8]}@example.com",
        password_hash="other-hash",
    )
    test_session.add(u)
    await test_session.flush()
    return u


@pytest.fixture
async def unowned_server(test_session: AsyncSession, other_user: User) -> MCPServer:
    """Create a server owned by ``other_user`` (not ``auth_user``)."""
    server = MCPServer(
        user_id=other_user.id,
        slug=f"other-server-{uuid4().hex[:6]}",
        name="Other's Server",
        base_url="https://api.other.com",
        status="active",
    )
    test_session.add(server)
    await test_session.flush()
    return server


# ── Share endpoint tests ─────────────────────────────────────────────────────


class TestCreateShareLink:
    """POST /api/v1/servers/{slug}/playground/share"""

    SHARE_PAYLOAD: dict[str, object] = {
        "tool_name": "get_users",
        "arguments": {"user_id": 123, "include_deleted": False},
    }

    # ── Happy path ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_share_success(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Returns 201 with share_id, url, and expires_at."""
        fake_pool, fake_redis, _ = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            response = await auth_client.post(url, json=self.SHARE_PAYLOAD)

        assert response.status_code == 201
        data = response.json()
        assert "share_id" in data
        assert "url" in data
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_create_share_url_format(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """URL follows the expected pattern."""
        fake_pool, fake_redis, _ = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            response = await auth_client.post(url, json=self.SHARE_PAYLOAD)

        data = response.json()
        expected_prefix = f"/dashboard/servers/{owned_server.slug}/playground?share="
        assert data["url"].startswith(expected_prefix)
        assert data["url"].endswith(data["share_id"])

    @pytest.mark.asyncio
    async def test_create_share_expires_at(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """expires_at is in the near future (within 48 h of now)."""
        fake_pool, fake_redis, _ = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            response = await auth_client.post(url, json=self.SHARE_PAYLOAD)

        data = response.json()
        expires = datetime.fromisoformat(data["expires_at"])
        now = datetime.now(UTC)
        assert now < expires
        assert (expires - now).total_seconds() < 48 * 3600  # within 48 h

    @pytest.mark.asyncio
    async def test_create_share_custom_expiry(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Custom expires_in_hours is honored."""
        fake_pool, fake_redis, _ = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            response = await auth_client.post(
                url,
                json={"tool_name": "x", "arguments": {}, "expires_in_hours": 6},
            )

        data = response.json()
        expires = datetime.fromisoformat(data["expires_at"])
        now = datetime.now(UTC)
        diff_hours = (expires - now).total_seconds() / 3600
        assert 5.5 <= diff_hours <= 7  # approx 6 h (allow clock skew)

    @pytest.mark.asyncio
    async def test_create_share_empty_arguments(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Empty arguments dict works fine."""
        fake_pool, fake_redis, _ = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            response = await auth_client.post(
                url,
                json={"tool_name": "ping", "arguments": {}},
            )

        assert response.status_code == 201

    # ── Credential stripping ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_share_credentials_stripped(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Sensitive keys are stripped from stored arguments."""
        fake_pool, fake_redis, mock_redis = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            await auth_client.post(url, json={"tool_name": "x", "arguments": SENSITIVE_ARG_DATA})

        assert mock_redis.setex.called
        _call_args = mock_redis.setex.call_args
        stored_json = _call_args[0][2]  # third positional arg = data JSON
        stored = json.loads(stored_json)

        # sensitive keys must NOT be in stored arguments
        for key in SENSITIVE_KEYS:
            assert key not in stored["arguments"], f"{key} should have been stripped"

        # non-sensitive keys must survive
        assert stored["arguments"]["user_id"] == 42
        assert stored["arguments"]["format"] == "json"

    @pytest.mark.asyncio
    async def test_create_share_no_credentials_unchanged(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Arguments with no sensitive keys pass through unchanged."""
        safe_args = {"user_id": 1, "limit": 10}
        fake_pool, fake_redis, mock_redis = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            await auth_client.post(url, json={"tool_name": "x", "arguments": safe_args})

        stored = json.loads(mock_redis.setex.call_args[0][2])
        assert stored["arguments"] == safe_args

    # ── Redis TTL ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_share_redis_ttl(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Redis setex is called with TTL matching expires_in_hours."""
        fake_pool, fake_redis, mock_redis = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            await auth_client.post(
                url,
                json={"tool_name": "x", "arguments": {}, "expires_in_hours": 12},
            )

        assert mock_redis.setex.called
        _key, ttl, _data = mock_redis.setex.call_args[0]
        assert ttl == 12 * 3600  # 12 h in seconds
        assert _key.startswith("playground_share:")

    @pytest.mark.asyncio
    async def test_create_share_redis_key_format(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Redis key follows ``playground_share:{share_id}`` pattern."""
        fake_pool, fake_redis, mock_redis = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            response = await auth_client.post(url, json=self.SHARE_PAYLOAD)

        share_id = response.json()["share_id"]
        stored_key = mock_redis.setex.call_args[0][0]
        expected_key = f"playground_share:{share_id}"
        assert stored_key == expected_key

    # ── Error cases ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_share_server_not_found(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Returns 404 when slug does not exist."""
        fake_pool, fake_redis, _ = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug="nonexistent-slug")
            response = await auth_client.post(url, json=self.SHARE_PAYLOAD)

        assert response.status_code == 404
        err = response.json()["error"]
        assert err["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_create_share_forbidden(
        self,
        auth_client: AsyncClient,
        unowned_server: MCPServer,
    ) -> None:
        """Returns 403 when server belongs to another user."""
        fake_pool, fake_redis, _ = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=unowned_server.slug)
            response = await auth_client.post(url, json=self.SHARE_PAYLOAD)

        assert response.status_code == 403
        err = response.json()["error"]
        assert err["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_create_share_unauthenticated(
        self,
        client: AsyncClient,
        owned_server: MCPServer,
    ) -> None:
        """Returns 401 without authentication."""
        url = SHARE_URL.format(slug=owned_server.slug)
        response = await client.post(url, json=self.SHARE_PAYLOAD)

        assert response.status_code == 401
        err = response.json()["error"]
        assert err["code"] == "UNAUTHORIZED"

    # ── Stored payload integrity ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_share_stored_payload(
        self,
        auth_client: AsyncClient,
        owned_server: MCPServer,
        auth_user: User,
    ) -> None:
        """Full stored payload in Redis is correct."""
        args = {"user_id": 99, "format": "csv"}
        fake_pool, fake_redis, mock_redis = _redis_ctx()
        with fake_pool, fake_redis:
            url = SHARE_URL.format(slug=owned_server.slug)
            await auth_client.post(
                url,
                json={"tool_name": "export", "arguments": args},
            )

        stored = json.loads(mock_redis.setex.call_args[0][2])
        assert stored["tool_name"] == "export"
        assert stored["arguments"] == args
        assert stored["server_slug"] == owned_server.slug
        assert stored["server_id"] == str(owned_server.id)
        assert stored["user_id"] == str(auth_user.id)


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket MCP-over-WS tests  (new)
# ═══════════════════════════════════════════════════════════════════════════

USER_ID = "00000000-0000-0000-0000-000000000001"
SERVER_ID = "00000000-0000-0000-0000-000000000010"
SLUG = "test-server"

ACTIVE_CONFIG: dict[str, Any] = {
    "server_id": SERVER_ID,
    "user_id": USER_ID,
    "slug": SLUG,
    "name": "Test Server",
    "base_url": "https://api.example.com",
    "auth_scheme": "none",
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
            },
            {
                "name": "echo",
                "description": "Echo back input",
                "ai_enhanced_name": "echo_enhanced",
                "ai_enhanced_description": "Echo back the input message with style",
                "method": "POST",
                "path": "/echo",
                "inputSchema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            },
        ]
    },
    "status": "active",
    "plan": "free",
}

DRAFT_CONFIG: dict[str, Any] = {
    **ACTIVE_CONFIG,
    "status": "building",
    "tools_config": {
        "tools": [
            {
                "name": "draft-tool",
                "description": "A tool still in development",
                "method": "GET",
                "path": "/draft",
                "inputSchema": {
                    "type": "object",
                    "properties": {"param": {"type": "string"}},
                },
            }
        ]
    },
}

ANOTHER_USER_CONFIG: dict[str, Any] = {
    **ACTIVE_CONFIG,
    "user_id": "00000000-0000-0000-0000-000000009999",
}

TOOL_CALL_RESULT: dict[str, Any] = {
    "content": [{"type": "text", "text": '{"results": ["item1"]}'}],
    "isError": False,
}

INVALID_TOKEN_PAYLOAD: dict[str, Any] = {"sub": USER_ID, "type": "refresh"}

WS_PATH = f"/ws/playground/{SLUG}"


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _ws_reset_sessions() -> None:
    """Reset in-memory sessions before and after each WebSocket test."""
    _sessions.clear()
    yield
    _sessions.clear()


@pytest.fixture(autouse=True)
def _ws_test_env() -> None:
    """Force testing mode."""
    settings.ENVIRONMENT = "testing"


@pytest.fixture(autouse=True)
def _ws_mock_db() -> None:
    """Override ``get_db`` so WS tests never touch a real database.

    The override yields a plain ``AsyncMock`` which is never actually
    called because all DB code paths are mocked at a higher level.
    """

    async def _mock_get_db() -> Any:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _mock_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def ws_client() -> TestClient:
    """Provide a synchronous TestClient for WebSocket tests.

    Uses Starlette's ``TestClient`` (not ``httpx.AsyncClient``) because
    ``httpx`` does not support WebSocket.
    """
    return TestClient(app)


@pytest.fixture
def mock_redis_ok() -> None:
    """Mock Redis so the normal code path through ``ServerConfigCache.get`` works."""
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    with (
        patch("app.playground.ws.get_redis_pool", return_value=AsyncMock()),
        patch("redis.asyncio.Redis.from_pool", return_value=mock_redis),
    ):
        yield


@pytest.fixture
def mock_redis_fail() -> None:
    """Mock Redis to raise, forcing a fallback to DB loading."""
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()

    def _fail(*args: Any, **kwargs: Any) -> Any:
        raise ConnectionError("Redis unavailable")

    with (
        patch("app.playground.ws.get_redis_pool", side_effect=_fail),
        patch("redis.asyncio.Redis.from_pool", return_value=mock_redis),
    ):
        yield


# ── Helpers ───────────────────────────────────────────────────────────────


def _assert_jsonrpc_result(
    data: dict[str, Any],
    expected_id: int | str | None,
) -> dict[str, Any]:
    """Assert a JSON-RPC 2.0 success response and return the ``result`` dict."""
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == expected_id
    assert "result" in data
    return data["result"]


def _assert_jsonrpc_error(
    data: dict[str, Any],
    expected_id: int | str | None,
) -> dict[str, Any]:
    """Assert a JSON-RPC 2.0 error response and return the ``error`` dict."""
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == expected_id
    assert "error" in data
    return data["error"]


# ── Test 1: Successful connection ──────────────────────────────────────────


@pytest.mark.usefixtures("mock_redis_ok")
class TestWebSocketPlayground:
    """WebSocket MCP Playground handler tests."""

    # ═════════════════════════════════════════════════════════════════
    # Connection & Auth
    # ═════════════════════════════════════════════════════════════════

    def _decode_ok(self) -> dict[str, Any]:
        return {"sub": USER_ID, "type": "access"}

    def test_connect_success_receives_tools_list(self, ws_client: TestClient) -> None:
        """Connect with a valid JWT → receives ``tools/list`` response immediately."""
        mock_decode = patch("app.playground.ws.decode_token", return_value=self._decode_ok())
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            data = ws.receive_text()
            result = _assert_jsonrpc_result(json.loads(data), 0)
            assert "tools" in result
            assert len(result["tools"]) == 2
            tools_by_name = {t["name"]: t for t in result["tools"]}
            assert "search" in tools_by_name
            assert tools_by_name["search"]["description"] == "Search for items"
            assert "q" in tools_by_name["search"]["inputSchema"]["properties"]

    def test_connect_missing_token_closes_ws(self, ws_client: TestClient) -> None:
        """Connect without ``token`` → error frame, then WS closes."""
        with ws_client.websocket_connect(f"/ws/playground/{SLUG}") as ws:
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 0)
            assert error["code"] == -32001
            assert "token" in error["message"].lower()

            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    def test_connect_invalid_token_closes_ws(self, ws_client: TestClient) -> None:
        """Connect with a malformed / expired JWT → error, then WS closes."""
        mock_decode = patch(
            "app.playground.ws.decode_token",
            side_effect=JWTError("JWT expired"),
        )
        with mock_decode, ws_client.websocket_connect(
            f"{WS_PATH}?token=expired-jwt",
        ) as ws:
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 0)
            msg = error["message"].lower()
            assert "expired" in msg or "invalid" in msg

            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    def test_connect_refresh_token_rejected(self, ws_client: TestClient) -> None:
        """Token with ``type=refresh`` → rejected."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=INVALID_TOKEN_PAYLOAD,
        )
        with mock_decode, ws_client.websocket_connect(
            f"{WS_PATH}?token=refresh-jwt",
        ) as ws:
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 0)
            assert "token" in error["message"].lower()

            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    def test_connect_server_not_found(self, ws_client: TestClient) -> None:
        """Non-existent slug → error, then WS closes."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch("app.playground.ws.ServerConfigCache.get", return_value=None)
        mock_draft = patch("app.playground.ws._load_server_draft", return_value=None)
        with mock_decode, mock_cache, mock_draft, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 0)
            assert error["code"] == -32001
            assert "not found" in error["message"].lower()

            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    def test_connect_ownership_mismatch(self, ws_client: TestClient) -> None:
        """Server owned by another user → error (returned as 'not found')."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get",
            return_value=ANOTHER_USER_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 0)
            assert error["code"] == -32001
            assert "not found" in error["message"].lower()

            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()

    # ═════════════════════════════════════════════════════════════════
    # Protocol: ping / pong
    # ═════════════════════════════════════════════════════════════════

    def test_ping_pong(self, ws_client: TestClient) -> None:
        """Send ``ping`` → receive ``pong``."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text(
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            )
            data = ws.receive_text()
            result = _assert_jsonrpc_result(json.loads(data), 1)
            assert result == {}

    # ═════════════════════════════════════════════════════════════════
    # Protocol: tools/call
    # ═════════════════════════════════════════════════════════════════

    def test_tools_call_success(self, ws_client: TestClient) -> None:
        """Call a known tool → dispatches via ``ToolDispatcher.dispatch``."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        mock_dispatch = patch.object(
            ToolDispatcher, "dispatch",
            new_callable=AsyncMock,
            return_value=TOOL_CALL_RESULT,
        )
        with mock_decode, mock_cache, mock_dispatch as md, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"q": "test"}},
                }),
            )
            data = ws.receive_text()
            result = _assert_jsonrpc_result(json.loads(data), 2)
            assert result["content"] == TOOL_CALL_RESULT["content"]
            assert "_meta" in result
            assert "elapsed_ms" in result["_meta"]

            md.assert_called_once()
            _, kwargs = md.call_args
            assert kwargs["tool_config"]["name"] == "search"
            assert kwargs["arguments"] == {"q": "test"}

    def test_tools_call_unknown_tool_yields_error(self, ws_client: TestClient) -> None:
        """Call a tool that does not exist → ``TOOL_NOT_FOUND``."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "nonexistent-tool", "arguments": {}},
                }),
            )
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 3)
            assert error["code"] == -32001  # TOOL_NOT_FOUND
            assert "nonexistent-tool" in error["message"]

    def test_tools_call_missing_name_yields_error(self, ws_client: TestClient) -> None:
        """``tools/call`` without ``name`` param → ``INVALID_PARAMS``."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"arguments": {}},
                }),
            )
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 4)
            assert error["code"] == -32602  # INVALID_PARAMS
            assert "name" in error["message"].lower()

    def test_tools_call_dispatch_failure_yields_internal_error(
        self, ws_client: TestClient,
    ) -> None:
        """When ``ToolDispatcher.dispatch`` raises → ``INTERNAL_ERROR`` w/ timing."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        mock_dispatch = patch.object(
            ToolDispatcher, "dispatch",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Upstream API unreachable"),
        )
        with mock_decode, mock_cache, mock_dispatch, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"q": "fail"}},
                }),
            )
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 7)
            assert error["code"] == -32603  # INTERNAL_ERROR
            assert "unreachable" in error["message"]
            assert "elapsed_ms" in error.get("data", {})

    # ═════════════════════════════════════════════════════════════════
    # Protocol: unknown method
    # ═════════════════════════════════════════════════════════════════

    def test_unknown_method_yields_error(self, ws_client: TestClient) -> None:
        """Unsupported method → ``METHOD_NOT_FOUND``."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/describe",
                    "params": {},
                }),
            )
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), 5)
            assert error["code"] == -32601  # METHOD_NOT_FOUND
            assert "tools/describe" in error["message"]

    # ═════════════════════════════════════════════════════════════════
    # Error handling: malformed input
    # ═════════════════════════════════════════════════════════════════

    def test_invalid_json_yields_parse_error(self, ws_client: TestClient) -> None:
        """Malformed JSON → ``PARSE_ERROR``."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text("this is not json")
            data = ws.receive_text()
            error = _assert_jsonrpc_error(json.loads(data), None)
            assert error["code"] == -32700  # PARSE_ERROR
            assert "json" in error["message"].lower()

    # ═════════════════════════════════════════════════════════════════
    # Pre-deployment mode
    # ═════════════════════════════════════════════════════════════════

    @pytest.mark.usefixtures("mock_redis_fail")
    def test_pre_deployment_loads_from_db(self, ws_client: TestClient) -> None:
        """Server with ``status=building`` → loads draft ``tools_config`` from DB.

        When Redis is unavailable (or returns ``None``), the handler
        falls back to ``_load_server_draft``.
        """
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_draft = patch(
            "app.playground.ws._load_server_draft", return_value=DRAFT_CONFIG,
        )
        with mock_decode, mock_draft, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            data = ws.receive_text()
            result = _assert_jsonrpc_result(json.loads(data), 0)
            assert len(result["tools"]) == 1
            assert result["tools"][0]["name"] == "draft-tool"

    # ═════════════════════════════════════════════════════════════════
    # AI-enhanced names
    # ═════════════════════════════════════════════════════════════════

    def test_tools_list_uses_ai_enhanced_names(self, ws_client: TestClient) -> None:
        """Tools with ``ai_enhanced_name`` → used instead of original name."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            data = ws.receive_text()
            result = _assert_jsonrpc_result(json.loads(data), 0)
            tools_by_name = {t["name"]: t for t in result["tools"]}

            # "echo" → "echo_enhanced" (ai_enhanced_name)
            assert "echo_enhanced" in tools_by_name
            echo = tools_by_name["echo_enhanced"]
            assert "style" in echo["description"]  # ai_enhanced_description

            # Original name should NOT appear
            assert "echo" not in tools_by_name

    def test_tools_call_by_ai_enhanced_name(self, ws_client: TestClient) -> None:
        """Call a tool by its ``ai_enhanced_name`` → correct original dispatched."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        mock_dispatch = patch.object(
            ToolDispatcher, "dispatch",
            new_callable=AsyncMock,
            return_value=TOOL_CALL_RESULT,
        )
        with mock_decode, mock_cache, mock_dispatch as md, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {
                        "name": "echo_enhanced",
                        "arguments": {"message": "hello"},
                    },
                }),
            )
            data = ws.receive_text()
            result = _assert_jsonrpc_result(json.loads(data), 6)
            assert result["content"] == TOOL_CALL_RESULT["content"]

            # Dispatcher receives the ORIGINAL tool config (name="echo")
            md.assert_called_once()
            _, kwargs = md.call_args
            assert kwargs["tool_config"]["name"] == "echo"

    # ═════════════════════════════════════════════════════════════════
    # Session lifecycle
    # ═════════════════════════════════════════════════════════════════

    def test_session_cleanup_on_disconnect(self, ws_client: TestClient) -> None:
        """On WebSocket close → session removed from in-memory dict."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        assert len(_sessions) == 0
        with mock_decode, mock_cache, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list
            assert len(_sessions) == 1

        # After disconnect
        assert len(_sessions) == 0

    def test_session_call_counter(self, ws_client: TestClient) -> None:
        """Session ``call_count`` increments after each ``tools/call``."""
        mock_decode = patch(
            "app.playground.ws.decode_token", return_value=self._decode_ok(),
        )
        mock_cache = patch(
            "app.playground.ws.ServerConfigCache.get", return_value=ACTIVE_CONFIG,
        )
        mock_dispatch = patch.object(
            ToolDispatcher, "dispatch",
            new_callable=AsyncMock,
            return_value=TOOL_CALL_RESULT,
        )
        with mock_decode, mock_cache, mock_dispatch, ws_client.websocket_connect(
            f"{WS_PATH}?token=valid-jwt",
        ) as ws:
            ws.receive_text()  # consume initial tools/list
            session_id = list(_sessions.keys())[0]
            assert _sessions[session_id].call_count == 0

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"q": "a"}},
                }),
            )
            ws.receive_text()  # result
            assert _sessions[session_id].call_count == 1

            ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"q": "b"}},
                }),
            )
            ws.receive_text()  # result
            assert _sessions[session_id].call_count == 2
