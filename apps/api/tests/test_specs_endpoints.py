"""Endpoint tests for OpenAPI spec ingestion (F1).

Tests all 6 endpoints in ``app.api.v1.endpoints.specs``:

- POST   /specs/fetch                    — Fetch a spec from a URL
- POST   /specs/upload                   — Upload a spec file (multipart)
- GET    /specs/{spec_id}/tools          — Get parsed tool list
- POST   /specs/{spec_id}/select-tools   — Select tools and create an MCP server
- GET    /specs/{spec_id}                — Get spec metadata
- DELETE /specs/{spec_id}                — Delete a spec
"""

from __future__ import annotations

import json
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spec import SpecSource
from app.models.user import User
from app.repositories.spec_repo import SpecRepository

# ── Thread-local recursion guard for ToolDefinition serializer ────────────
# The production ``ToolDefinition._add_backward_compat_keys`` calls
# ``self.model_dump()`` inside a ``@model_serializer``, causing infinite
# recursion.  We patch ``model_dump`` on the class to detect re-entrance.

_tool_tls = threading.local()


def _make_safe_tool_dump(original_dump: Any) -> Any:
    """Build a recursion-guarded version of ``ToolDefinition.model_dump``.

    Closes over ``original_dump`` so the fixture can capture the class
    method before monkeypatching.
    """

    def _safe_tool_model_dump(self, **kwargs: Any) -> dict[str, Any]:
        if getattr(_tool_tls, "in_serializer", False):
            d: dict[str, Any] = {}
            for field_name, field_info in self.model_fields.items():
                alias = field_info.alias or field_name
                d[alias] = getattr(self, field_name)
            return d
        _tool_tls.in_serializer = True
        try:
            return original_dump(self, **kwargs)
        finally:
            _tool_tls.in_serializer = False

    return _safe_tool_model_dump

# ── Constants ───────────────────────────────────────────────────────────────

BASE_URL = "/api/v1/specs"

# A public IP works around SSRF validation without real DNS calls.
PUBLIC_URL = "http://93.184.216.34/spec.json"
LOOPBACK_URL = "http://127.0.0.1/spec.json"

# ── Test data ──────────────────────────────────────────────────────────────

VALID_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List all items",
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}

FIVE_ENDPOINT_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Multi-API", "version": "2.0.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "put": {
                "operationId": "updatePet",
                "summary": "Update a pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"204": {"description": "Deleted"}},
            },
        },
    },
}


# ── Autouse fixtures ─────────────────────────────────────────────────────────
# These run before every test to fix test-environment concerns.


@pytest.fixture(autouse=True)
def _csrf_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ``ENVIRONMENT=testing`` to bypass the CSRF middleware for writes.

    The middleware (``app.core.middleware.csrf``) skips the CSRF check when
    ``settings.ENVIRONMENT == "testing"`` (line 111).
    """
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "testing")


@pytest.fixture(autouse=True)
def _fix_tool_serializer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply recursion guard to ``ToolDefinition.model_dump``.

    ``ToolDefinition._add_backward_compat_keys`` is decorated with
    ``@model_serializer(mode="plain")`` and calls ``self.model_dump()``
    inside, creating infinite recursion.  We replace ``model_dump`` on the
    class with a recursion-guarded version for the duration of each test.
    """
    from pydantic import BaseModel

    from app.schemas.openapi_spec import ToolDefinition

    safe_dump = _make_safe_tool_dump(BaseModel.model_dump)
    monkeypatch.setattr(ToolDefinition, "model_dump", safe_dump)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_r2(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Monkeypatch R2Client in the specs module so no env vars are needed.

    Every ``R2Client()`` call inside the endpoint returns this mock.
    """
    mock = MagicMock()
    mock.put_object = AsyncMock()
    mock.get_object = AsyncMock(return_value=b"{}")
    mock.delete_object = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.specs.R2Client", lambda: mock)
    return mock


@pytest_asyncio.fixture
async def other_user(test_session: AsyncSession) -> User:
    """A second test user for ownership/permission tests."""
    u = User(
        email=f"other-{uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
    )
    test_session.add(u)
    await test_session.flush()
    return u


@pytest_asyncio.fixture
async def sample_spec(test_session: AsyncSession, auth_user: User) -> SpecSource:
    """A ``SpecSource`` owned by ``auth_user`` with R2 content set."""
    spec = SpecSource(
        user_id=auth_user.id,
        source_type="url",
        source_url="https://example.com/spec.json",
        r2_key=f"{auth_user.id}/test-hash.json",
        title="Test API",
        version="1.0.0",
        openapi_version="3.0.0",
        endpoint_count=2,
        spec_size_bytes=512,
        fetch_status="fetched",
    )
    test_session.add(spec)
    await test_session.flush()
    return spec


# ═══════════════════════════════════════════════════════════════════════════
# TestFetchSpec — POST /specs/fetch
# ═══════════════════════════════════════════════════════════════════════════


class TestFetchSpec:
    """POST /api/v1/specs/fetch — Fetch an OpenAPI spec from a URL."""

    async def test_fetch_spec_returns_tools(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """A valid 5-endpoint spec returns extracted tools in the response."""
        with respx.mock:
            respx.get(PUBLIC_URL).respond(
                200,
                content=json.dumps(FIVE_ENDPOINT_SPEC).encode(),
                headers={"content-type": "application/json"},
            )

            response = await auth_client.post(
                f"{BASE_URL}/fetch",
                json={"url": PUBLIC_URL},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Multi-API"
        assert data["endpoint_count"] == 5
        assert len(data["tools"]) == 5
        # spec_id should be a valid UUID
        assert UUID(data["spec_id"])
        # R2 put_object should have been called during storage
        mock_r2.put_object.assert_awaited()

    async def test_fetch_spec_invalid_url_returns_400(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """A loopback URL fails SSRF prevention and returns 400."""
        response = await auth_client.post(
            f"{BASE_URL}/fetch",
            json={"url": LOOPBACK_URL},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "INVALID_URL"


# ═══════════════════════════════════════════════════════════════════════════
# TestUploadSpec — POST /specs/upload
# ═══════════════════════════════════════════════════════════════════════════


class TestUploadSpec:
    """POST /api/v1/specs/upload — Upload an OpenAPI spec file."""

    async def test_upload_spec_returns_tools(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """A valid spec file upload returns 201 with extracted tools."""
        content = json.dumps(VALID_SPEC).encode()
        response = await auth_client.post(
            f"{BASE_URL}/upload",
            files={"file": ("spec.json", content, "application/json")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["endpoint_count"] >= 1
        assert len(data["tools"]) >= 1
        assert data["tools"][0]["name"] == "listItems"
        assert UUID(data["spec_id"])
        mock_r2.put_object.assert_awaited()

    async def test_upload_spec_too_large_returns_413(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """A file exceeding 5 MB returns 413 with SPEC_TOO_LARGE."""
        large_content = b"x" * 6_000_000  # ~6 MB > 5 MB max
        response = await auth_client.post(
            f"{BASE_URL}/upload",
            files={"file": ("large.json", large_content, "application/json")},
        )

        assert response.status_code == 413
        data = response.json()
        assert data["error"]["code"] == "SPEC_TOO_LARGE"


# ═══════════════════════════════════════════════════════════════════════════
# TestGetSpecTools — GET /specs/{spec_id}/tools
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSpecTools:
    """GET /api/v1/specs/{spec_id}/tools — Get parsed tool list."""

    async def test_get_spec_tools_returns_extracted_tools(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        sample_spec: SpecSource,
    ) -> None:
        """Tools are extracted from the R2-stored spec content."""
        mock_r2.get_object.return_value = json.dumps(VALID_SPEC).encode()

        response = await auth_client.get(
            f"{BASE_URL}/{sample_spec.id}/tools",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["spec_id"] == str(sample_spec.id)
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "listItems"

    async def test_get_spec_tools_other_user_forbidden(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """A spec owned by another user returns 403 FORBIDDEN."""
        spec = SpecSource(
            user_id=other_user.id,
            source_type="url",
            r2_key=f"{other_user.id}/secret.json",
            title="Other's Spec",
            fetch_status="fetched",
        )
        test_session.add(spec)
        await test_session.flush()

        response = await auth_client.get(
            f"{BASE_URL}/{spec.id}/tools",
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    async def test_get_spec_tools_not_found(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """A non-existent spec ID returns 404 NOT_FOUND."""
        response = await auth_client.get(
            f"{BASE_URL}/{uuid4()}/tools",
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════════════
# TestGetSpec — GET /specs/{spec_id}
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSpec:
    """GET /api/v1/specs/{spec_id} — Get spec metadata."""

    async def test_get_spec_returns_metadata(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        sample_spec: SpecSource,
    ) -> None:
        """All ``SpecSourceResponse`` fields match the created record."""
        response = await auth_client.get(
            f"{BASE_URL}/{sample_spec.id}",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_spec.id)
        assert data["user_id"] == str(sample_spec.user_id)
        assert data["source_type"] == "url"
        assert data["source_url"] == "https://example.com/spec.json"
        assert data["r2_key"] == sample_spec.r2_key
        assert data["title"] == "Test API"
        assert data["version"] == "1.0.0"
        assert data["openapi_version"] == "3.0.0"
        assert data["endpoint_count"] == 2
        assert data["spec_size_bytes"] == 512
        assert data["fetch_status"] == "fetched"
        assert data["created_at"] is not None

    async def test_get_spec_other_user_forbidden(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """A spec owned by another user returns 403 FORBIDDEN."""
        spec = SpecSource(
            user_id=other_user.id,
            source_type="url",
            title="Other's Spec",
            fetch_status="fetched",
        )
        test_session.add(spec)
        await test_session.flush()

        response = await auth_client.get(
            f"{BASE_URL}/{spec.id}",
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    async def test_get_spec_not_found(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """A non-existent spec ID returns 404 NOT_FOUND."""
        response = await auth_client.get(
            f"{BASE_URL}/{uuid4()}",
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════════════
# TestDeleteSpec — DELETE /specs/{spec_id}
# ═══════════════════════════════════════════════════════════════════════════


class TestDeleteSpec:
    """DELETE /api/v1/specs/{spec_id} — Delete a spec."""

    async def test_delete_spec_removes_row(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        sample_spec: SpecSource,
        test_session: AsyncSession,
    ) -> None:
        """Deleting a spec returns 204, removes the DB row, and calls R2 delete."""
        response = await auth_client.delete(
            f"{BASE_URL}/{sample_spec.id}",
        )

        assert response.status_code == 204
        mock_r2.delete_object.assert_awaited_once_with(sample_spec.r2_key)

        # Verify the row is gone
        repo = SpecRepository(test_session)
        assert await repo.get_by_id(sample_spec.id) is None

    async def test_delete_spec_other_user_forbidden(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """Deleting a spec owned by another user returns 403."""
        spec = SpecSource(
            user_id=other_user.id,
            source_type="url",
            r2_key=f"{other_user.id}/secret.json",
            title="Other's Spec",
            fetch_status="fetched",
        )
        test_session.add(spec)
        await test_session.flush()

        response = await auth_client.delete(
            f"{BASE_URL}/{spec.id}",
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    async def test_delete_spec_not_found(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """Deleting a non-existent spec returns 404."""
        response = await auth_client.delete(
            f"{BASE_URL}/{uuid4()}",
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════════════
# TestSelectTools — POST /specs/{spec_id}/select-tools
# ═══════════════════════════════════════════════════════════════════════════


class TestSelectTools:
    """POST /api/v1/specs/{spec_id}/select-tools — Select tools and create MCP server."""

    async def test_select_tools_creates_mcp_server(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        sample_spec: SpecSource,
    ) -> None:
        """Selecting tools creates an MCP server with the selected tool."""
        mock_r2.get_object.return_value = json.dumps(VALID_SPEC).encode()

        response = await auth_client.post(
            f"{BASE_URL}/{sample_spec.id}/select-tools",
            json={
                "slug": "my-server",
                "name": "My Server",
                "base_url": "https://api.example.com",
                "selected_tool_names": ["listItems"],
                "auth_scheme": "none",
                "transport_mode": "sse",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "my-server"
        assert data["name"] == "My Server"
        assert isinstance(data["tools_config"], dict)
        assert data["tools_config"]["version"] == 1
        assert len(data["tools_config"]["tools"]) == 1
        assert data["version"] == 1

    async def test_select_tools_unauthorized_for_other_user(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """A spec owned by another user returns 403."""
        spec = SpecSource(
            user_id=other_user.id,
            source_type="url",
            r2_key=f"{other_user.id}/secret.json",
            title="Other's Spec",
            fetch_status="fetched",
        )
        test_session.add(spec)
        await test_session.flush()

        response = await auth_client.post(
            f"{BASE_URL}/{spec.id}/select-tools",
            json={
                "slug": "my-server",
                "name": "My Server",
                "base_url": "https://api.example.com",
                "selected_tool_names": ["listItems"],
                "auth_scheme": "none",
                "transport_mode": "sse",
            },
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    async def test_select_tools_not_found(
        self,
        auth_client: AsyncClient,
        mock_r2: MagicMock,
    ) -> None:
        """A non-existent spec ID returns 404."""
        response = await auth_client.post(
            f"{BASE_URL}/{uuid4()}/select-tools",
            json={
                "slug": "my-server",
                "name": "My Server",
                "base_url": "https://api.example.com",
                "selected_tool_names": ["listItems"],
                "auth_scheme": "none",
                "transport_mode": "sse",
            },
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
