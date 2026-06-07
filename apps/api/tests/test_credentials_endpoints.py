"""Endpoint tests for credential management (F1 / OpenAPI Ingestion).

Tests the 4 credential endpoints:
- GET    /api/v1/servers/{server_id}/credentials
- POST   /api/v1/servers/{server_id}/credentials
- POST   /api/v1/servers/{server_id}/credentials/test
- DELETE /api/v1/servers/{server_id}/credentials/{env_var_name}
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.services.credential_service import CredentialService

CREDENTIALS_URL = "/api/v1/servers/{server_id}/credentials"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _csrf_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable CSRF middleware for credential endpoint tests.

    The CSRF middleware bypasses checks when ENVIRONMENT is "testing".
    """
    monkeypatch.setattr(settings, "ENVIRONMENT", "testing")


@pytest_asyncio.fixture
async def server(test_session: AsyncSession, auth_user: User) -> MCPServer:
    """Create a test MCP server owned by ``auth_user``."""
    s = MCPServer(
        user_id=auth_user.id,
        slug=f"test-cred-{uuid.uuid4().hex[:8]}",
        name="Test Server",
        base_url="https://api.example.com",
        auth_scheme="bearer",
    )
    test_session.add(s)
    await test_session.flush()
    return s


@pytest_asyncio.fixture
async def svc(test_session: AsyncSession) -> CredentialService:
    """Create a fresh ``CredentialService`` bound to the test session."""
    return CredentialService(test_session)


# ---------------------------------------------------------------------------
# GET /api/v1/servers/{server_id}/credentials
# ---------------------------------------------------------------------------


class TestListCredentials:
    """GET /api/v1/servers/{server_id}/credentials — list all credentials."""

    @pytest.mark.asyncio
    async def test_list_credentials_returns_all_for_server(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
        svc: CredentialService,
        auth_user: User,
    ) -> None:
        """List returns all credentials for the server and never leaks values."""
        await svc.add_credential(
            server_id=server.id,
            user_id=auth_user.id,
            env_var_name="API_KEY",
            value="sk-test-123",
            auth_scheme="bearer",
        )
        await svc.add_credential(
            server_id=server.id,
            user_id=auth_user.id,
            env_var_name="SECRET_KEY",
            value="secret-456",
            auth_scheme="bearer",
        )

        response = await auth_client.get(
            CREDENTIALS_URL.format(server_id=server.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["credentials"]) == 2

        env_names = {c["env_var_name"] for c in data["credentials"]}
        assert env_names == {"API_KEY", "SECRET_KEY"}

        # Response must never expose the plaintext or encrypted value
        for cred in data["credentials"]:
            assert "value" not in cred
            assert "encrypted_value" not in cred


# ---------------------------------------------------------------------------
# POST /api/v1/servers/{server_id}/credentials
# ---------------------------------------------------------------------------


class TestAddCredential:
    """POST /api/v1/servers/{server_id}/credentials — add new credential."""

    @pytest.mark.asyncio
    async def test_add_credential_returns_201(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Add credential returns 201 with the credential metadata."""
        response = await auth_client.post(
            CREDENTIALS_URL.format(server_id=server.id),
            json={
                "env_var_name": "API_KEY",
                "value": "sk-test-123",
                "auth_scheme": "bearer",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["env_var_name"] == "API_KEY"
        assert data["auth_scheme"] == "bearer"
        assert data["auth_header_name"] is None

        # The response must never leak the plaintext or encrypted value
        assert "value" not in data
        assert "encrypted_value" not in data

    @pytest.mark.asyncio
    async def test_add_duplicate_credential_returns_409(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Adding a duplicate env_var_name returns 409 CONFLICT."""
        await auth_client.post(
            CREDENTIALS_URL.format(server_id=server.id),
            json={
                "env_var_name": "API_KEY",
                "value": "sk-first",
                "auth_scheme": "bearer",
            },
        )

        response = await auth_client.post(
            CREDENTIALS_URL.format(server_id=server.id),
            json={
                "env_var_name": "API_KEY",
                "value": "sk-second",
                "auth_scheme": "bearer",
            },
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# POST /api/v1/servers/{server_id}/credentials/test
# ---------------------------------------------------------------------------


class TestTestCredential:
    """POST /api/v1/servers/{server_id}/credentials/test — dry-run test."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_test_credential_bearer_success(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Test bearer credential returns success when upstream responds 200."""
        respx.route(host="api.example.com").mock(
            return_value=httpx.Response(200),
        )

        response = await auth_client.post(
            f"{CREDENTIALS_URL.format(server_id=server.id)}/test",
            json={
                "env_var_name": "API_KEY",
                "test_value": "my-token",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status_code"] == 200
        assert data["error"] is None


# ---------------------------------------------------------------------------
# DELETE /api/v1/servers/{server_id}/credentials/{env_var_name}
# ---------------------------------------------------------------------------


class TestDeleteCredential:
    """DELETE /api/v1/servers/{server_id}/credentials/{env_var_name}."""

    @pytest.mark.asyncio
    async def test_delete_credential_returns_204(
        self,
        auth_client: AsyncClient,
        server: MCPServer,
    ) -> None:
        """Delete credential returns 204 and removes the credential."""
        # Seed a credential via the endpoint
        await auth_client.post(
            CREDENTIALS_URL.format(server_id=server.id),
            json={
                "env_var_name": "API_KEY",
                "value": "sk-test-123",
                "auth_scheme": "bearer",
            },
        )

        response = await auth_client.delete(
            f"{CREDENTIALS_URL.format(server_id=server.id)}/API_KEY",
        )
        assert response.status_code == 204
        assert response.content == b""

        # Verify the credential was actually removed
        list_resp = await auth_client.get(
            CREDENTIALS_URL.format(server_id=server.id),
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 0
