"""Tests for CredentialService — encryption, ownership, and connectivity testing.

Uses inline DB fixtures (User / MCPServer) and ``respx`` for HTTP mocking.
"""

from __future__ import annotations

import base64
import uuid

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.repositories.credential_repo import CredentialRepository
from app.services.credential_service import CredentialService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def user(test_session: AsyncSession) -> User:
    """Create a test user."""
    u = User(
        email=f"svc-cred-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
    )
    test_session.add(u)
    await test_session.flush()
    return u


@pytest.fixture
async def server(test_session: AsyncSession, user: User) -> MCPServer:
    """Create a test MCP server owned by ``user``."""
    s = MCPServer(
        user_id=user.id,
        slug=f"test-svc-{uuid.uuid4().hex[:8]}",
        name="Test Server",
        base_url="https://api.example.com",
        auth_scheme="bearer",
    )
    test_session.add(s)
    await test_session.flush()
    return s


@pytest.fixture
def svc(test_session: AsyncSession) -> CredentialService:
    """Create a fresh ``CredentialService`` bound to the test session."""
    return CredentialService(test_session)


# ---------------------------------------------------------------------------
# add_credential
# ---------------------------------------------------------------------------


class TestAddCredential:
    """CredentialService.add_credential — happy path and error cases."""

    @pytest.mark.asyncio
    async def test_happy_path_creates_encrypted_credential(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """add_credential encrypts the value and persists it."""
        cred = await svc.add_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            value="sk-123456",
            auth_scheme="bearer",
        )

        assert cred.id is not None
        assert cred.env_var_name == "API_KEY"
        assert cred.auth_scheme == "bearer"
        assert cred.encryption_key_id == "default"
        # encrypted_value must not be the plaintext
        assert cred.encrypted_value != b"sk-123456"
        assert len(cred.encrypted_value) > 0
        # auth_header_name should be None when not provided
        assert cred.auth_header_name is None

    @pytest.mark.asyncio
    async def test_duplicate_env_var_raises_conflict(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """Same env_var_name on the same server → ConflictError."""
        await svc.add_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            value="sk-123456",
        )

        with pytest.raises(ConflictError) as exc:
            await svc.add_credential(
                server_id=server.id,
                user_id=user.id,
                env_var_name="API_KEY",
                value="sk-789012",
            )
        assert "API_KEY" in str(exc.value)

    @pytest.mark.asyncio
    async def test_forbidden_on_other_users_server(
        self,
        svc: CredentialService,
        server: MCPServer,
    ) -> None:
        """Adding a credential to a server owned by someone else → ForbiddenError."""
        other_user_id = uuid.uuid4()

        with pytest.raises(ForbiddenError):
            await svc.add_credential(
                server_id=server.id,
                user_id=other_user_id,
                env_var_name="API_KEY",
                value="sk-123456",
            )

    @pytest.mark.asyncio
    async def test_not_found_on_nonexistent_server(
        self,
        svc: CredentialService,
        user: User,
    ) -> None:
        """Adding a credential to a server that does not exist → NotFoundError."""
        with pytest.raises(NotFoundError):
            await svc.add_credential(
                server_id=uuid.uuid4(),
                user_id=user.id,
                env_var_name="API_KEY",
                value="sk-123456",
            )


# ---------------------------------------------------------------------------
# list_credentials & delete_credential
# ---------------------------------------------------------------------------


class TestListAndDelete:
    """CredentialService.list_credentials and delete_credential."""

    @pytest.mark.asyncio
    async def test_list_returns_all_for_server(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """list_credentials returns credentials only for the requested server."""
        await svc.add_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            value="key-1",
        )
        await svc.add_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="SECRET",
            value="secret-1",
        )

        creds = await svc.list_credentials(server_id=server.id, user_id=user.id)
        assert len(creds) == 2
        env_names = {c.env_var_name for c in creds}
        assert env_names == {"API_KEY", "SECRET"}

    @pytest.mark.asyncio
    async def test_list_excludes_other_servers(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
        test_session: AsyncSession,
    ) -> None:
        """list_credentials does not leak credentials from other servers."""
        # Create a second server with its own credential
        other_server = MCPServer(
            user_id=user.id,
            slug=f"other-{uuid.uuid4().hex[:8]}",
            name="Other Server",
            base_url="https://other.example.com",
            auth_scheme="api_key",
        )
        test_session.add(other_server)
        await test_session.flush()

        await svc.add_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            value="key-1",
        )
        await svc.add_credential(
            server_id=other_server.id,
            user_id=user.id,
            env_var_name="OTHER_KEY",
            value="key-2",
        )

        creds = await svc.list_credentials(server_id=server.id, user_id=user.id)
        assert len(creds) == 1
        assert creds[0].env_var_name == "API_KEY"

    @pytest.mark.asyncio
    async def test_delete_removes_credential(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """delete_credential removes the credential from the database."""
        await svc.add_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            value="sk-123456",
        )

        await svc.delete_credential(
            server_id=server.id,
            env_var_name="API_KEY",
            user_id=user.id,
        )

        creds = await svc.list_credentials(server_id=server.id, user_id=user.id)
        assert len(creds) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises_not_found(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """Deleting a credential that does not exist → NotFoundError."""
        with pytest.raises(NotFoundError):
            await svc.delete_credential(
                server_id=server.id,
                env_var_name="DOES_NOT_EXIST",
                user_id=user.id,
            )

    @pytest.mark.asyncio
    async def test_delete_forbidden_on_other_users_server(
        self,
        svc: CredentialService,
        server: MCPServer,
    ) -> None:
        """Deleting a credential on another user's server → ForbiddenError."""
        other_user_id = uuid.uuid4()

        with pytest.raises(ForbiddenError):
            await svc.delete_credential(
                server_id=server.id,
                env_var_name="API_KEY",
                user_id=other_user_id,
            )


# ---------------------------------------------------------------------------
# test_credential
# ---------------------------------------------------------------------------


class TestTestCredential:
    """CredentialService.test_credential — auth header construction + error modes."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_bearer_scheme(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """Bearer scheme sends ``Authorization: Bearer <value>``."""
        captured: dict[str, dict[str, str]] = {"headers": {}}

        def _capture(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200)

        respx.route(host="api.example.com").mock(side_effect=_capture)

        result = await svc.test_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            test_value="my-bearer-token",
        )

        assert result.success is True
        assert result.status_code == 200
        assert captured["headers"].get("authorization") == "Bearer my-bearer-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key_scheme_from_stored_credential(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
        test_session: AsyncSession,
    ) -> None:
        """api_key scheme on a stored credential sends the custom header."""
        # Seed a stored credential with api_key scheme so the service picks it up.
        repo = CredentialRepository(test_session)
        encrypted_value = b"dummy-encrypted"
        await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=encrypted_value,
            auth_scheme="api_key",
            auth_header_name="X-API-Key",
        )

        captured: dict[str, dict[str, str]] = {"headers": {}}

        def _capture(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200)

        respx.route(host="api.example.com").mock(side_effect=_capture)

        result = await svc.test_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            test_value="my-api-key-value",
        )

        assert result.success is True
        # respx lower-cases header keys
        assert captured["headers"].get("x-api-key") == "my-api-key-value"

    @pytest.mark.asyncio
    @respx.mock
    async def test_basic_scheme_from_stored_credential(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
        test_session: AsyncSession,
    ) -> None:
        """Basic scheme sends ``Authorization: Basic <base64(value)>``."""
        repo = CredentialRepository(test_session)
        encrypted_value = b"dummy-encrypted"
        await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="BASIC_CRED",
            encrypted_value=encrypted_value,
            auth_scheme="basic",
        )

        captured: dict[str, dict[str, str]] = {"headers": {}}

        def _capture(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200)

        respx.route(host="api.example.com").mock(side_effect=_capture)

        test_value = "user:pass"
        expected_basic = base64.b64encode(test_value.encode()).decode()

        result = await svc.test_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="BASIC_CRED",
            test_value=test_value,
        )

        assert result.success is True
        assert captured["headers"].get("authorization") == f"Basic {expected_basic}"

    @pytest.mark.asyncio
    @respx.mock
    async def test_5xx_response_returns_success_false(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """A 5xx upstream response yields ``success=False`` with the status code."""
        respx.route(host="api.example.com").mock(
            return_value=httpx.Response(502),
        )

        result = await svc.test_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            test_value="some-token",
        )

        assert result.success is False
        assert result.status_code == 502
        assert result.error == "HTTP 502"

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_timeout(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """Timeout exception yields ``success=False`` with a descriptive error."""
        respx.route(host="api.example.com").mock(
            side_effect=httpx.TimeoutException("Connection timed out", request=None),
        )

        result = await svc.test_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            test_value="some-token",
        )

        assert result.success is False
        assert result.status_code is None
        assert result.error == "Connection timed out (5s)"

    @pytest.mark.asyncio
    @respx.mock
    async def test_generic_network_error(
        self,
        svc: CredentialService,
        user: User,
        server: MCPServer,
    ) -> None:
        """A non-timeout network error yields ``success=False`` with ``Network error: ...``."""
        respx.route(host="api.example.com").mock(
            side_effect=httpx.ConnectError("DNS resolution failed"),
        )

        result = await svc.test_credential(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            test_value="some-token",
        )

        assert result.success is False
        assert result.status_code is None
        assert "Network error: ConnectError" in (result.error or "")
