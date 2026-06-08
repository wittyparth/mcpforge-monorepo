"""Build pipeline endpoint tests.

Tests for the 4 build endpoints:
- POST /api/v1/servers/{server_id}/build          (F1 minimal)
- GET  /api/v1/servers/{server_id}/build-status   (SSE stream)
- POST /api/v1/servers/{server_id}/tools/accept   (501 stub)
- POST /api/v1/servers/{server_id}/deploy         (501 stub)
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.repositories.mcp_server_repo import MCPServerRepository

# Bypass CSRF middleware in tests: the middleware skips enforcement when
# ENVIRONMENT == "testing" (see app/core/middleware/csrf.py:111).
settings.ENVIRONMENT = "testing"

BASE_URL = "/api/v1/servers"


@pytest_asyncio.fixture
async def other_user(test_session: AsyncSession) -> User:
    """Create a second test user (not auth_user) for 403 tests."""
    u = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
    )
    test_session.add(u)
    await test_session.flush()
    return u


class TestStartBuild:
    """POST /api/v1/servers/{server_id}/build"""

    @pytest.mark.asyncio
    async def test_start_build_marks_server_active(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """Verify a server transitions from 'building' to 'active'."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=auth_user.id,
            slug=f"build-active-{uuid.uuid4().hex[:8]}",
            name="Build Active Test",
            base_url="https://api.example.com",
        )
        assert server.status == "building"

        response = await auth_client.post(f"{BASE_URL}/{server.id}/build")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

        # Verify persistence in the database
        refreshed = await repo.get_by_id(server.id)
        assert refreshed is not None
        assert refreshed.status == "active"

    @pytest.mark.asyncio
    async def test_start_build_other_user_forbidden(
        self,
        auth_client: AsyncClient,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """Verify a user cannot build another user's server."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=other_user.id,
            slug=f"build-forbid-{uuid.uuid4().hex[:8]}",
            name="Forbidden Build Server",
            base_url="https://other.example.com",
        )

        response = await auth_client.post(f"{BASE_URL}/{server.id}/build")
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["error"]["code"] == "FORBIDDEN"


class TestBuildStatusSSE:
    """GET /api/v1/servers/{server_id}/build-status"""

    @pytest.mark.asyncio
    async def test_build_status_returns_sse_event(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """Verify the SSE stream returns a single parsing-complete event."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=auth_user.id,
            slug=f"build-sse-{uuid.uuid4().hex[:8]}",
            name="Build SSE Test",
            base_url="https://api.example.com",
        )

        response = await auth_client.get(f"{BASE_URL}/{server.id}/build-status")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type

        body = response.text
        assert "data:" in body
        assert "parsing" in body
        assert "100" in body

    @pytest.mark.asyncio
    async def test_build_status_other_user_forbidden(
        self,
        auth_client: AsyncClient,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """Verify a user cannot check build status of another user's server."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=other_user.id,
            slug=f"build-sse-forbid-{uuid.uuid4().hex[:8]}",
            name="SSE Forbidden Server",
            base_url="https://other.example.com",
        )

        response = await auth_client.get(f"{BASE_URL}/{server.id}/build-status")
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["error"]["code"] == "FORBIDDEN"


class TestStubs:
    """501 stub endpoints (accept + deploy)."""

    @pytest.mark.asyncio
    async def test_accept_ai_enhancements_returns_501(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """Verify accept endpoint returns 501 NOT_IMPLEMENTED."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=auth_user.id,
            slug=f"accept-501-{uuid.uuid4().hex[:8]}",
            name="Accept 501 Test",
            base_url="https://api.example.com",
        )

        response = await auth_client.post(
            f"{BASE_URL}/{server.id}/tools/accept"
        )
        assert response.status_code == 501
        error_data = response.json()
        assert error_data["error"]["code"] == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_deploy_server_returns_501(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """Verify deploy endpoint returns 501 NOT_IMPLEMENTED."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=auth_user.id,
            slug=f"deploy-501-{uuid.uuid4().hex[:8]}",
            name="Deploy 501 Test",
            base_url="https://api.example.com",
        )

        response = await auth_client.post(f"{BASE_URL}/{server.id}/deploy")
        assert response.status_code == 501
        error_data = response.json()
        assert error_data["error"]["code"] == "NOT_IMPLEMENTED"


class TestBuildNonExistent:
    """POST /api/v1/servers/{server_id}/build with non-existent server."""

    @pytest.mark.asyncio
    async def test_start_build_nonexistent_server_returns_404(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Building a server that does not exist should return 404."""
        fake_id = uuid.uuid4()
        response = await auth_client.post(f"{BASE_URL}/{fake_id}/build")
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["error"]["code"] == "NOT_FOUND"


class TestEnhanceEndpoint:
    """POST /api/v1/servers/{server_id}/tools/enhance"""

    @pytest.mark.asyncio
    async def test_enhance_nonexistent_server_returns_404(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Enhancing a server that does not exist should return 404."""
        fake_id = uuid.uuid4()
        response = await auth_client.post(
            f"{BASE_URL}/{fake_id}/tools/enhance",
            json={"tool_names": None, "force": False},
        )
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_enhance_other_user_server_returns_403(
        self,
        auth_client: AsyncClient,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """Enhancing another user's server should return 403."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=other_user.id,
            slug=f"enhance-forbid-{uuid.uuid4().hex[:8]}",
            name="Enhance Forbidden",
            base_url="https://other.example.com",
            tools_config={
                "tools": [
                    {"name": "tool_1", "description": "First tool"},
                ]
            },
        )

        response = await auth_client.post(
            f"{BASE_URL}/{server.id}/tools/enhance",
            json={"tool_names": None, "force": False},
        )
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["error"]["code"] == "FORBIDDEN"


class TestAcceptEndpoint:
    """POST /api/v1/servers/{server_id}/tools/accept"""

    @pytest.mark.asyncio
    async def test_accept_nonexistent_server_returns_404(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Accepting enhancements on a non-existent server should return 404."""
        fake_id = uuid.uuid4()
        response = await auth_client.post(
            f"{BASE_URL}/{fake_id}/tools/accept",
            json={"accepted_tools": [], "rejected_tools": [], "custom_edits": {}},
        )
        assert response.status_code == 404
        error_data = response.json()
        assert error_data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_accept_other_user_server_returns_403(
        self,
        auth_client: AsyncClient,
        test_session: AsyncSession,
        other_user: User,
    ) -> None:
        """Accepting enhancements on another user's server should return 403."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=other_user.id,
            slug=f"accept-forbid-{uuid.uuid4().hex[:8]}",
            name="Accept Forbidden",
            base_url="https://other.example.com",
        )

        response = await auth_client.post(
            f"{BASE_URL}/{server.id}/tools/accept",
            json={"accepted_tools": [], "rejected_tools": [], "custom_edits": {}},
        )
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["error"]["code"] == "FORBIDDEN"
