"""Tests for tool workspace endpoints (F1).

Endpoints:
- GET    /api/v1/servers/{server_id}/tools
- PATCH  /api/v1/servers/{server_id}/tools/{tool_name}
- POST   /api/v1/servers/{server_id}/tools/enhance (stub — returns 501)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.mcp_server import MCPServer
from app.models.user import User

# Disable CSRF for testing — the middleware only bypasses CSRF when
# settings.ENVIRONMENT == "testing".  All state-changing endpoint tests
# rely on this.
settings.ENVIRONMENT = "testing"

TOOLS_URL = "/api/v1/servers"

DEFAULT_TOOLS = [
    {"name": "list_pets", "description": "List all pets", "method": "GET", "path": "/pets"},
    {"name": "create_pet", "description": "Create a pet", "method": "POST", "path": "/pets"},
]

DEFAULT_TOOLS_CONFIG = {
    "version": 1,
    "generator": "spec_analyzer_v1",
    "tools": DEFAULT_TOOLS,
}


@pytest.fixture
async def server(test_session: AsyncSession, auth_user: User) -> MCPServer:
    """Create a test MCP server owned by ``auth_user`` with default tools."""
    s = MCPServer(
        user_id=auth_user.id,
        slug=f"test-tools-{uuid.uuid4().hex[:8]}",
        name="Test Tools Server",
        base_url="https://api.example.com",
        tools_config=DEFAULT_TOOLS_CONFIG,
    )
    test_session.add(s)
    await test_session.flush()
    return s


class TestListTools:
    """GET /api/v1/servers/{server_id}/tools."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_config_tools(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """List tools returns the tools from the server's tools_config."""
        response = await auth_client.get(f"{TOOLS_URL}/{server.id}/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["server_id"] == str(server.id)
        assert data["tool_count"] == 2
        assert len(data["tools"]) == 2
        tool_names = [t["name"] for t in data["tools"]]
        assert "list_pets" in tool_names
        assert "create_pet" in tool_names


class TestUpdateTool:
    """PATCH /api/v1/servers/{server_id}/tools/{tool_name}."""

    @pytest.mark.asyncio
    async def test_update_tool_description(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Updating a tool's description returns the updated tool and persists."""
        response = await auth_client.patch(
            f"{TOOLS_URL}/{server.id}/tools/list_pets",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "list_pets"
        assert data["description"] == "Updated description"

        # Verify the change persisted via GET
        get_resp = await auth_client.get(f"{TOOLS_URL}/{server.id}/tools")
        assert get_resp.status_code == 200
        tools = get_resp.json()["tools"]
        updated = [t for t in tools if t["name"] == "list_pets"][0]
        assert updated["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_tool_rename_collision_returns_409(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Renaming a tool to an already-used tool name returns 409."""
        response = await auth_client.patch(
            f"{TOOLS_URL}/{server.id}/tools/list_pets",
            json={"name": "create_pet"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_update_tool_not_found_returns_404(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Patching a non-existent tool name returns 404."""
        response = await auth_client.patch(
            f"{TOOLS_URL}/{server.id}/tools/nonexistent",
            json={"description": "whatever"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"


class TestEnhanceTools:
    """POST /api/v1/servers/{server_id}/tools/enhance."""

    @pytest.mark.asyncio
    async def test_enhance_tools_returns_501(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Enhance tools endpoint returns 501 (F2 stub)."""
        response = await auth_client.post(
            f"{TOOLS_URL}/{server.id}/tools/enhance",
        )
        assert response.status_code == 501
        data = response.json()
        assert data["error"]["code"] == "NOT_IMPLEMENTED"
        assert "pending F2" in data["error"]["message"]
