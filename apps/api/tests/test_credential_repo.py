"""Tests for CredentialRepository."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServer
from app.models.user import User
from app.repositories.credential_repo import CredentialRepository


@pytest.fixture
async def user(test_session: AsyncSession) -> User:
    """Create a test user for credential repo tests."""
    u = User(
        email=f"cred-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
    )
    test_session.add(u)
    await test_session.flush()
    return u


@pytest.fixture
async def server(test_session: AsyncSession, user: User) -> MCPServer:
    """Create a test MCP server owned by the test user."""
    s = MCPServer(
        user_id=user.id,
        slug=f"test-server-{uuid.uuid4().hex[:8]}",
        name="Test Server",
        base_url="https://api.example.com",
    )
    test_session.add(s)
    await test_session.flush()
    return s


class TestCredentialRepository:
    """Test suite for CredentialRepository."""

    async def test_create_and_get_by_id(
        self,
        test_session: AsyncSession,
        user: User,
        server: MCPServer,
    ) -> None:
        """Create a Credential, then get_by_id returns full object."""
        repo = CredentialRepository(test_session)
        cred = await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=b"encrypted-secret-value",
            auth_scheme="bearer",
            auth_header_name="X-API-Key",
        )

        assert cred.id is not None
        assert cred.env_var_name == "API_KEY"
        assert cred.encrypted_value == b"encrypted-secret-value"
        assert cred.auth_scheme == "bearer"
        assert cred.auth_header_name == "X-API-Key"

        fetched = await repo.get_by_id(cred.id)
        assert fetched is not None
        assert fetched.id == cred.id
        assert fetched.env_var_name == "API_KEY"
        assert fetched.encrypted_value == b"encrypted-secret-value"

    async def test_get_by_server_and_env(
        self,
        test_session: AsyncSession,
        user: User,
        server: MCPServer,
    ) -> None:
        """get_by_server_and_env returns the correct credential."""
        repo = CredentialRepository(test_session)

        # Create two credentials for same server
        await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=b"key-value",
        )
        await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="SECRET",
            encrypted_value=b"secret-value",
        )

        found = await repo.get_by_server_and_env(server.id, "SECRET")
        assert found is not None
        assert found.env_var_name == "SECRET"
        assert found.encrypted_value == b"secret-value"

    async def test_get_by_server_and_env_nonexistent(
        self,
        test_session: AsyncSession,
        server: MCPServer,
    ) -> None:
        """get_by_server_and_env returns None when no match."""
        repo = CredentialRepository(test_session)
        result = await repo.get_by_server_and_env(server.id, "DOES_NOT_EXIST")
        assert result is None

    async def test_get_by_server_returns_all(
        self,
        test_session: AsyncSession,
        user: User,
        server: MCPServer,
    ) -> None:
        """get_by_server returns all credentials for a server."""
        repo = CredentialRepository(test_session)

        for env_name in ["API_KEY", "SECRET", "TOKEN"]:
            await repo.create(
                server_id=server.id,
                user_id=user.id,
                env_var_name=env_name,
                encrypted_value=f"{env_name}-value".encode(),
            )

        results = await repo.get_by_server(server.id)
        assert len(results) == 3
        env_names = {c.env_var_name for c in results}
        assert env_names == {"API_KEY", "SECRET", "TOKEN"}

    async def test_get_by_server_other_server(
        self,
        test_session: AsyncSession,
        user: User,
        server: MCPServer,
    ) -> None:
        """get_by_server does not return credentials for other servers."""
        # Create a second server
        other_server = MCPServer(
            user_id=user.id,
            slug=f"other-server-{uuid.uuid4().hex[:8]}",
            name="Other Server",
            base_url="https://other.example.com",
        )
        test_session.add(other_server)
        await test_session.flush()

        repo = CredentialRepository(test_session)
        await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=b"key-value",
        )
        await repo.create(
            server_id=other_server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=b"other-key",
        )

        results = await repo.get_by_server(server.id)
        assert len(results) == 1
        assert results[0].encrypted_value == b"key-value"

    async def test_rotate_updates_value_and_timestamp(
        self,
        test_session: AsyncSession,
        user: User,
        server: MCPServer,
    ) -> None:
        """rotate updates encrypted_value, rotated_at, and rotated_by."""
        repo = CredentialRepository(test_session)
        cred = await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=b"original-value",
        )

        assert cred.rotated_at is None
        assert cred.rotated_by is None

        rotated = await repo.rotate(
            cred,
            new_encrypted_value=b"rotated-value",
            rotated_by=user.id,
        )

        assert rotated.encrypted_value == b"rotated-value"
        assert rotated.rotated_by == user.id
        assert rotated.rotated_at is not None

        # Verify persistence
        fetched = await repo.get_by_id(cred.id)
        assert fetched is not None
        assert fetched.encrypted_value == b"rotated-value"
        assert fetched.rotated_by == user.id
        assert fetched.rotated_at is not None

    async def test_rotate_without_rotated_by(
        self,
        test_session: AsyncSession,
        user: User,
        server: MCPServer,
    ) -> None:
        """rotate works without specifying rotated_by."""
        repo = CredentialRepository(test_session)
        cred = await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=b"original",
        )

        rotated = await repo.rotate(cred, new_encrypted_value=b"new-value")
        assert rotated.encrypted_value == b"new-value"
        assert rotated.rotated_at is not None
        assert rotated.rotated_by is None

    async def test_delete_removes_credential(
        self,
        test_session: AsyncSession,
        user: User,
        server: MCPServer,
    ) -> None:
        """delete removes the credential from the database."""
        repo = CredentialRepository(test_session)
        cred = await repo.create(
            server_id=server.id,
            user_id=user.id,
            env_var_name="API_KEY",
            encrypted_value=b"delete-me",
        )
        cred_id = cred.id

        await repo.delete(cred)

        fetched = await repo.get_by_id(cred_id)
        assert fetched is None

    async def test_get_by_id_nonexistent(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_by_id returns None for a non-existent UUID."""
        repo = CredentialRepository(test_session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None
