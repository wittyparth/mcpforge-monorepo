"""Tests for the MCP gateway response handler.

Covers content-type-aware processing (JSON, binary, HTML, text),
size limit enforcement, truncation, and upstream error classification.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.exceptions import UpstreamError
from app.gateway.response_handler import (
    MAX_RESPONSE_SIZE,
    UPSTREAM_MAX_SIZE,
    ResponseHandler,
)


@pytest.fixture
def handler() -> ResponseHandler:
    """Return a fresh ``ResponseHandler`` instance for each test."""
    return ResponseHandler()


# ---------------------------------------------------------------------------
# JSON responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_response(handler: ResponseHandler) -> None:
    """A JSON response should be parsed and returned as a ``dict``."""
    data = {"key": "value", "nested": [1, 2, 3]}
    response = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=json.dumps(data).encode("utf-8"),
    )

    result = await handler.handle(response)

    assert result.type == "json"
    assert result.content == data
    assert isinstance(result.content, dict)
    assert result.mime_type == "application/json"
    assert result.truncated is False
    assert result.status_code == 200
    assert result.response_size_bytes > 0


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_truncated_response(handler: ResponseHandler) -> None:
    """A response body larger than ``MAX_RESPONSE_SIZE`` should be truncated."""
    body = b"x" * (MAX_RESPONSE_SIZE + 5000)
    assert len(body) > MAX_RESPONSE_SIZE

    response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/plain"},
        content=body,
    )

    result = await handler.handle(response)

    assert result.type == "text"
    assert result.truncated is True
    assert result.response_size_bytes == len(body)
    assert len(str(result.content)) <= MAX_RESPONSE_SIZE


# ---------------------------------------------------------------------------
# Binary responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_binary_response(handler: ResponseHandler) -> None:
    """An ``image/png`` response should be base64-encoded."""
    raw_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Minimal PNG-like header
    response = httpx.Response(
        status_code=200,
        headers={"content-type": "image/png"},
        content=raw_bytes,
    )

    result = await handler.handle(response)

    assert result.type == "binary"
    assert result.mime_type == "image/png"
    assert result.truncated is False
    assert result.response_size_bytes == len(raw_bytes)
    # Content should be base64-encoded ASCII string.
    assert isinstance(result.content, str)
    assert result.content.isascii()


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_html_stripped(handler: ResponseHandler) -> None:
    """A ``text/html`` response should have HTML tags stripped."""
    html = "<html><body><h1>Hello</h1><p>World</p></body></html>"
    response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/html"},
        content=html.encode("utf-8"),
    )

    result = await handler.handle(response)

    assert result.type == "text"
    assert "Hello" in result.content
    assert "World" in result.content
    assert "<html>" not in result.content
    assert "<h1>" not in result.content
    assert result.mime_type == "text/html"
    assert result.truncated is False


# ---------------------------------------------------------------------------
# Plain text responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_response(handler: ResponseHandler) -> None:
    """A plain text response should be returned as-is."""
    text = "Hello, world!"
    response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/plain"},
        content=text.encode("utf-8"),
    )

    result = await handler.handle(response)

    assert result.type == "text"
    assert result.content == text
    assert result.mime_type == "text/plain"
    assert result.truncated is False
    assert result.status_code == 200


# ---------------------------------------------------------------------------
# 4xx responses (client errors — treated as content, not exception)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_4xx_response(handler: ResponseHandler) -> None:
    """A 4xx response should be processed as normal content (not raise)."""
    body = {"error": "not found", "status": 404}
    response = httpx.Response(
        status_code=404,
        headers={"content-type": "application/json"},
        content=json.dumps(body).encode("utf-8"),
    )

    result = await handler.handle(response)

    # Must NOT raise UpstreamError — the caller inspects status_code.
    assert result.type == "json"
    assert result.content == body
    assert result.status_code == 404
    assert result.truncated is False


# ---------------------------------------------------------------------------
# 5xx upstream errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_5xx_upstream_error(handler: ResponseHandler) -> None:
    """A 5xx response should raise ``UpstreamError``."""
    response = httpx.Response(
        status_code=502,
        headers={"content-type": "text/plain"},
        content=b"Bad Gateway",
    )

    with pytest.raises(UpstreamError) as exc_info:
        await handler.handle(response)

    assert "502" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Upstream response size limit (5 MB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_size_limit(handler: ResponseHandler) -> None:
    """A response with ``content-length`` exceeding 5 MB should be rejected."""
    response = httpx.Response(
        status_code=200,
        headers={
            "content-type": "text/plain",
            "content-length": str(UPSTREAM_MAX_SIZE + 1),
        },
        content=b"small body that should not be processed",
    )

    result = await handler.handle(response)

    assert result.type == "text"
    assert "exceeds maximum allowed size" in str(result.content)
    assert result.status_code == 200
    assert result.response_size_bytes == UPSTREAM_MAX_SIZE + 1
