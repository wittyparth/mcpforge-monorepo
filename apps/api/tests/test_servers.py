"""MCP Server CRUD endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

SERVERS_URL = "/api/v1/servers"
AUTH_REGISTER_URL = "/api/v1/auth/register"

TEST_EMAIL = "server-test@example.com"
TEST_PASSWORD = "servertestpass123!"
SERVER_SLUG = "my-test-server"
SERVER_NAME = "My Test Server"
SERVER_BASE_URL = "https://api.example.com"


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Return an authenticated client session."""
    response = await client.post(
        AUTH_REGISTER_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    access_token = response.cookies.get("access_token")
    client.cookies.set("access_token", access_token)
    return client


@pytest.mark.asyncio
async def test_create_server(client: AsyncClient, auth_client: AsyncClient) -> None:
    """POST /api/v1/servers should create a server."""
    response = await auth_client.post(
        SERVERS_URL,
        json={
            "name": SERVER_NAME,
            "slug": SERVER_SLUG,
            "base_url": SERVER_BASE_URL,
            "description": "A test server",
            "auth_scheme": "none",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == SERVER_NAME
    assert data["slug"] == SERVER_SLUG
    assert data["base_url"] == SERVER_BASE_URL
    assert data["status"] == "building"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_server_duplicate_slug(client: AsyncClient, auth_client: AsyncClient) -> None:
    """POST /api/v1/servers with a duplicate slug should fail."""
    # First creation
    await auth_client.post(
        SERVERS_URL,
        json={"name": SERVER_NAME, "slug": SERVER_SLUG, "base_url": SERVER_BASE_URL},
    )

    # Duplicate slug
    response = await auth_client.post(
        SERVERS_URL,
        json={"name": "Another Server", "slug": SERVER_SLUG, "base_url": "https://other.com"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_servers(client: AsyncClient, auth_client: AsyncClient) -> None:
    """GET /api/v1/servers should list user's servers."""
    # Create a server
    await auth_client.post(
        SERVERS_URL,
        json={"name": SERVER_NAME, "slug": SERVER_SLUG, "base_url": SERVER_BASE_URL},
    )

    # List servers
    response = await auth_client.get(SERVERS_URL)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(s["slug"] == SERVER_SLUG for s in data)


@pytest.mark.asyncio
async def test_get_server(client: AsyncClient, auth_client: AsyncClient) -> None:
    """GET /api/v1/servers/{id} should return a specific server."""
    # Create a server
    create_resp = await auth_client.post(
        SERVERS_URL,
        json={"name": SERVER_NAME, "slug": SERVER_SLUG, "base_url": SERVER_BASE_URL},
    )
    server_id = create_resp.json()["id"]

    # Get server
    response = await auth_client.get(f"{SERVERS_URL}/{server_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == server_id
    assert data["slug"] == SERVER_SLUG


@pytest.mark.asyncio
async def test_update_server(client: AsyncClient, auth_client: AsyncClient) -> None:
    """PATCH /api/v1/servers/{id} should update a server."""
    create_resp = await auth_client.post(
        SERVERS_URL,
        json={"name": SERVER_NAME, "slug": SERVER_SLUG, "base_url": SERVER_BASE_URL},
    )
    server_id = create_resp.json()["id"]

    # Update
    response = await auth_client.patch(
        f"{SERVERS_URL}/{server_id}",
        json={"name": "Updated Name", "status": "active"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_delete_server(client: AsyncClient, auth_client: AsyncClient) -> None:
    """DELETE /api/v1/servers/{id} should delete a server."""
    create_resp = await auth_client.post(
        SERVERS_URL,
        json={"name": SERVER_NAME, "slug": SERVER_SLUG, "base_url": SERVER_BASE_URL},
    )
    server_id = create_resp.json()["id"]

    # Delete
    response = await auth_client.delete(f"{SERVERS_URL}/{server_id}")
    assert response.status_code == 204

    # Verify deletion
    get_resp = await auth_client.get(f"{SERVERS_URL}/{server_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_server_unauthenticated(client: AsyncClient) -> None:
    """POST /api/v1/servers without auth should fail."""
    response = await client.post(
        SERVERS_URL,
        json={"name": "Hacker Server", "slug": "hack", "base_url": "https://evil.com"},
    )
    assert response.status_code == 401
