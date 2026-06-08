"""Gateway admin endpoint tests.

These tests cover the user-facing gateway management endpoints:
connect panel, test connection, pause, resume, and authorization.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.main import app
from app.models.user import User
from app.services.mcp_server_service import MCPServerService

# Bypass CSRF middleware in tests: the middleware skips enforcement when
# ENVIRONMENT == "testing" (see app/core/middleware/csrf.py:111).
settings.ENVIRONMENT = "testing"

GATEWAY_PREFIX = "/api/v1/servers"


@pytest.mark.asyncio
async def test_connect_panel_returns_config(
    test_session: AsyncSession,
    auth_client: AsyncClient,
    auth_user: User,
) -> None:
    """GET /servers/{id}/connect should return connection details."""
    # Arrange: create a server owned by auth_user
    svc = MCPServerService(test_session)
    server = await svc.create_server(
        user_id=auth_user.id,
        slug="connect-test",
        name="Connect Test",
        base_url="https://api.example.com",
    )

    # Act
    resp = await auth_client.get(f"{GATEWAY_PREFIX}/{server.id}/connect")

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["server_slug"] == "connect-test"
    assert "mcp/v1/connect-test/" in data["gateway_url"]
    assert "mcp/v1/connect-test/sse" in data["gateway_url"] or any(
        "sse" in str(v) for v in data.values()
    )
    assert "sse" in data["transport_modes"]
    assert "streamable_http" in data["transport_modes"]
    assert "claude_desktop_config" in data
    assert "cursor_config" in data
    assert "mcpServers" in data["claude_desktop_config"]
    assert data["test_connection_endpoint"] == f"/api/v1/servers/{server.id}/connect/test"


@pytest.mark.asyncio
async def test_pause_server_updates_status(
    test_session: AsyncSession,
    auth_client: AsyncClient,
    auth_user: User,
) -> None:
    """POST /servers/{id}/pause should set status to paused."""
    # Arrange: create an active server
    svc = MCPServerService(test_session)
    server = await svc.create_server(
        user_id=auth_user.id,
        slug="pause-test",
        name="Pause Test",
        base_url="https://api.example.com",
    )

    # Act
    resp = await auth_client.post(f"{GATEWAY_PREFIX}/{server.id}/pause")

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "paused"
    assert data["server_id"] == str(server.id)
    assert data["estimated_propagation_seconds"] == 5

    # Verify the DB was updated
    updated = await svc.get_server(server.id)
    assert updated.status == "paused"


@pytest.mark.asyncio
async def test_resume_server_activates(
    test_session: AsyncSession,
    auth_client: AsyncClient,
    auth_user: User,
) -> None:
    """POST /servers/{id}/resume should set status back to active."""
    # Arrange: create a paused server
    svc = MCPServerService(test_session)
    server = await svc.create_server(
        user_id=auth_user.id,
        slug="resume-test",
        name="Resume Test",
        base_url="https://api.example.com",
    )
    # First pause it
    await svc.update_server(server.id, auth_user.id, status="paused")

    # Act
    resp = await auth_client.post(f"{GATEWAY_PREFIX}/{server.id}/resume")

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["server_id"] == str(server.id)

    # Verify the DB was updated
    updated = await svc.get_server(server.id)
    assert updated.status == "active"


@pytest.mark.asyncio
async def test_unauthorized_access(
    test_session: AsyncSession,
    auth_client: AsyncClient,
    auth_user: User,
) -> None:
    """Non-owner should get 403 when accessing server endpoints."""
    # Arrange: create a server owned by auth_user
    svc = MCPServerService(test_session)
    server = await svc.create_server(
        user_id=auth_user.id,
        slug="owner-only",
        name="Owner Server",
        base_url="https://owner.example.com",
    )

    # Create a second user
    other_user = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    test_session.add(other_user)
    await test_session.flush()

    # Temporarily override auth to be the other user
    original_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: other_user

    try:
        # Try connect panel as other user
        resp = await auth_client.get(f"{GATEWAY_PREFIX}/{server.id}/connect")
        assert resp.status_code == 403
    finally:
        # Restore original override
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override
        else:
            del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_connect_panel_not_found(
    auth_client: AsyncClient,
) -> None:
    """GET /servers/{id}/connect with nonexistent server should return 404."""
    fake_id = uuid.uuid4()
    resp = await auth_client.get(f"{GATEWAY_PREFIX}/{fake_id}/connect")
    assert resp.status_code == 404
