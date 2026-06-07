"""Tests for SpecRepository."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.spec_repo import SpecRepository


@pytest.fixture
async def user(test_session: AsyncSession) -> User:
    """Create a test user for spec repo tests."""
    u = User(
        email=f"spec-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
        display_name="Spec Tester",
    )
    test_session.add(u)
    await test_session.flush()
    return u


class TestSpecRepository:
    """Test suite for SpecRepository."""

    async def test_create_and_get_by_id(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """Create a SpecSource, then get_by_id returns full object."""
        repo = SpecRepository(test_session)
        spec = await repo.create(
            user_id=user.id,
            source_type="url",
            source_url="https://example.com/openapi.json",
            title="Test API",
            endpoint_count=5,
            spec_size_bytes=1024,
        )

        assert spec.id is not None
        assert spec.source_type == "url"
        assert spec.source_url == "https://example.com/openapi.json"
        assert spec.title == "Test API"
        assert spec.endpoint_count == 5
        assert spec.spec_size_bytes == 1024
        assert spec.fetch_status == "pending"

        fetched = await repo.get_by_id(spec.id)
        assert fetched is not None
        assert fetched.id == spec.id
        assert fetched.source_url == "https://example.com/openapi.json"
        assert fetched.title == "Test API"

    async def test_list_by_user_paginates(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """list_by_user with limit returns only up to limit items."""
        repo = SpecRepository(test_session)
        for i in range(3):
            await repo.create(
                user_id=user.id,
                source_type="url",
                source_url=f"https://example.com/api{i}.json",
            )

        results = await repo.list_by_user(user.id, skip=0, limit=2)
        assert len(results) == 2

    async def test_list_by_user_respects_skip(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """list_by_user with skip returns correct page."""
        repo = SpecRepository(test_session)
        for i in range(3):
            await repo.create(
                user_id=user.id,
                source_type="url",
                source_url=f"https://example.com/api{i}.json",
            )

        page2 = await repo.list_by_user(user.id, skip=2, limit=2)
        assert len(page2) == 1

    async def test_get_by_user_and_hash_matches(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """get_by_user_and_hash finds spec by SHA-256 in r2_key pattern."""
        repo = SpecRepository(test_session)
        sha = "abc123def456"
        r2_key = f"{user.id}/{sha}.json"
        await repo.create(
            user_id=user.id,
            source_type="upload",
            r2_key=r2_key,
            title="Hashed Spec",
        )

        found = await repo.get_by_user_and_hash(user.id, sha)
        assert found is not None
        assert found.r2_key == r2_key
        assert found.title == "Hashed Spec"

    async def test_get_by_user_and_hash_no_match(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """get_by_user_and_hash returns None when no match."""
        repo = SpecRepository(test_session)
        await repo.create(
            user_id=user.id,
            source_type="url",
            source_url="https://example.com/api.json",
        )

        found = await repo.get_by_user_and_hash(user.id, "nonexistent")
        assert found is None

    async def test_get_by_user_and_hash_other_user(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """get_by_user_and_hash does not return specs for other users."""
        # Create second user
        other_user = User(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash",
        )
        test_session.add(other_user)
        await test_session.flush()

        repo = SpecRepository(test_session)
        sha = "abc123"
        await repo.create(
            user_id=other_user.id,
            source_type="upload",
            r2_key=f"{other_user.id}/{sha}.json",
        )

        found = await repo.get_by_user_and_hash(user.id, sha)
        assert found is None

    async def test_update_status(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """update_status changes fetch_status and persists it."""
        repo = SpecRepository(test_session)
        spec = await repo.create(
            user_id=user.id,
            source_type="url",
            source_url="https://example.com/api.json",
        )

        assert spec.fetch_status == "pending"

        updated = await repo.update_status(spec, status="fetched")
        assert updated.fetch_status == "fetched"

        # Verify persistence via fresh read
        re_fetched = await repo.get_by_id(spec.id)
        assert re_fetched is not None
        assert re_fetched.fetch_status == "fetched"

    async def test_update_status_with_error(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """update_status can set an error message."""
        repo = SpecRepository(test_session)
        spec = await repo.create(
            user_id=user.id,
            source_type="url",
            source_url="https://example.com/api.json",
        )

        updated = await repo.update_status(
            spec, status="error", error="Connection refused"
        )
        assert updated.fetch_status == "error"
        assert updated.fetch_error == "Connection refused"

    async def test_delete_removes_row(
        self, test_session: AsyncSession, user: User
    ) -> None:
        """delete removes the spec from the database."""
        repo = SpecRepository(test_session)
        spec = await repo.create(
            user_id=user.id,
            source_type="url",
            source_url="https://example.com/api.json",
        )
        spec_id = spec.id

        await repo.delete(spec)

        fetched = await repo.get_by_id(spec_id)
        assert fetched is None

    async def test_get_by_id_nonexistent(
        self, test_session: AsyncSession
    ) -> None:
        """get_by_id returns None for a non-existent UUID."""
        repo = SpecRepository(test_session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None
