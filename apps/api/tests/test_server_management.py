"""Tests for server management endpoints (duplicate, versions, rollback).

Requires a running test database (SQLite or PostgreSQL). Uses the same
pattern as ``test_servers.py`` for fixtures and HTTP clients.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

SERVERS_URL = "/api/v1/servers"
SERVER_SLUG = "my-test-server"
SERVER_NAME = "My Test Server"
SERVER_BASE_URL = "https://api.example.com"

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
async def test_server(auth_client: AsyncClient) -> dict:
    """Create a test server and return its data."""
    resp = await auth_client.post(
        SERVERS_URL,
        json={
            "name": SERVER_NAME,
            "slug": SERVER_SLUG,
            "base_url": SERVER_BASE_URL,
            "tools_config": {
                "tools": [
                    {"name": "get_users", "description": "Fetch users"},
                    {"name": "create_user", "description": "Create a user"},
                ]
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ── Duplicate tests ──────────────────────────────────────────────────────


class TestDuplicateServer:
    """Tests for POST /servers/{id}/duplicate."""

    @pytest.mark.asyncio
    async def test_duplicate_server_creates_copy_with_new_name(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Duplicate creates a new server with the specified name."""
        dup_name = "Duplicated Server"
        resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/duplicate",
            json={"new_name": dup_name},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == dup_name
        assert data["id"] != test_server["id"]
        assert data["slug"] != test_server["slug"]

    @pytest.mark.asyncio
    async def test_duplicate_server_copies_tools_config(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Duplicate copies tools_config from the source."""
        resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/duplicate",
            json={"new_name": "Copy of Server"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tools_config"] == test_server["tools_config"]
        # Should be a different object in memory (deep copy)
        assert data["tools_config"] is not test_server["tools_config"]

    @pytest.mark.asyncio
    async def test_duplicate_server_resets_version_and_stats(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Duplicate resets version to 1 and stats to 0."""
        resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/duplicate",
            json={"new_name": "Fresh Copy"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == 1
        assert data["total_calls"] == 0
        assert data["monthly_calls"] == 0
        assert data["status"] == "building"

    @pytest.mark.asyncio
    async def test_duplicate_server_generates_unique_slug_on_collision(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
        test_server: dict,
    ) -> None:
        """When the generated slug collides, append -copy-N suffix."""
        # Ensure user has room in their plan
        auth_user.plan = "pro"
        await test_session.flush()

        # Create another server with known slug
        occupied_slug = "second-server"
        resp = await auth_client.post(
            SERVERS_URL,
            json={
                "name": "Second Server",
                "slug": occupied_slug,
                "base_url": "https://other.com",
            },
        )
        assert resp.status_code == 201

        # Request duplicate with new_slug that matches occupied_slug
        resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/duplicate",
            json={"new_name": "Collision Test", "new_slug": occupied_slug},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] != occupied_slug
        assert data["slug"].startswith(occupied_slug)

    @pytest.mark.asyncio
    async def test_duplicate_server_respects_plan_limit(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
        test_server: dict,
    ) -> None:
        """Free user with 2 servers gets 402 on 3rd."""
        # Set user to free plan
        auth_user.plan = "free"
        await test_session.flush()

        # Create second server (free plan allows 2)
        resp = await auth_client.post(
            SERVERS_URL,
            json={
                "name": "Server 2",
                "slug": "server-2",
                "base_url": "https://example2.com",
            },
        )
        assert resp.status_code == 201

        # Try to duplicate — should hit plan limit
        resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/duplicate",
            json={"new_name": "Should Fail"},
        )
        assert resp.status_code == 402

        # Reset plan for other tests
        auth_user.plan = "pro"
        await test_session.flush()

    @pytest.mark.asyncio
    async def test_duplicate_server_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Duplicate without auth returns 401."""
        resp = await client.post(
            f"{SERVERS_URL}/{uuid.uuid4()}/duplicate",
            json={"new_name": "Hacker Copy"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_duplicate_server_404_on_nonexistent(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Duplicate a non-existent server returns 404."""
        fake_id = uuid.uuid4()
        resp = await auth_client.post(
            f"{SERVERS_URL}/{fake_id}/duplicate",
            json={"new_name": "Ghost Copy"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_server_accepts_custom_slug(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Duplicate with explicit new_slug uses it."""
        custom_slug = "my-custom-copy"
        resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/duplicate",
            json={"new_name": "Custom Slug Copy", "new_slug": custom_slug},
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == custom_slug


# ── Versions tests ───────────────────────────────────────────────────────


class TestListVersions:
    """Tests for GET /servers/{id}/versions."""

    @pytest.mark.asyncio
    async def test_list_versions_returns_empty_for_new_server(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """A newly created server has no version history yet."""
        resp = await auth_client.get(f"{SERVERS_URL}/{test_server['id']}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_versions_returns_snapshot_after_update(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Updating a server creates a version snapshot."""
        # Update the server (triggers snapshot)
        await auth_client.patch(
            f"{SERVERS_URL}/{test_server['id']}",
            json={"name": "Updated Name"},
        )

        resp = await auth_client.get(f"{SERVERS_URL}/{test_server['id']}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        # The snapshot should have version=1 (initial state before update)
        assert any(item["version"] == 1 for item in data["items"])

    @pytest.mark.asyncio
    async def test_list_versions_returns_ordered_history(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Versions are returned newest first."""
        # Perform multiple updates
        for i in range(3):
            await auth_client.patch(
                f"{SERVERS_URL}/{test_server['id']}",
                json={"name": f"Update {i}"},
            )

        resp = await auth_client.get(f"{SERVERS_URL}/{test_server['id']}/versions")
        data = resp.json()
        versions = [item["version"] for item in data["items"]]
        assert versions == sorted(versions, reverse=True), "Versions not in DESC order"

    @pytest.mark.asyncio
    async def test_list_versions_paginates(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Versions are paginated with skip and limit."""
        # Perform 5 updates to generate some history
        for i in range(5):
            await auth_client.patch(
                f"{SERVERS_URL}/{test_server['id']}",
                json={"name": f"Update {i}"},
            )

        # Get first 2
        resp = await auth_client.get(
            f"{SERVERS_URL}/{test_server['id']}/versions?skip=0&limit=2"
        )
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5  # 5 updates created 5 snapshots
        assert data["skip"] == 0
        assert data["limit"] == 2

    @pytest.mark.asyncio
    async def test_list_versions_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Versions without auth returns 401."""
        resp = await client.get(f"{SERVERS_URL}/{uuid.uuid4()}/versions")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_versions_404_on_nonexistent(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Versions for non-existent server returns 404."""
        fake_id = uuid.uuid4()
        resp = await auth_client.get(f"{SERVERS_URL}/{fake_id}/versions")
        assert resp.status_code == 404


# ── Rollback tests ───────────────────────────────────────────────────────


class TestRollbackServer:
    """Tests for POST /servers/{id}/rollback."""

    @pytest.mark.asyncio
    async def test_rollback_restores_tools_config(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Rollback restores tools_config from the target version."""
        sid = test_server["id"]
        original_config = test_server["tools_config"]

        # Update with new tools_config
        new_config = {"tools": [{"name": "new_tool"}]}
        await auth_client.patch(
            f"{SERVERS_URL}/{sid}",
            json={"tools_config": new_config},
        )

        # Get the version history to find the target version
        versions_resp = await auth_client.get(f"{SERVERS_URL}/{sid}/versions")
        versions = versions_resp.json()["items"]
        # Find the initial snapshot (version=1)
        v1 = next(v for v in versions if v["version"] == 1)

        # Rollback to version 1
        resp = await auth_client.post(
            f"{SERVERS_URL}/{sid}/rollback",
            json={"version": v1["version"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tools_config"] == original_config

    @pytest.mark.asyncio
    async def test_rollback_creates_snapshot_of_current_state(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Rollback creates a snapshot of the current state first."""
        sid = test_server["id"]

        # Update tools_config
        await auth_client.patch(
            f"{SERVERS_URL}/{sid}",
            json={"tools_config": {"tools": [{"name": "updated"}]}},
        )

        # Get version before rollback
        pre_resp = await auth_client.get(f"{SERVERS_URL}/{sid}/versions")
        pre_count = pre_resp.json()["total"]

        # Rollback to v1
        await auth_client.post(
            f"{SERVERS_URL}/{sid}/rollback",
            json={"version": 1},
        )

        # A new snapshot should have been added
        post_resp = await auth_client.get(f"{SERVERS_URL}/{sid}/versions")
        post_count = post_resp.json()["total"]
        assert post_count == pre_count + 1, "Rollback did not create a snapshot"

    @pytest.mark.asyncio
    async def test_rollback_increments_version_counter(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Rollback increments the server's version counter."""
        sid = test_server["id"]
        assert test_server["version"] == 1

        # Update to bump version
        await auth_client.patch(
            f"{SERVERS_URL}/{sid}",
            json={"name": "v2"},
        )
        get_resp = await auth_client.get(f"{SERVERS_URL}/{sid}")
        assert get_resp.json()["version"] == 2

        # Rollback to v1
        await auth_client.post(
            f"{SERVERS_URL}/{sid}/rollback",
            json={"version": 1},
        )

        get_resp = await auth_client.get(f"{SERVERS_URL}/{sid}")
        assert get_resp.json()["version"] == 3, "Version should increment on rollback"

    @pytest.mark.asyncio
    async def test_rollback_to_nonexistent_version_returns_404(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Rollback to a version that doesn't exist returns 404."""
        resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/rollback",
            json={"version": 999},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rollback_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """Rollback without auth returns 401."""
        resp = await client.post(
            f"{SERVERS_URL}/{uuid.uuid4()}/rollback",
            json={"version": 1},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_rollback_404_on_nonexistent_server(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Rollback on non-existent server returns 404."""
        fake_id = uuid.uuid4()
        resp = await auth_client.post(
            f"{SERVERS_URL}/{fake_id}/rollback",
            json={"version": 1},
        )
        assert resp.status_code == 404


# ── Integration / edge-case tests ────────────────────────────────────────


class TestServerManagementIntegration:
    """Integrated scenarios for server management."""

    @pytest.mark.asyncio
    async def test_update_server_creates_version_snapshot(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """Updating a server creates a version history record."""
        sid = test_server["id"]

        # Initial: no versions yet
        resp = await auth_client.get(f"{SERVERS_URL}/{sid}/versions")
        assert resp.json()["total"] == 0

        # Update name
        await auth_client.patch(
            f"{SERVERS_URL}/{sid}",
            json={"name": "Versioned Name"},
        )

        # Now there should be 1 version
        resp = await auth_client.get(f"{SERVERS_URL}/{sid}/versions")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["version"] == 1
        assert data["items"][0]["change_note"] == "Updated via API"

    @pytest.mark.asyncio
    async def test_update_server_version_has_changed_by(
        self,
        auth_client: AsyncClient,
        test_server: dict,
        auth_user: User,
    ) -> None:
        """Version snapshot records who made the change."""
        sid = test_server["id"]

        await auth_client.patch(
            f"{SERVERS_URL}/{sid}",
            json={"description": "Updated description"},
        )

        resp = await auth_client.get(f"{SERVERS_URL}/{sid}/versions")
        data = resp.json()
        assert data["items"][0]["changed_by"] == str(auth_user.id)

    @pytest.mark.asyncio
    async def test_full_duplicate_versions_rollback_cycle(
        self,
        auth_client: AsyncClient,
        test_server: dict,
    ) -> None:
        """End-to-end: duplicate → update → verify versions → rollback."""
        # 1. Duplicate
        dup_resp = await auth_client.post(
            f"{SERVERS_URL}/{test_server['id']}/duplicate",
            json={"new_name": "Cycle Test Copy"},
        )
        assert dup_resp.status_code == 201
        dup = dup_resp.json()

        # 2. Update the duplicate's tools_config
        new_config = {"tools": [{"name": "cycle-tool"}]}
        await auth_client.patch(
            f"{SERVERS_URL}/{dup['id']}",
            json={"tools_config": new_config},
        )

        # 3. Verify versions exist
        ver_resp = await auth_client.get(f"{SERVERS_URL}/{dup['id']}/versions")
        assert ver_resp.json()["total"] >= 1

        # 4. Rollback to v1
        roll_resp = await auth_client.post(
            f"{SERVERS_URL}/{dup['id']}/rollback",
            json={"version": 1},
        )
        assert roll_resp.status_code == 200
        # The rolled-back config should match the duplicate's original
        # (which equals test_server's tools_config since we deep-copied)
        assert roll_resp.json()["tools_config"] == test_server["tools_config"]
