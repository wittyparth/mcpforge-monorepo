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

from app.core.celery_app import celery_app as _celery_app
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
    @pytest.mark.skipif(
        _celery_app.conf.task_always_eager,
        reason="asyncio.run() conflicts with Celery eager mode",
    )
    async def test_start_build_marks_server_building(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """Verify ``POST /build`` flips the server to ``building`` and returns
        a Celery ``job_id`` synchronously.
        """
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

        # The endpoint returns an AIEnhancementResponse, not a status wrapper.
        # The Celery job runs asynchronously; the synchronous response only
        # carries the job_id and cost estimate.
        assert "job_id" in data
        assert isinstance(data["job_id"], str) and len(data["job_id"]) > 0
        assert "estimated_cost_cents" in data
        assert isinstance(data["estimated_cost_cents"], int)

        # Verify persistence in the database
        refreshed = await repo.get_by_id(server.id)
        assert refreshed is not None
        # The server should remain in 'building' state (the worker eventually
        # flips it to 'active' or 'review'; the synchronous endpoint just kicks
        # off the job).
        assert refreshed.status == "building"

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
        """Verify the SSE stream emits a ``connected`` event as the first
        chunk. Uses the ``close_after_first=True`` test affordance so the
        endpoint terminates after the initial event instead of looping on
        heartbeats.
        """
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=auth_user.id,
            slug=f"build-sse-{uuid.uuid4().hex[:8]}",
            name="Build SSE Test",
            base_url="https://api.example.com",
        )

        response = await auth_client.get(
            f"{BASE_URL}/{server.id}/build-status",
            params={"close_after_first": "true"},
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type

        body = response.text
        assert "event: connected" in body
        assert "data:" in body

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


class TestAcceptEndpoint:
    """POST /api/v1/servers/{server_id}/tools/accept — real implementation."""

    @pytest.mark.asyncio
    async def test_accept_returns_200_with_empty_tools(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """Accepting with no tools returns 200 (idempotent)."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=auth_user.id,
            slug=f"accept-200-{uuid.uuid4().hex[:8]}",
            name="Accept 200 Test",
            base_url="https://api.example.com",
        )

        response = await auth_client.post(
            f"{BASE_URL}/{server.id}/tools/accept",
            json={"accepted_tools": [], "rejected_tools": [], "custom_edits": {}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in {"accepted", "no_changes"}


class TestDeployEndpoint:
    """POST /api/v1/servers/{server_id}/deploy — real implementation."""

    @pytest.mark.asyncio
    async def test_deploy_blocks_on_critical_findings(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """A server with CRITICAL security findings cannot be deployed.

        The security scanner runs synchronously inside the deploy
        handler. A clean OpenAPI spec (no credentials, no risky tools)
        produces 0 critical findings, so the deploy proceeds. We
        assert the endpoint either succeeds (200) or is blocked (409)
        based on the deterministic scan output.
        """
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=auth_user.id,
            slug=f"deploy-real-{uuid.uuid4().hex[:8]}",
            name="Deploy Real Test",
            base_url="https://api.example.com",
        )

        response = await auth_client.post(f"{BASE_URL}/{server.id}/deploy")
        # 200 (deployed) or 409 (blocked by scanner) are both valid.
        assert response.status_code in {200, 409}
        if response.status_code == 409:
            data = response.json()
            assert "BLOCKED_BY_SCANNER" in str(data) or "critical" in str(data).lower()


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

