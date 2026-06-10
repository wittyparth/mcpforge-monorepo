"""Tests for OpenAPIFetcher service (F1 — OpenAPI ingestion).

Uses ``respx`` to mock HTTP responses at the transport layer,
``unittest.mock.AsyncMock`` for all other dependencies (S3Client,
SpecRepository, SpecAnalyzer).

Test matrix (10 tests):
  1. fetch_from_url: valid OpenAPI 3.0 returns ``SpecUploadResponse``
  2. fetch_from_url: HTTP 404 raises ``UpstreamError``
  3. fetch_from_url: timeout raises ``FetchTimeoutError``
  4. fetch_from_url: loopback IP raises ``InvalidURLError``
  5. fetch_from_url: spec >5MB raises ``SpecTooLargeError``
  6. fetch_from_url: malformed JSON raises ``SpecParseError`` with line/column
  7. fetch_from_url: invalid spec (missing required fields) raises ``SpecValidationError``
  8. fetch_from_url: Swagger 2.0 raises ``UnsupportedSpecVersionError``
  9. fetch_from_url: dedup hit reuses existing spec, skips ``put_object``
  10. upload: file bytes parsed, deduped, stored in S3
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from app.core.exceptions import (
    FetchTimeoutError,
    InvalidURLError,
    SpecParseError,
    SpecTooLargeError,
    SpecValidationError,
    UnsupportedSpecVersionError,
    UpstreamError,
)
from app.schemas.openapi_spec import ToolDefinition

# ── Test data ──────────────────────────────────────────────────────────────

VALID_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List all users",
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}

SWAGGER_SPEC: dict[str, Any] = {
    "swagger": "2.0",
    "info": {"title": "Swagger API", "version": "1.0.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}

TOOL_DEFINITION = ToolDefinition(
    name="listUsers",
    description="List all users",
    input_schema={"type": "object", "properties": {}},
    http_method="GET",
    http_path="/users",
    operation_id="listUsers",
)

TOOL_LIST = [TOOL_DEFINITION]


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def user_id() -> UUID:
    return uuid4()


@pytest.fixture
def mock_s3() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_spec_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_analyzer() -> AsyncMock:
    m = AsyncMock()
    m.extract_tools.return_value = TOOL_LIST
    return m


@pytest.fixture
def fetcher(mock_s3: AsyncMock, mock_spec_repo: AsyncMock, mock_analyzer: AsyncMock):
    """Build an OpenAPIFetcher with all dependencies mocked.

    Must be imported inside the fixture to avoid circular/early import
    issues before the respx mock is active.
    """
    from app.services.openapi_fetcher import OpenAPIFetcher

    return OpenAPIFetcher(s3=mock_s3, spec_repo=mock_spec_repo, analyzer=mock_analyzer)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _spec_url() -> str:
    """A public-IP URL that passes SSRF validation without real DNS."""
    return "http://93.184.216.34/spec.json"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Valid spec — happy path
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_valid(
    fetcher: Any,
    user_id: UUID,
    mock_s3: AsyncMock,
    mock_spec_repo: AsyncMock,
    mock_analyzer: AsyncMock,
) -> None:
    """A valid OpenAPI 3.0 spec returns SpecUploadResponse with parsed tools."""
    url = _spec_url()
    body = json.dumps(VALID_SPEC).encode()

    with respx.mock:
        respx.get(url).respond(
            200, content=body, headers={"content-type": "application/json"},
        )
        mock_spec_repo.get_by_user_and_hash.return_value = None
        mock_spec_repo.create.return_value.id = uuid4()
        mock_spec_repo.create.return_value.title = "Test API"
        mock_spec_repo.create.return_value.version = "1.0.0"
        mock_spec_repo.create.return_value.openapi_version = "3.0.0"
        mock_spec_repo.create.return_value.endpoint_count = 1
        mock_spec_repo.create.return_value.spec_size_bytes = len(body)

        result = await fetcher.fetch_from_url(user_id, url, {})

    assert result.title == "Test API"
    assert result.version == "1.0.0"
    assert result.openapi_version == "3.0.0"
    assert result.endpoint_count == 1
    assert result.spec_size_bytes == len(body)
    assert len(result.tools) == 1
    assert result.tools[0].name == "listUsers"

    mock_s3.put_object.assert_awaited_once()
    mock_spec_repo.create.assert_awaited_once()
    mock_analyzer.extract_tools.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════
# 2. HTTP 404
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_http_404(
    fetcher: Any,
    user_id: UUID,
) -> None:
    """An upstream 404 raises UpstreamError with status code in message."""
    url = _spec_url()

    with respx.mock:
        respx.get(url).respond(404)

        with pytest.raises(UpstreamError) as exc:
            await fetcher.fetch_from_url(user_id, url, {})

    assert "404" in str(exc.value.message)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Timeout
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_timeout(
    fetcher: Any,
    user_id: UUID,
) -> None:
    """An httpx.TimeoutException is converted to FetchTimeoutError."""
    url = _spec_url()

    with respx.mock:
        route = respx.get(url)
        route.side_effect = httpx.TimeoutException("Connection timed out")

        with pytest.raises(FetchTimeoutError) as exc:
            await fetcher.fetch_from_url(user_id, url, {})

    assert "timeout" in str(exc.value.message).lower()


# ═══════════════════════════════════════════════════════════════════════════
# 4. SSRF — private / loopback IP
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_private_ip(
    fetcher: Any,
    user_id: UUID,
) -> None:
    """A URL resolving to 127.0.0.1 raises InvalidURLError with suggestion."""
    url = "http://127.0.0.1/spec.json"

    with pytest.raises(InvalidURLError) as exc:
        await fetcher.fetch_from_url(user_id, url, {})

    msg_lower = str(exc.value.message).lower()
    assert "private" in msg_lower or "loopback" in msg_lower
    assert exc.value.suggestion is not None


# ═══════════════════════════════════════════════════════════════════════════
# 5. Spec too large (>5 MB)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_too_large(
    fetcher: Any,
    user_id: UUID,
) -> None:
    """A spec exceeding MAX_SPEC_SIZE_BYTES raises SpecTooLargeError."""
    url = _spec_url()
    # 6 MB of garbage exceeds the 5 MB default limit
    body = b"x" * (6 * 1024 * 1024)

    with respx.mock:
        respx.get(url).respond(200, content=body)

        with pytest.raises(SpecTooLargeError) as exc:
            await fetcher.fetch_from_url(user_id, url, {})

    assert "max" in str(exc.value.message).lower()


# ═══════════════════════════════════════════════════════════════════════════
# 6. Malformed JSON
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_invalid_json(
    fetcher: Any,
    user_id: UUID,
) -> None:
    """Invalid JSON raises SpecParseError with line and column."""
    url = _spec_url()
    body = b'{"invalid": json}'

    with respx.mock:
        respx.get(url).respond(
            200, content=body, headers={"content-type": "application/json"},
        )

        with pytest.raises(SpecParseError) as exc:
            await fetcher.fetch_from_url(user_id, url, {})

    assert exc.value.line is not None
    assert exc.value.column is not None


# ═══════════════════════════════════════════════════════════════════════════
# 7. Invalid OpenAPI (missing required fields)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_invalid_openapi(
    fetcher: Any,
    user_id: UUID,
) -> None:
    """A spec missing required fields raises SpecValidationError with details."""
    url = _spec_url()
    # Missing "info" key — required by OpenAPI 3.0
    invalid_spec = {"openapi": "3.0.0", "paths": {}}
    body = json.dumps(invalid_spec).encode()

    with respx.mock:
        respx.get(url).respond(
            200, content=body, headers={"content-type": "application/json"},
        )

        with pytest.raises(SpecValidationError) as exc:
            await fetcher.fetch_from_url(user_id, url, {})

    assert len(exc.value.details) > 0
    assert any("info" in d.get("message", "") for d in exc.value.details)


# ═══════════════════════════════════════════════════════════════════════════
# 8. Swagger 2.0 (unsupported version)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_swagger(
    fetcher: Any,
    user_id: UUID,
) -> None:
    """A Swagger 2.0 spec raises UnsupportedSpecVersionError with suggestion."""
    url = _spec_url()
    body = json.dumps(SWAGGER_SPEC).encode()

    with respx.mock:
        respx.get(url).respond(
            200, content=body, headers={"content-type": "application/json"},
        )

        with pytest.raises(UnsupportedSpecVersionError) as exc:
            await fetcher.fetch_from_url(user_id, url, {})

    assert "swagger2openapi" in (exc.value.suggestion or "")


# ═══════════════════════════════════════════════════════════════════════════
# 9. Dedup — same hash found in DB
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fetch_from_url_dedup(
    fetcher: Any,
    user_id: UUID,
    mock_s3: AsyncMock,
    mock_spec_repo: AsyncMock,
    mock_analyzer: AsyncMock,
) -> None:
    """A spec whose hash matches an existing record reuses the old record."""
    url = _spec_url()
    body = json.dumps(VALID_SPEC).encode()
    spec_id = uuid4()

    existing_spec = AsyncMock()
    existing_spec.id = spec_id
    existing_spec.title = "Test API"
    existing_spec.version = "1.0.0"
    existing_spec.openapi_version = "3.0.0"
    existing_spec.endpoint_count = 1
    existing_spec.spec_size_bytes = len(body)
    existing_spec.r2_key = f"{user_id}/fakesha.json"

    # get_by_user_and_hash returns the existing spec
    mock_spec_repo.get_by_user_and_hash.return_value = existing_spec
    # get_object returns the original content
    mock_s3.get_object.return_value = body

    with respx.mock:
        respx.get(url).respond(
            200, content=body, headers={"content-type": "application/json"},
        )

        result = await fetcher.fetch_from_url(user_id, url, {})

    # Should NOT have stored a new object or created a new DB row
    mock_s3.put_object.assert_not_awaited()
    mock_spec_repo.create.assert_not_awaited()
    # Should have fetched the existing content and re-analyzed
    mock_s3.get_object.assert_awaited_once_with(existing_spec.r2_key)
    mock_analyzer.extract_tools.assert_awaited_once()

    assert result.spec_id == spec_id
    assert result.title == "Test API"
    assert result.endpoint_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# 10. Upload — file content
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_upload_file_content(
    fetcher: Any,
    user_id: UUID,
    mock_s3: AsyncMock,
    mock_spec_repo: AsyncMock,
    mock_analyzer: AsyncMock,
) -> None:
    """Uploaded file content is parsed, stored in S3, and tools extracted."""
    body = json.dumps(VALID_SPEC).encode()
    filename = "api-spec.json"

    mock_spec_repo.get_by_user_and_hash.return_value = None
    mock_spec_repo.create.return_value.id = uuid4()
    mock_spec_repo.create.return_value.title = "Test API"
    mock_spec_repo.create.return_value.version = "1.0.0"
    mock_spec_repo.create.return_value.openapi_version = "3.0.0"
    mock_spec_repo.create.return_value.endpoint_count = 1
    mock_spec_repo.create.return_value.spec_size_bytes = len(body)

    result = await fetcher.upload(user_id, body, filename)

    assert result.title == "Test API"
    assert result.version == "1.0.0"
    assert result.openapi_version == "3.0.0"
    assert result.endpoint_count == 1
    assert result.spec_size_bytes == len(body)
    assert len(result.tools) == 1

    mock_s3.put_object.assert_awaited_once()
    mock_spec_repo.create.assert_awaited_once()
    mock_analyzer.extract_tools.assert_awaited_once()
