"""Endpoint tests for security scanner (F5).

Tests the 6 security endpoints:
- POST   /api/v1/servers/{server_id}/security/scan
- GET    /api/v1/servers/{server_id}/security/latest
- POST   /api/v1/servers/{server_id}/security/{finding_id}/acknowledge
- DELETE /api/v1/servers/{server_id}/security/{finding_id}/acknowledge
- GET    /api/v1/servers/{server_id}/security/acknowledgments
- GET    /api/v1/servers/{server_id}/security/report.json
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.mcp_server import MCPServer
from app.models.security import SecurityScanResult
from app.models.user import User
from app.repositories.security_repo import SecurityAckRepository, SecurityScanRepository

SECURITY_URL = "/api/v1/servers/{server_id}/security"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _csrf_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable CSRF middleware for security endpoint tests."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "testing")


@pytest_asyncio.fixture
async def server(test_session: AsyncSession, auth_user: User) -> MCPServer:
    """Create a test MCP server owned by ``auth_user``."""
    s = MCPServer(
        user_id=auth_user.id,
        slug=f"test-sec-{uuid.uuid4().hex[:8]}",
        name="Security Test Server",
        base_url="https://api.example.com",
        auth_scheme="bearer",
        tools_config={"tools": []},
    )
    test_session.add(s)
    await test_session.flush()
    return s


@pytest_asyncio.fixture
async def scan_repo(test_session: AsyncSession) -> SecurityScanRepository:
    """Fixture scoped repository for scan operations."""
    return SecurityScanRepository(test_session)


@pytest_asyncio.fixture
async def ack_repo(test_session: AsyncSession) -> SecurityAckRepository:
    """Fixture scoped repository for ack operations."""
    return SecurityAckRepository(test_session)


@pytest_asyncio.fixture
async def seeded_scan(
    test_session: AsyncSession,
    server: MCPServer,
    scan_repo: SecurityScanRepository,
) -> SecurityScanResult:
    """Seed a completed scan result with one critical finding."""
    return await scan_repo.create(
        server_id=server.id,
        scan_status="completed",
        findings=[
            {
                "id": "NO_AUTH_DELETE",
                "severity": "critical",
                "title": "DELETE operation without authentication",
                "description": "DELETE method with no auth configured",
                "affected_tools": ["delete-thing"],
                "remediation": "Add Bearer or API Key authentication",
                "references": [],
            },
        ],
        critical_count=1,
        scan_duration_ms=5,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/servers/{server_id}/security/scan
# ---------------------------------------------------------------------------


class TestTriggerScan:
    """POST /api/v1/servers/{server_id}/security/scan — trigger a scan."""

    @pytest.mark.asyncio
    async def test_trigger_scan_returns_scan_trigger(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Trigger scan returns 200 with ScanTriggerResponse."""
        mock_task = MagicMock()
        mock_task.id = "mock-task-id"

        with patch(
            "app.services.security_scanner.tasks.scan_server.delay",
            return_value=mock_task,
        ):
            response = await auth_client.post(
                f"{SECURITY_URL.format(server_id=server.id)}/scan"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["scan_status"] == "running"
        assert data["scan_id"] == str(server.id)
        assert "initiated" in data["message"]


# ---------------------------------------------------------------------------
# GET /api/v1/servers/{server_id}/security/latest
# ---------------------------------------------------------------------------


class TestGetLatestScan:
    """GET /api/v1/servers/{server_id}/security/latest — get latest scan."""

    @pytest.mark.asyncio
    async def test_get_latest_scan_returns_result(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
        seeded_scan: SecurityScanResult,
    ) -> None:
        """GET /latest returns the most recent scan result."""
        response = await auth_client.get(
            f"{SECURITY_URL.format(server_id=server.id)}/latest"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scan_status"] == "completed"
        assert data["critical_count"] == 1
        assert len(data["findings"]) == 1
        assert data["findings"][0]["id"] == "NO_AUTH_DELETE"
        assert data["server_id"] == str(server.id)

    @pytest.mark.asyncio
    async def test_get_latest_scan_returns_null(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """GET /latest on a server with no scans returns 200 with ``null``."""
        response = await auth_client.get(
            f"{SECURITY_URL.format(server_id=server.id)}/latest"
        )

        assert response.status_code == 200
        assert response.json() is None


# ---------------------------------------------------------------------------
# POST /api/v1/servers/{server_id}/security/{finding_id}/acknowledge
# ---------------------------------------------------------------------------


class TestAcknowledgeFinding:
    """POST /api/v1/servers/{server_id}/security/{finding_id}/acknowledge."""

    @pytest.mark.asyncio
    async def test_acknowledge_finding_returns_ack(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Acknowledge a finding returns 200 with AcknowledgeResponse."""
        response = await auth_client.post(
            f"{SECURITY_URL.format(server_id=server.id)}/NO_AUTH_DELETE/acknowledge",
            json={"note": "Acknowledged for testing"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["finding_id"] == "NO_AUTH_DELETE"
        assert data["server_id"] == str(server.id)
        assert "acknowledged_at" in data

    @pytest.mark.asyncio
    async def test_acknowledge_duplicate_returns_409(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Acknowledging the same finding twice returns 409 Conflict."""
        # First ack succeeds
        await auth_client.post(
            f"{SECURITY_URL.format(server_id=server.id)}/SSRF_URL_PARAM/acknowledge",
            json={"note": "First ack"},
        )

        # Second ack is a conflict
        response = await auth_client.post(
            f"{SECURITY_URL.format(server_id=server.id)}/SSRF_URL_PARAM/acknowledge",
            json={"note": "Duplicate ack"},
        )

        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# DELETE /api/v1/servers/{server_id}/security/{finding_id}/acknowledge
# ---------------------------------------------------------------------------


class TestRemoveAcknowledgment:
    """DELETE /api/v1/servers/{server_id}/security/{finding_id}/acknowledge."""

    @pytest.mark.asyncio
    async def test_remove_acknowledgment_returns_204(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
        ack_repo: SecurityAckRepository,
    ) -> None:
        """Remove an acknowledgment returns 204 and actually removes it."""
        # Seed an acknowledgment
        await ack_repo.acknowledge(
            server_id=server.id,
            finding_id="NO_AUTH_DELETE",
            user_id=server.user_id,
            note="Test ack",
        )

        # Remove it
        response = await auth_client.delete(
            f"{SECURITY_URL.format(server_id=server.id)}/NO_AUTH_DELETE/acknowledge"
        )

        assert response.status_code == 204
        assert response.content == b""

        # Verify it's actually removed
        acks = await ack_repo.get_for_server(server.id)
        assert len(acks) == 0


# ---------------------------------------------------------------------------
# GET /api/v1/servers/{server_id}/security/acknowledgments
# ---------------------------------------------------------------------------


class TestListAcknowledgments:
    """GET /api/v1/servers/{server_id}/security/acknowledgments."""

    @pytest.mark.asyncio
    async def test_list_acknowledgments_returns_all(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
        ack_repo: SecurityAckRepository,
    ) -> None:
        """List acknowledgments returns all acks for a server."""
        # Seed two acknowledgments
        await ack_repo.acknowledge(
            server_id=server.id,
            finding_id="NO_AUTH_DELETE",
            user_id=server.user_id,
            note="First ack",
        )
        await ack_repo.acknowledge(
            server_id=server.id,
            finding_id="SSRF_URL_PARAM",
            user_id=server.user_id,
            note="Second ack",
        )

        response = await auth_client.get(
            f"{SECURITY_URL.format(server_id=server.id)}/acknowledgments"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        finding_ids = {item["finding_id"] for item in data["items"]}
        assert finding_ids == {"NO_AUTH_DELETE", "SSRF_URL_PARAM"}


# ---------------------------------------------------------------------------
# GET /api/v1/servers/{server_id}/security/report.json
# ---------------------------------------------------------------------------


class TestExportReport:
    """GET /api/v1/servers/{server_id}/security/report.json."""

    @pytest.mark.asyncio
    async def test_export_report_with_scan(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
        seeded_scan: SecurityScanResult,
        ack_repo: SecurityAckRepository,
    ) -> None:
        """Export report with a scan and acknowledgments."""
        # Seed an acknowledgment
        await ack_repo.acknowledge(
            server_id=server.id,
            finding_id="NO_AUTH_DELETE",
            user_id=server.user_id,
            note="Test ack",
        )

        response = await auth_client.get(
            f"{SECURITY_URL.format(server_id=server.id)}/report.json"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["server_id"] == str(server.id)
        assert data["server_name"] == "Security Test Server"
        assert data["scan"] is not None
        assert data["scan"]["scan_status"] == "completed"
        assert len(data["acknowledgments"]) == 1
        assert "generated_at" in data
        assert "summary" in data
