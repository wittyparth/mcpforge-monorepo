"""API key service and endpoint tests.

Tests both the service layer (unit) and the HTTP endpoints (integration).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User
from app.repositories.api_key_repo import ApiKeyRepository
from app.services.api_key_service import ApiKeyService

# ── Service-level tests ──────────────────────────────────────────────────


class TestCreateKey:
    """Tests for ApiKeyService.create_key()."""

    @pytest.mark.asyncio
    async def test_create_key_generates_unique_plaintext(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Verify format: mcpforge_live_<32 base64 chars>."""
        service = ApiKeyService(test_session)
        _, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="test-key",
            scopes=["servers:read"],
        )

        assert plaintext.startswith("mcpforge_live_")
        random_part = plaintext[len("mcpforge_live_"):]
        assert len(random_part) == 32  # token_urlsafe(24) → 32 chars
        # All URL-safe base64 chars
        assert all(c.isalnum() or c in "-_" for c in random_part)

    @pytest.mark.asyncio
    async def test_create_key_stores_hash_not_plaintext(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Verify the DB stores SHA-256 hash, not the plaintext."""
        service = ApiKeyService(test_session)
        api_key, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="test-key",
            scopes=["servers:read"],
        )

        # Hash should match
        expected_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        assert api_key.key_hash == expected_hash

        # The plaintext should NOT appear in the DB
        assert api_key.key_hash != plaintext

        # key_prefix should be first 12 chars
        assert api_key.key_prefix == plaintext[:12]

    @pytest.mark.asyncio
    async def test_create_key_enforces_max_5_per_user(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Creating a 6th key should raise ConflictError."""
        service = ApiKeyService(test_session)

        # Create 5 keys
        for i in range(5):
            _, plaintext = await service.create_key(
                user_id=auth_user.id,
                name=f"key-{i}",
                scopes=["servers:read"],
            )

        # 6th should fail
        from app.core.exceptions import PlanLimitExceededError

        with pytest.raises(PlanLimitExceededError, match="Maximum of 5 API keys reached"):
            await service.create_key(
                user_id=auth_user.id,
                name="key-6",
                scopes=["servers:read"],
            )

    @pytest.mark.asyncio
    async def test_create_key_with_expiry(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Verify expires_at is set when expires_in_days is provided."""
        service = ApiKeyService(test_session)
        api_key, _ = await service.create_key(
            user_id=auth_user.id,
            name="expiring-key",
            scopes=["servers:read"],
            expires_in_days=30,
        )

        assert api_key.expires_at is not None
        expected = datetime.now(UTC) + timedelta(days=30)
        assert abs((api_key.expires_at - expected).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_create_key_rejects_empty_name(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Empty name should raise ValidationError."""
        service = ApiKeyService(test_session)

        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="API key name is required"):
            await service.create_key(
                user_id=auth_user.id,
                name="",
                scopes=["servers:read"],
            )

    @pytest.mark.asyncio
    async def test_create_key_rejects_invalid_scope(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Invalid scopes should raise ValidationError."""
        service = ApiKeyService(test_session)

        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Invalid scopes"):
            await service.create_key(
                user_id=auth_user.id,
                name="bad-scope-key",
                scopes=["servers:read", "servers:delete"],
            )


class TestAuthenticate:
    """Tests for ApiKeyService.authenticate()."""

    @pytest.mark.asyncio
    async def test_authenticate_returns_user_for_valid_key(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Valid key should return the owning user."""
        service = ApiKeyService(test_session)
        api_key, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="valid-key",
            scopes=["servers:read"],
        )

        user = await service.authenticate(plaintext)
        assert user is not None
        assert user.id == auth_user.id

    @pytest.mark.asyncio
    async def test_authenticate_returns_none_for_invalid_key(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Random string should return None."""
        service = ApiKeyService(test_session)
        user = await service.authenticate("mcpforge_live_not-a-real-key")
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_returns_none_for_revoked_key(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Revoked key should return None."""
        service = ApiKeyService(test_session)
        api_key, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="revocable-key",
            scopes=["servers:read"],
        )

        await service.revoke_key(key_id=api_key.id, user_id=auth_user.id)

        user = await service.authenticate(plaintext)
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_returns_none_for_expired_key(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Expired key should return None."""
        service = ApiKeyService(test_session)
        _, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="expiring-key",
            scopes=["servers:read"],
            expires_in_days=1,
        )

        # Move forward 2 days
        with freeze_time(datetime.now(UTC) + timedelta(days=2)):
            user = await service.authenticate(plaintext)
            assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_returns_none_for_wrong_prefix(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Key with wrong prefix should return None."""
        service = ApiKeyService(test_session)
        user = await service.authenticate("wrongprefix_abc123")
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_updates_last_used_at(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Authenticating should update last_used_at."""
        service = ApiKeyService(test_session)
        api_key, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="usage-key",
            scopes=["servers:read"],
        )
        assert api_key.last_used_at is None

        await service.authenticate(plaintext)

        # Flush and reload to get updated value
        await test_session.flush()
        repo = ApiKeyRepository(test_session)
        updated = await repo.get_by_id(api_key.id)
        assert updated is not None
        assert updated.last_used_at is not None
        assert (datetime.now(UTC) - updated.last_used_at).total_seconds() < 5


class TestRevokeKey:
    """Tests for ApiKeyService.revoke_key()."""

    @pytest.mark.asyncio
    async def test_revoke_key_marks_revoked(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Revoking a key should set revoked_at."""
        service = ApiKeyService(test_session)
        api_key, _ = await service.create_key(
            user_id=auth_user.id,
            name="revoke-me",
            scopes=["servers:read"],
        )
        assert api_key.revoked_at is None

        await service.revoke_key(key_id=api_key.id, user_id=auth_user.id)
        await test_session.flush()

        repo = ApiKeyRepository(test_session)
        updated = await repo.get_by_id(api_key.id)
        assert updated is not None
        assert updated.revoked_at is not None

    @pytest.mark.asyncio
    async def test_revoke_key_only_owner_can_revoke(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Non-owner should get ForbiddenError."""
        service = ApiKeyService(test_session)
        api_key, _ = await service.create_key(
            user_id=auth_user.id,
            name="owners-only",
            scopes=["servers:read"],
        )

        other_user_id = UUID("00000000-0000-0000-0000-000000000001")

        from app.core.exceptions import ForbiddenError

        with pytest.raises(ForbiddenError, match="You do not own this API key"):
            await service.revoke_key(key_id=api_key.id, user_id=other_user_id)

    @pytest.mark.asyncio
    async def test_revoke_key_not_found(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Revoking a non-existent key should raise NotFoundError."""
        service = ApiKeyService(test_session)
        fake_id = UUID("00000000-0000-0000-0000-000000000000")

        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError, match="API key not found"):
            await service.revoke_key(key_id=fake_id, user_id=auth_user.id)


class TestCheckScope:
    """Tests for ApiKeyService.check_scope()."""

    def test_check_scope_admin_grants_all(
        self,
    ) -> None:
        """Admin scope should grant access to any scope."""
        key = ApiKey(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            name="admin-key",
            key_prefix="mcpforge_adm",
            key_hash="hash",
            scopes=["admin"],
        )
        assert ApiKeyService.check_scope(key, "servers:read") is True
        assert ApiKeyService.check_scope(key, "servers:write") is True
        assert ApiKeyService.check_scope(key, "analytics:read") is True

    def test_check_scope_specific_scope_required(
        self,
    ) -> None:
        """Non-admin scopes should be checked exactly."""
        key = ApiKey(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            name="read-only-key",
            key_prefix="mcpforge_re",
            key_hash="hash",
            scopes=["servers:read"],
        )
        assert ApiKeyService.check_scope(key, "servers:read") is True
        assert ApiKeyService.check_scope(key, "servers:write") is False
        assert ApiKeyService.check_scope(key, "analytics:read") is False

    def test_check_scope_returns_false_for_missing(
        self,
    ) -> None:
        """Missing scope on non-admin key should return False."""
        key = ApiKey(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            name="no-scope-key",
            key_prefix="mcpforge_no",
            key_hash="hash",
            scopes=[],
        )
        assert ApiKeyService.check_scope(key, "servers:read") is False


class TestRepository:
    """Tests for ApiKeyRepository."""

    @pytest.mark.asyncio
    async def test_count_active_for_user(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """count_active_for_user should return correct count."""
        repo = ApiKeyRepository(test_session)
        service = ApiKeyService(test_session)

        assert await repo.count_active_for_user(auth_user.id) == 0

        await service.create_key(
            user_id=auth_user.id,
            name="key-1",
            scopes=["servers:read"],
        )
        assert await repo.count_active_for_user(auth_user.id) == 1

        # Revoked keys should not count
        key2, _ = await service.create_key(
            user_id=auth_user.id,
            name="key-2",
            scopes=["servers:read"],
        )
        assert await repo.count_active_for_user(auth_user.id) == 2

        await service.revoke_key(key_id=key2.id, user_id=auth_user.id)
        assert await repo.count_active_for_user(auth_user.id) == 1

    @pytest.mark.asyncio
    async def test_list_for_user_excludes_revoked_by_default(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """list_for_user should exclude revoked keys by default."""
        repo = ApiKeyRepository(test_session)
        service = ApiKeyService(test_session)

        key1, _ = await service.create_key(
            user_id=auth_user.id,
            name="key-1",
            scopes=["servers:read"],
        )
        key2, _ = await service.create_key(
            user_id=auth_user.id,
            name="key-2",
            scopes=["servers:read"],
        )

        keys = await repo.list_for_user(auth_user.id)
        assert len(keys) == 2

        await service.revoke_key(key_id=key2.id, user_id=auth_user.id)

        keys = await repo.list_for_user(auth_user.id)
        assert len(keys) == 1
        assert keys[0].id == key1.id

    @pytest.mark.asyncio
    async def test_list_for_user_includes_revoked_when_requested(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """list_for_user should include revoked keys when requested."""
        repo = ApiKeyRepository(test_session)
        service = ApiKeyService(test_session)

        key1, _ = await service.create_key(
            user_id=auth_user.id,
            name="key-1",
            scopes=["servers:read"],
        )
        await service.revoke_key(key_id=key1.id, user_id=auth_user.id)

        keys = await repo.list_for_user(auth_user.id, include_revoked=True)
        assert len(keys) == 1

    @pytest.mark.asyncio
    async def test_get_by_hash(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """get_by_hash should find a key by its SHA-256 hash."""
        repo = ApiKeyRepository(test_session)
        service = ApiKeyService(test_session)
        _, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="hash-key",
            scopes=["servers:read"],
        )

        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        found = await repo.get_by_hash(key_hash)
        assert found is not None
        assert found.name == "hash-key"

        not_found = await repo.get_by_hash("nonexistent-hash")
        assert not_found is None


# ── Integration tests (HTTP endpoints) ──────────────────────────────────


class TestAPIKeyEndpoints:
    """Tests for the API key HTTP endpoints."""

    LIST_URL = "/api/v1/api-keys"
    CREATE_URL = "/api/v1/api-keys"

    @pytest.mark.asyncio
    async def test_list_keys_empty(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """GET /api/v1/api-keys should return empty list initially."""
        response = await auth_client.get(self.LIST_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_create_and_list_keys(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """POST then GET should show the created key."""
        create_resp = await auth_client.post(
            self.CREATE_URL,
            json={"name": "my-key", "scopes": ["servers:read"]},
        )
        assert create_resp.status_code == 201
        create_data = create_resp.json()
        assert "plaintext_key" in create_data
        assert create_data["plaintext_key"].startswith("mcpforge_live_")
        assert create_data["name"] == "my-key"
        assert create_data["scopes"] == ["servers:read"]

        # List should show the key (without plaintext)
        list_resp = await auth_client.get(self.LIST_URL)
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] == 1
        assert list_data["items"][0]["name"] == "my-key"
        assert "plaintext_key" not in list_data["items"][0]

    @pytest.mark.asyncio
    async def test_revoke_key(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """DELETE /api/v1/api-keys/{id} should revoke the key."""
        # Create
        create_resp = await auth_client.post(
            self.CREATE_URL,
            json={"name": "doomed-key", "scopes": ["servers:read"]},
        )
        key_id = create_resp.json()["id"]

        # Revoke
        delete_resp = await auth_client.delete(f"{self.LIST_URL}/{key_id}")
        assert delete_resp.status_code == 204

        # List should not include it
        list_resp = await auth_client.get(self.LIST_URL)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_key(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """DELETE with non-existent ID should return 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await auth_client.delete(f"{self.LIST_URL}/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_key_invalid_scope(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """POST with invalid scope should return 422."""
        response = await auth_client.post(
            self.CREATE_URL,
            json={"name": "bad-key", "scopes": ["servers:read", "servers:delete"]},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_key_exceeds_limit(
        self,
        auth_client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """POST after 5 keys should return 409."""
        service = ApiKeyService(test_session)
        for i in range(5):
            await service.create_key(
                user_id=auth_user.id,
                name=f"key-{i}",
                scopes=["servers:read"],
            )
        await test_session.commit()

        response = await auth_client.post(
            self.CREATE_URL,
            json={"name": "too-many", "scopes": ["servers:read"]},
        )
        assert response.status_code == 402

    @pytest.mark.asyncio
    async def test_api_key_can_authenticate_to_me_endpoint(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Using the API key as Bearer token should authenticate to /auth/me.

        This is an integration test: we create a key via the service directly,
        then call /me with ``Authorization: Bearer <plaintext>`` instead of a
        JWT cookie. We use ``client`` (not ``auth_client``) so that the
        real ``get_current_user`` dependency runs (no override).
        """
        # Create a key for the auth_user directly via the service
        service = ApiKeyService(test_session)
        _, plaintext = await service.create_key(
            user_id=auth_user.id,
            name="auth-test-key",
            scopes=["servers:read"],
        )
        await test_session.commit()

        # Now call /me with the API key as Bearer token
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {plaintext}"},
        )
        assert me_response.status_code == 200
        data = me_response.json()
        assert data["email"] == auth_user.email
