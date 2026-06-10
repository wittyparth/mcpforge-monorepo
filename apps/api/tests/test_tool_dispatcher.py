"""Tests for ToolDispatcher — MCP gateway request building and execution.

Covers the full dispatch lifecycle: GET/POST requests, path/query
parameter handling, auth header injection, 4xx/5xx upstream responses,
timeouts, and SSRF blocking.
"""

from __future__ import annotations

import json
import socket
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.core.exceptions import SSRFBlockedError, UpstreamError
from app.gateway.tool_dispatcher import ToolDispatcher


def _mock_addrinfo(ip: str) -> list[tuple]:
    """Return a fake ``getaddrinfo`` result tuple for *ip*."""
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0)),
    ]


@pytest.fixture
def dispatcher() -> ToolDispatcher:
    """Return a ``ToolDispatcher`` with the SSRF guard mocked to allow all URLs."""
    d = ToolDispatcher()
    d.ssrf_guard.assert_safe = AsyncMock(return_value=None)
    return d


@pytest.fixture
def server_config() -> dict:
    """A basic server configuration pointing to a public API."""
    return {
        "base_url": "https://api.example.com",
        "auth_scheme": "none",
    }


@pytest.fixture
def tool_config() -> dict:
    """A basic tool configuration for a GET search endpoint."""
    return {
        "name": "search_products",
        "method": "GET",
        "path": "/products/search",
        "parameters": [
            {
                "name": "q",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            },
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Basic GET with query params
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_basic_get(
    dispatcher: ToolDispatcher,
    server_config: dict,
    tool_config: dict,
) -> None:
    """A GET request with query parameters returns JSON successfully."""
    async with respx.mock:
        route = respx.get(
            "https://api.example.com/products/search?q=test",
        ).respond(200, json={"results": ["item1", "item2"]})

        result = await dispatcher.dispatch(
            server_config,
            tool_config,
            {"q": "test"},
        )

        assert route.called
        assert result["isError"] is False
        assert len(result["content"]) == 1
        assert "item1" in result["content"][0]["text"]


# ═══════════════════════════════════════════════════════════════════════
# Test 2: POST with JSON body
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_post_with_body(dispatcher: ToolDispatcher) -> None:
    """A POST request sends JSON body and returns the created resource."""
    server = {"base_url": "https://api.example.com", "auth_scheme": "none"}
    tool = {
        "name": "create_product",
        "method": "POST",
        "path": "/products",
        "parameters": [],
    }
    arguments = {"name": "Widget", "price": 9.99}

    async with respx.mock:
        route = respx.post("https://api.example.com/products").respond(
            201,
            json={"id": 1, "name": "Widget", "price": 9.99},
        )

        result = await dispatcher.dispatch(server, tool, arguments)

        assert route.called
        sent = route.calls[0].request
        assert sent.method == "POST"
        body = json.loads(sent.content)
        assert body["name"] == "Widget"
        assert body["price"] == 9.99
        assert result["isError"] is False


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Path params substitution
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_path_params(dispatcher: ToolDispatcher) -> None:
    """URL path parameters like ``{id}`` are substituted from arguments."""
    server = {"base_url": "https://api.example.com", "auth_scheme": "none"}
    tool = {
        "name": "get_user",
        "method": "GET",
        "path": "/users/{id}",
        "parameters": [
            {
                "name": "id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
            },
        ],
    }
    arguments = {"id": 42}

    async with respx.mock:
        route = respx.get("https://api.example.com/users/42").respond(
            200,
            json={"id": 42, "name": "Alice"},
        )

        result = await dispatcher.dispatch(server, tool, arguments)

        assert route.called
        assert result["isError"] is False
        assert "Alice" in result["content"][0]["text"]


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Query params passed correctly
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_query_params(
    dispatcher: ToolDispatcher,
    server_config: dict,
) -> None:
    """Multiple query parameters are passed to the upstream URL."""
    tool = {
        "name": "search",
        "method": "GET",
        "path": "/items",
        "parameters": [
            {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
            {"name": "page", "in": "query", "required": False, "schema": {"type": "integer"}},
            {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}},
        ],
    }

    async with respx.mock:
        route = respx.get(
            "https://api.example.com/items?q=hello&page=1&limit=10",
        ).respond(200, json={"items": []})

        result = await dispatcher.dispatch(
            server_config,
            tool,
            {"q": "hello", "page": 1, "limit": 10},
        )

        assert route.called
        assert result["isError"] is False


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Header auth (api_key)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_header_auth(
    dispatcher: ToolDispatcher,
    tool_config: dict,
) -> None:
    """The ``api_key`` auth scheme injects the correct custom header."""
    server = {
        "base_url": "https://api.example.com",
        "auth_scheme": "api_key",
        "auth_header_name": "X-API-Key",
    }
    arguments = {"q": "test"}
    credential = "my-api-key-123"

    async with respx.mock:
        route = respx.get(
            "https://api.example.com/products/search?q=test",
        ).respond(200, json={"ok": True})

        await dispatcher.dispatch(server, tool_config, arguments, credential)

        assert route.called
        sent = route.calls[0].request
        assert sent.headers.get("X-API-Key") == "my-api-key-123"
        assert sent.headers.get("User-Agent") == "MCPForge-Gateway/1.0"


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Bearer auth
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_bearer_auth(
    dispatcher: ToolDispatcher,
    tool_config: dict,
) -> None:
    """The ``bearer`` auth scheme injects ``Authorization: Bearer <token>``."""
    server = {
        "base_url": "https://api.example.com",
        "auth_scheme": "bearer",
    }
    arguments = {"q": "test"}
    credential = "tok_abc123"

    async with respx.mock:
        route = respx.get(
            "https://api.example.com/products/search?q=test",
        ).respond(200, json={"ok": True})

        await dispatcher.dispatch(server, tool_config, arguments, credential)

        assert route.called
        sent = route.calls[0].request
        assert sent.headers.get("Authorization") == "Bearer tok_abc123"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: 4xx upstream
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_4xx_upstream(
    dispatcher: ToolDispatcher,
    server_config: dict,
    tool_config: dict,
) -> None:
    """A 4xx upstream response returns content with ``isError: True``."""
    async with respx.mock:
        route = respx.get(
            "https://api.example.com/products/search?q=test",
        ).respond(404, json={"error": "not found"})

        result = await dispatcher.dispatch(
            server_config,
            tool_config,
            {"q": "test"},
        )

        assert route.called
        assert result["isError"] is True
        assert len(result["content"]) == 2
        assert result["content"][1]["text"] == "Upstream returned HTTP 404"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: 5xx upstream
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_5xx_upstream(
    dispatcher: ToolDispatcher,
    server_config: dict,
    tool_config: dict,
) -> None:
    """A 5xx upstream response raises ``UpstreamError``."""
    async with respx.mock:
        respx.get(
            "https://api.example.com/products/search?q=test",
        ).respond(502, text="Bad Gateway")

        with pytest.raises(UpstreamError):
            await dispatcher.dispatch(
                server_config,
                tool_config,
                {"q": "test"},
            )


# ═══════════════════════════════════════════════════════════════════════
# Test 9: Timeout
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_timeout(
    dispatcher: ToolDispatcher,
    server_config: dict,
    tool_config: dict,
) -> None:
    """An HTTP timeout raises ``UpstreamError`` with a descriptive message."""
    async def mock_send(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    dispatcher.client.send = mock_send  # type: ignore[method-assign]

    with pytest.raises(UpstreamError) as exc:
        await dispatcher.dispatch(
            server_config,
            tool_config,
            {"q": "test"},
        )
    assert "timed out" in str(exc.value).lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 10: SSRF blocked
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ssrf_blocked() -> None:
    """A URL pointing to an internal IP is blocked by the SSRF guard."""
    d = ToolDispatcher()
    server = {"base_url": "http://192.168.1.1", "auth_scheme": "none"}
    tool = {
        "name": "test",
        "method": "GET",
        "path": "/admin",
        "parameters": [],
    }

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(
                    return_value=_mock_addrinfo("192.168.1.1"),
                ),
            ),
        ),
        pytest.raises(SSRFBlockedError),
    ):
        await d.dispatch(server, tool, {})
