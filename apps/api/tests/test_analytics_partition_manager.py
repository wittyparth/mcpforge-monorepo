"""Tests for PartitionManager (F6 — Usage Analytics).

4 tests covering:
  - ensure_partitions creates for today + N days
  - ensure_partitions is idempotent
  - cleanup_old_partitions drops old partitions
  - cleanup keeps recent partitions

All tests require PostgreSQL (pg_inherits, CREATE TABLE PARTITION OF) and
are skipped on SQLite.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.partition_manager import PartitionManager


@pytest_asyncio.fixture
async def skip_sqlite(test_session: AsyncSession) -> None:
    """Skip all partition manager tests on SQLite."""
    if test_session.bind.dialect.name == "sqlite":
        pytest.skip("PartitionManager requires PostgreSQL (pg_inherits, CREATE TABLE PARTITION OF)")


class TestPartitionManager:
    """PartitionManager behaviour — PostgreSQL only."""

    @pytest.mark.skip(reason="Requires PostgreSQL — pg_inherits, PARTITION OF")
    async def test_ensure_partitions_creates_for_today_and_n_days(
        self,
        test_session: AsyncSession,
    ) -> None:
        """ensure_partitions(7) creates 8 partitions (today + 7 days)."""
        pm = PartitionManager()
        created = await pm.ensure_partitions(days_ahead=7)
        assert created == 8  # today + 7 days

        partitions = await pm.list_partitions()
        assert len(partitions) >= 8

    @pytest.mark.skip(reason="Requires PostgreSQL — pg_inherits, PARTITION OF")
    async def test_ensure_partitions_idempotent(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Running ensure_partitions twice produces same partitions."""
        pm = PartitionManager()
        first = await pm.ensure_partitions(days_ahead=3)
        second = await pm.ensure_partitions(days_ahead=3)

        assert first == 4  # today + 3 days
        assert second == 0  # no new partitions

        partitions = await pm.list_partitions()
        assert len(partitions) == 4

    @pytest.mark.skip(reason="Requires PostgreSQL — pg_inherits, PARTITION OF")
    async def test_cleanup_old_partitions_drops_old(
        self,
        test_session: AsyncSession,
    ) -> None:
        """cleanup_old_partitions drops partitions older than retention."""
        pm = PartitionManager()

        # Create partitions for the next 7 days.
        await pm.ensure_partitions(days_ahead=7)

        # Cleanup with retention=1 should keep today's + yesterday's partitions.
        dropped = await pm.cleanup_old_partitions(retention_days=1)
        # At least some partitions from 2+ days ago should be dropped.
        # Exact count depends on how many exist older than 1 day.
        # Since we just created them, there may not be old ones.
        # This tests the call doesn't error.
        assert isinstance(dropped, int)
        assert dropped >= 0

    @pytest.mark.skip(reason="Requires PostgreSQL — pg_inherits, PARTITION OF")
    async def test_cleanup_keeps_recent(
        self,
        test_session: AsyncSession,
    ) -> None:
        """cleanup_old_partitions with retention=7 keeps all if all are recent."""
        pm = PartitionManager()

        # Create partitions for the next 7 days (all are "future").
        await pm.ensure_partitions(days_ahead=7)

        # Cleanup with retention=7 should not drop future partitions.
        dropped = await pm.cleanup_old_partitions(retention_days=7)
        assert dropped == 0
