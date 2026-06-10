"""Tests for SecurityScanner and its Celery task (F5).

8 tests covering:
  - Scanner with safe config → 0 findings
  - Scanner detects SSRF
  - Scanner detects no-auth DELETE
  - Acknowledgment suppresses finding
  - Scanner returns correct severity counts
  - Scanner raises NotFoundError for missing server
  - Task is registered in Celery
  - Task routes to scanner queue
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.exceptions import NotFoundError
from app.models.mcp_server import MCPServer
from app.models.security import SecurityAcknowledgment
from app.models.user import User
from app.services.security_scanner.scanner import SecurityScanner
from app.services.security_scanner.tasks import scan_server

# ── Helpers ───────────────────────────────────────────────────────────────────


def _tool(
    name: str = "test_tool",
    method: str = "GET",
    path: str = "/test",
    tags: list[str] | None = None,
    description: str = "A test tool",
    properties: dict[str, Any] | None = None,
    response_properties: dict[str, Any] | None = None,
    **extra: object,
) -> dict[str, Any]:
    """Build a minimal tool dict matching the tools_config JSONB shape."""
    tool: dict[str, Any] = {
        "name": name,
        "description": description,
        "method": method,
        "path": path,
        "tags": tags if tags is not None else ["default"],
        "input_schema": {
            "type": "object",
            "properties": properties or {},
        },
        "parameters": [],
        "request_body_schema": None,
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": response_properties or {},
            },
        },
        "security_requirements": [],
        "selected": True,
    }
    tool.update(extra)
    return tool


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def server(test_session: AsyncSession, auth_user: User) -> MCPServer:
    """Create a minimal MCPServer for scanning tests."""
    s = MCPServer(
        user_id=auth_user.id,
        slug=f"test-scan-{uuid.uuid4().hex[:8]}",
        name="Scan Test Server",
        base_url="https://api.example.com",
        auth_scheme="none",
        tools_config={"tools": []},
    )
    test_session.add(s)
    await test_session.flush()
    return s


# ── Scanner tests ─────────────────────────────────────────────────────────────


class TestSecurityScanner:
    """Scanner behaviour with various tool configurations."""

    async def test_scan_no_findings(
        self, test_session: AsyncSession, auth_user: User,
    ) -> None:
        """Safe tools with authentication yield 0 findings."""
        s = MCPServer(
            user_id=auth_user.id,
            slug=f"safe-{uuid.uuid4().hex[:8]}",
            name="Safe Server",
            base_url="https://api.example.com",
            auth_scheme="api_key",
            tools_config={
                "tools": [
                    _tool(
                        name="list_users",
                        method="GET",
                        tags=["users"],
                        description="List all users",
                        properties={"page": {"type": "integer"}},
                    ),
                ],
            },
        )
        test_session.add(s)
        await test_session.flush()

        scanner = SecurityScanner(test_session)
        result = await scanner.scan(s.id)

        assert result.scan_status == "completed"
        assert result.findings == []
        assert result.critical_count == 0
        assert result.high_count == 0
        assert result.medium_count == 0
        assert result.info_count == 0
        assert result.scan_duration_ms is not None

    async def test_scan_detects_ssrf(
        self, test_session: AsyncSession, auth_user: User,
    ) -> None:
        """Tool with a URL parameter triggers SSRF_URL_PARAM finding."""
        s = MCPServer(
            user_id=auth_user.id,
            slug=f"ssrf-{uuid.uuid4().hex[:8]}",
            name="SSRF Server",
            base_url="https://api.example.com",
            auth_scheme="bearer",
            tools_config={
                "tools": [
                    _tool(
                        name="fetch_page",
                        method="GET",
                        properties={"url": {"type": "string"}},
                    ),
                ],
            },
        )
        test_session.add(s)
        await test_session.flush()

        scanner = SecurityScanner(test_session)
        result = await scanner.scan(s.id)

        assert result.scan_status == "completed"
        finding_ids = [f["id"] for f in result.findings]
        assert "SSRF_URL_PARAM" in finding_ids
        assert result.critical_count >= 1

    async def test_scan_detects_no_auth_delete(
        self, test_session: AsyncSession, auth_user: User,
    ) -> None:
        """DELETE tool with no auth triggers NO_AUTH_DELETE finding."""
        s = MCPServer(
            user_id=auth_user.id,
            slug=f"nodel-{uuid.uuid4().hex[:8]}",
            name="No Auth Delete Server",
            base_url="https://api.example.com",
            auth_scheme="none",
            tools_config={
                "tools": [
                    _tool(name="delete_user", method="DELETE"),
                ],
            },
        )
        test_session.add(s)
        await test_session.flush()

        scanner = SecurityScanner(test_session)
        result = await scanner.scan(s.id)

        assert result.scan_status == "completed"
        finding_ids = [f["id"] for f in result.findings]
        assert "NO_AUTH_DELETE" in finding_ids
        assert result.critical_count >= 1

    async def test_scan_acknowledgment_suppresses_finding(
        self, test_session: AsyncSession, auth_user: User,
    ) -> None:
        """Acknowledged finding is filtered out of scan results."""
        s = MCPServer(
            user_id=auth_user.id,
            slug=f"ack-{uuid.uuid4().hex[:8]}",
            name="Ack Test Server",
            base_url="https://api.example.com",
            auth_scheme="none",
            tools_config={
                "tools": [
                    _tool(name="delete_user", method="DELETE"),
                ],
            },
        )
        test_session.add(s)
        await test_session.flush()

        # Pre-acknowledge the NO_AUTH_DELETE finding
        ack = SecurityAcknowledgment(
            server_id=s.id,
            finding_id="NO_AUTH_DELETE",
            acknowledged_by=auth_user.id,
            acknowledged_at=datetime.now(UTC),
        )
        test_session.add(ack)
        await test_session.flush()

        scanner = SecurityScanner(test_session)
        result = await scanner.scan(s.id)

        assert result.scan_status == "completed"
        finding_ids = [f["id"] for f in result.findings]
        assert "NO_AUTH_DELETE" not in finding_ids
        assert result.critical_count == 0

    async def test_scan_returns_counts(
        self, test_session: AsyncSession, auth_user: User,
    ) -> None:
        """Mixed findings produce correct severity counts."""
        s = MCPServer(
            user_id=auth_user.id,
            slug=f"counts-{uuid.uuid4().hex[:8]}",
            name="Counts Test Server",
            base_url="https://api.example.com",
            auth_scheme="none",
            tools_config={
                "tools": [
                    # Triggers SSRF_URL_PARAM (critical)
                    _tool(
                        name="fetch_page",
                        method="GET",
                        properties={"url": {"type": "string"}},
                    ),
                    # Triggers NO_AUTH_DELETE (critical)
                    _tool(name="delete_user", method="DELETE"),
                    # Triggers NO_AUTH_WRITES (high)
                    _tool(name="create_user", method="POST"),
                    # No tags → UNTAGGED_ENDPOINTS (medium)
                    _tool(name="orphan", tags=[]),
                ],
            },
        )
        test_session.add(s)
        await test_session.flush()

        scanner = SecurityScanner(test_session)
        result = await scanner.scan(s.id)

        assert result.scan_status == "completed"
        # Should have SSRF (critical) + NO_AUTH_DELETE (critical)"
        # " + NO_AUTH_WRITES (high) + UNTAGGED (medium)
        assert result.critical_count >= 2
        assert result.high_count >= 1
        assert result.medium_count >= 1
        # All findings should be present
        finding_ids = {f["id"] for f in result.findings}
        assert "SSRF_URL_PARAM" in finding_ids
        assert "NO_AUTH_DELETE" in finding_ids
        assert "NO_AUTH_WRITES" in finding_ids

    async def test_scan_server_not_found(
        self, test_session: AsyncSession,
    ) -> None:
        """Scanning a non-existent server raises NotFoundError."""
        fake_id = UUID("00000000-0000-0000-0000-000000000000")
        scanner = SecurityScanner(test_session)

        with pytest.raises(NotFoundError):
            await scanner.scan(fake_id)


# ── Task tests ────────────────────────────────────────────────────────────────


class TestSecurityScannerTask:
    """Celery task registration and routing."""

    def test_task_registered(self) -> None:
        """The scan_server task should be registered in Celery with the correct name."""
        task_name = "app.services.security_scanner.tasks.scan_server"
        task = celery_app.tasks.get(task_name)
        assert task is not None, f"Task '{task_name}' not registered"
        assert task.name == task_name
        assert callable(scan_server)

    def test_task_routes_to_scanner_queue(self) -> None:
        """The task should be routed to the 'scanner' queue."""
        route = celery_app.conf.task_routes
        assert "app.services.security_scanner.tasks.*" in route
        assert route["app.services.security_scanner.tasks.*"]["queue"] == "scanner"
