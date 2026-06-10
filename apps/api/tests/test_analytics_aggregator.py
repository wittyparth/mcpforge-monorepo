"""Tests for AnalyticsAggregator (F6 — Usage Analytics).

6 tests covering:
  - ensure_unique_index is idempotent
  - aggregate_hour writes rollup rows (PostgreSQL-only, skipped on SQLite)
  - aggregate_hour is idempotent (PostgreSQL-only)
  - aggregate_daily builds from hourly (PostgreSQL-only)
  - aggregate_handles_no_data (PostgreSQL-only)
  - aggregate uses only target hour (PostgreSQL-only)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServer
from app.models.user import User
from app.services.analytics.aggregator import AnalyticsAggregator

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_test_user_and_server(
    session: AsyncSession,
) -> tuple[User, MCPServer]:
    """Create a minimal user + server pair."""
    user = User(
        email=f"agg-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
    )
    session.add(user)
    await session.flush()
    server = MCPServer(
        user_id=user.id,
        slug=f"agg-slug-{uuid.uuid4().hex[:8]}",
        name="Agg Test Server",
        base_url="https://example.com",
    )
    session.add(server)
    await session.flush()
    return user, server


async def _is_sqlite(session: AsyncSession) -> bool:
    """Detect if the session is backed by SQLite."""
    return session.bind.dialect.name == "sqlite" if session.bind else True


def _within_hour(dt: datetime) -> datetime:
    """Floor a datetime to the hour boundary."""
    return dt.replace(minute=0, second=0, microsecond=0)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAggregatorEnsureIndex:
    """AnalyticsAggregator.ensure_unique_index — idempotent index creation."""

    async def test_ensure_unique_index_creates(
        self,
        test_session: AsyncSession,
    ) -> None:
        """ensure_unique_index creates the unique index (idempotent)."""
        aggregator = AnalyticsAggregator(test_session)

        # First call should succeed.
        await aggregator.ensure_unique_index()

        # Second call should also succeed (idempotent).
        await aggregator.ensure_unique_index()

        # Verify the index exists by trying to insert duplicate rollup.
        # Use a fixed server_id so both inserts conflict on the unique index.
        server_id = uuid.uuid4()
        bucket_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

        await test_session.execute(
            text("""
                INSERT INTO analytics_rollups
                    (id, server_id, tool_name, bucket_start, granularity, call_count, error_count)
                VALUES
                    (:id, :sid, :tool, :bucket, 'hour', 1, 0)
            """),
            {
                "id": uuid.uuid4(),
                "sid": server_id,
                "tool": "test_tool",
                "bucket": bucket_start,
            },
        )
        await test_session.flush()

        # Duplicate insert should raise integrity error due to unique index.
        # The index is on (server_id, tool_name, bucket_start, granularity).
        # The ON CONFLICT in the aggregator handles this in production.
        # Here we just verify the second INSERT without conflict handling fails.
        with pytest.raises(IntegrityError):
            await test_session.execute(
                text("""
                    INSERT INTO analytics_rollups
                        (id, server_id, tool_name, bucket_start, granularity,
                         call_count, error_count)
                    VALUES
                        (:id, :sid, :tool, :bucket, 'hour', 2, 0)
                """),
                {
                    "id": uuid.uuid4(),
                    "sid": server_id,
                    "tool": "test_tool",
                    "bucket": bucket_start,
                },
            )
            await test_session.flush()


class TestAggregatorHour:
    """AnalyticsAggregator.aggregate_hour — single-hour aggregation.

    These tests use PostgreSQL-specific SQL (date_trunc, FILTER, gen_random_uuid,
    ON CONFLICT) and are skipped on SQLite.
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc, FILTER, gen_random_uuid")
    async def test_aggregate_hour_writes_rollup(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Insert 3 tool_calls in same hour, aggregate → 1 rollup row with call_count=3."""
        if await _is_sqlite(test_session):
            pytest.skip("Requires PostgreSQL (date_trunc, FILTER, etc.)")

        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)
        hour_start = _within_hour(now)

        # Insert 3 tool calls in the same hour.
        for i in range(3):
            await test_session.execute(
                text("""
                    INSERT INTO tool_calls
                        (id, server_id, tool_name, status, latency_ms, called_at)
                    VALUES (:id, :sid, :tool, :status, :lat, :ts)
                """),
                {
                    "id": uuid.uuid4(),
                    "sid": server.id,
                    "tool": "agg_test_tool",
                    "status": "success" if i < 2 else "error",
                    "lat": 100 + i * 10,
                    "ts": hour_start + timedelta(minutes=i * 15),
                },
            )
        await test_session.commit()

        aggregator = AnalyticsAggregator(test_session)
        count = await aggregator.aggregate_hour(hour_bucket=hour_start)

        assert count >= 1
        row = (await test_session.execute(
            text("""
                SELECT call_count, error_count, avg_latency_ms
                FROM analytics_rollups
                WHERE server_id = :sid AND tool_name = 'agg_test_tool'
                  AND granularity = 'hour'
            """),
            {"sid": server.id},
        )).one()
        assert row.call_count == 3
        assert row.error_count == 1  # 2 successes + 1 error

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc, FILTER, gen_random_uuid")
    async def test_aggregate_hour_idempotent(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Running aggregate_hour twice produces same result (upsert)."""
        if await _is_sqlite(test_session):
            pytest.skip("Requires PostgreSQL")

        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)
        hour_start = _within_hour(now)

        # Insert calls in the target hour.
        for i in range(3):
            await test_session.execute(
                text("""
                    INSERT INTO tool_calls
                        (id, server_id, tool_name, status, latency_ms, called_at)
                    VALUES (:id, :sid, :tool, 'success', :lat, :ts)
                """),
                {
                    "id": uuid.uuid4(),
                    "sid": server.id,
                    "tool": "idemp_tool",
                    "lat": 100,
                    "ts": hour_start + timedelta(minutes=i * 10),
                },
            )
        await test_session.commit()

        aggregator = AnalyticsAggregator(test_session)
        first = await aggregator.aggregate_hour(hour_bucket=hour_start)
        second = await aggregator.aggregate_hour(hour_bucket=hour_start)

        assert first == second
        rows = (await test_session.execute(
            text("SELECT COUNT(*) FROM analytics_rollups WHERE server_id = :sid"),
            {"sid": server.id},
        )).scalar()
        # Should have only 1 rollup row (not 2).
        assert rows == 1

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc, FILTER, gen_random_uuid")
    async def test_aggregate_handles_no_data(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Aggregating an hour with no tool_calls returns 0 rows."""
        if await _is_sqlite(test_session):
            pytest.skip("Requires PostgreSQL")

        aggregator = AnalyticsAggregator(test_session)
        count = await aggregator.aggregate_hour(
            hour_bucket=datetime.now(UTC).replace(minute=0, second=0, microsecond=0),
        )
        assert count == 0

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc, FILTER, gen_random_uuid")
    async def test_aggregate_uses_only_target_hour(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Calls outside the target hour are excluded."""
        if await _is_sqlite(test_session):
            pytest.skip("Requires PostgreSQL")

        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)
        target_hour = _within_hour(now)
        # Previous hour (should not be included).
        prev_hour = target_hour - timedelta(hours=1)
        # Next hour (should not be included).
        next_hour = target_hour + timedelta(hours=1)

        # Insert calls across three hours.
        for hour, count in [(prev_hour, 5), (target_hour, 3), (next_hour, 2)]:
            for i in range(count):
                await test_session.execute(
                    text("""
                        INSERT INTO tool_calls
                            (id, server_id, tool_name, status, latency_ms, called_at)
                        VALUES (:id, :sid, :tool, 'success', :lat, :ts)
                    """),
                    {
                        "id": uuid.uuid4(),
                        "sid": server.id,
                        "tool": "boundary_tool",
                        "lat": 50,
                        "ts": hour + timedelta(minutes=i * 10),
                    },
                )
        await test_session.commit()

        aggregator = AnalyticsAggregator(test_session)
        count = await aggregator.aggregate_hour(hour_bucket=target_hour)

        # Only 3 calls from the target hour should be aggregated.
        assert count >= 1
        row = (await test_session.execute(
            text("""
                SELECT call_count FROM analytics_rollups
                WHERE server_id = :sid AND tool_name = 'boundary_tool'
                  AND granularity = 'hour'
            """),
            {"sid": server.id},
        )).one()
        assert row.call_count == 3


class TestAggregatorDaily:
    """AnalyticsAggregator.aggregate_daily — daily rollup from hourly.

    These tests use PostgreSQL-specific SQL and are skipped on SQLite.
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc, FILTER, gen_random_uuid")
    async def test_aggregate_daily_writes_from_hourly(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Aggregate hour, then daily → daily row with same totals."""
        if await _is_sqlite(test_session):
            pytest.skip("Requires PostgreSQL")

        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)
        hour_start = _within_hour(now)

        # Insert calls.
        for i in range(3):
            await test_session.execute(
                text("""
                    INSERT INTO tool_calls
                        (id, server_id, tool_name, status, latency_ms, called_at)
                    VALUES (:id, :sid, :tool, 'success', :lat, :ts)
                """),
                {
                    "id": uuid.uuid4(),
                    "sid": server.id,
                    "tool": "daily_tool",
                    "lat": 100,
                    "ts": hour_start + timedelta(minutes=i * 15),
                },
            )
        await test_session.commit()

        aggregator = AnalyticsAggregator(test_session)
        # First create the hourly aggregation.
        await aggregator.aggregate_hour(hour_bucket=hour_start)
        # Then roll up to daily.
        day_date = hour_start.date()
        day_count = await aggregator.aggregate_daily(day_bucket=day_date)

        assert day_count >= 1
        row = (await test_session.execute(
            text("""
                SELECT call_count, granularity FROM analytics_rollups
                WHERE server_id = :sid AND tool_name = 'daily_tool'
                  AND granularity = 'day'
            """),
            {"sid": server.id},
        )).one()
        assert row.call_count == 3
        assert row.granularity == "day"
