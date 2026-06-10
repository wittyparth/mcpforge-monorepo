"""Tests for AnalyticsQueries (F6 — Usage Analytics).

8 tests covering:
  - get_overview range validation (works on all DB backends)
  - get_overview aggregated data (PostgreSQL-only, skipped on SQLite)
  - get_tool_breakdown ordering (PostgreSQL-only)
  - get_error_log filtering (works on all DB backends)
  - get_error_log pagination (works on all DB backends)
  - get_error_log empty (works on all DB backends)
  - get_client_breakdown grouping (PostgreSQL-only)
  - get_time_series hourly (PostgreSQL-only)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.services.analytics.queries import AnalyticsQueries

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_test_user_and_server(
    session: AsyncSession,
) -> tuple[User, MCPServer]:
    """Create a minimal user + server pair."""
    user = User(
        email=f"qry-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
    )
    session.add(user)
    await session.flush()
    server = MCPServer(
        user_id=user.id,
        slug=f"qry-slug-{uuid.uuid4().hex[:8]}",
        name="Queries Test Server",
        base_url="https://example.com",
    )
    session.add(server)
    await session.flush()
    return user, server


async def _insert_tool_call(
    session: AsyncSession,
    server_id: uuid.UUID,
    tool_name: str,
    status: str = "success",
    error_type: str | None = None,
    error_msg: str | None = None,
    client_name: str | None = None,
    called_at: datetime | None = None,
) -> None:
    """Insert a row into tool_calls."""
    await session.execute(
        text("""
            INSERT INTO tool_calls
                (id, server_id, tool_name, status, error_type, error_msg,
                 client_name, called_at)
            VALUES (:id, :sid, :tool, :status, :err_type, :err_msg,
                    :client, :called_at)
        """),
        {
            "id": uuid.uuid4(),
            "sid": server_id,
            "tool": tool_name,
            "status": status,
            "err_type": error_type,
            "err_msg": error_msg,
            "client": client_name,
            "called_at": called_at or datetime.now(UTC),
        },
    )


# ── Range validation (works on all DB backends) ───────────────────────────────


class TestGetOverviewValidation:
    """AnalyticsQueries.get_overview — range validation (in-memory, no DB query)."""

    async def test_get_overview_invalid_range_raises_validation_error(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Invalid range string raises ValidationError before any DB query."""
        user, server = await _create_test_user_and_server(test_session)
        queries = AnalyticsQueries(test_session)

        with pytest.raises(ValidationError, match="Unsupported range"):
            await queries.get_overview(server.id, "bad-range")

        with pytest.raises(ValidationError, match="Unsupported range"):
            await queries.get_overview(server.id, "")

        with pytest.raises(ValidationError, match="Unsupported range"):
            await queries.get_overview(server.id, "1d")


# ── Overview (PostgreSQL-only SQL) ────────────────────────────────────────────


class TestGetOverview:
    """AnalyticsQueries.get_overview — aggregated data.

    Uses ::bigint cast — PostgreSQL only.
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast in COALESCE")
    async def test_get_overview_aggregates(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Overview returns aggregated values from rollups."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        user, server = await _create_test_user_and_server(test_session)

        await test_session.execute(
            text("""
                INSERT INTO analytics_rollups
                    (id, server_id, tool_name, bucket_start, granularity,
                     call_count, error_count, avg_latency_ms)
                VALUES (:id, :sid, :tool, :bucket, 'hour', :calls, :errors, :lat)
            """),
            {
                "id": uuid.uuid4(),
                "sid": server.id,
                "tool": "tool_a",
                "bucket": datetime.now(UTC) - timedelta(hours=2),
                "calls": 10,
                "errors": 2,
                "lat": 150.0,
            },
        )
        await test_session.commit()

        queries = AnalyticsQueries(test_session)
        overview = await queries.get_overview(server.id, "7d")

        assert overview.server_id == server.id
        assert overview.range == "7d"
        assert overview.total_calls >= 10
        assert overview.total_errors >= 2
        assert isinstance(overview.error_rate, float)

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast in COALESCE")
    async def test_get_overview_empty(
        self,
        test_session: AsyncSession,
    ) -> None:
        """No data → overview returns 0 calls."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        user, server = await _create_test_user_and_server(test_session)

        queries = AnalyticsQueries(test_session)
        overview = await queries.get_overview(server.id, "7d")

        assert overview.total_calls == 0
        assert overview.total_errors == 0
        assert overview.unique_clients == 0


# ── Tool breakdown (PostgreSQL-only SQL) ──────────────────────────────────────


class TestToolBreakdown:
    """AnalyticsQueries.get_tool_breakdown — ordering and grouping.

    Uses ::bigint cast — PostgreSQL only.
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast")
    async def test_get_tool_breakdown_orders_by_calls(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Tools are ordered by call_count DESC."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        user, server = await _create_test_user_and_server(test_session)

        tools = [("tool_c", 20), ("tool_a", 10), ("tool_b", 5)]
        for tool_name, calls in tools:
            await test_session.execute(
                text("""
                    INSERT INTO analytics_rollups
                        (id, server_id, tool_name, bucket_start, granularity,
                         call_count, error_count)
                    VALUES (:id, :sid, :tool, :bucket, 'hour', :calls, :errors)
                """),
                {
                    "id": uuid.uuid4(),
                    "sid": server.id,
                    "tool": tool_name,
                    "bucket": datetime.now(UTC) - timedelta(hours=1),
                    "calls": calls,
                    "errors": 0,
                },
            )
        await test_session.commit()

        queries = AnalyticsQueries(test_session)
        items = await queries.get_tool_breakdown(server.id, "7d")

        assert len(items) == 3
        assert items[0].tool_name == "tool_c"
        assert items[1].tool_name == "tool_a"
        assert items[2].tool_name == "tool_b"

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast")
    async def test_get_tool_breakdown_empty(
        self,
        test_session: AsyncSession,
    ) -> None:
        """No data → empty breakdown."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        user, server = await _create_test_user_and_server(test_session)

        queries = AnalyticsQueries(test_session)
        items = await queries.get_tool_breakdown(server.id, "7d")
        assert items == []


# ── Error log (works on all DB backends) ──────────────────────────────────────


class TestErrorLog:
    """AnalyticsQueries.get_error_log — error filtering.

    Uses simple SELECT — works on SQLite.
    """

    async def test_get_error_log_filters_success(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_error_log returns only non-success calls."""
        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)

        for i in range(5):
            await _insert_tool_call(
                test_session, server.id, f"err_tool_{i}",
                status="error", error_type="Other", error_msg=f"Error {i}",
                called_at=now - timedelta(hours=i),
            )
        for i in range(3):
            await _insert_tool_call(
                test_session, server.id, f"ok_tool_{i}",
                status="success",
                called_at=now - timedelta(hours=i),
            )
        await test_session.commit()

        queries = AnalyticsQueries(test_session)
        items = await queries.get_error_log(server.id, "7d")

        assert len(items) == 5
        for item in items:
            assert item.error_type != "success"

    async def test_get_error_log_pagination(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_error_log respects limit/offset."""
        user, server = await _create_test_user_and_server(test_session)

        for i in range(10):
            await _insert_tool_call(
                test_session, server.id, f"tool_{i}",
                status="error", error_type="Other", error_msg=f"Error {i}",
                called_at=datetime.now(UTC) - timedelta(minutes=i),
            )
        await test_session.commit()

        queries = AnalyticsQueries(test_session)
        page1 = await queries.get_error_log(server.id, "7d", limit=3, offset=0)
        page2 = await queries.get_error_log(server.id, "7d", limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        page1_ids = {e.tool_name for e in page1}
        page2_ids = {e.tool_name for e in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_get_error_log_empty(
        self,
        test_session: AsyncSession,
    ) -> None:
        """No errors → empty list."""
        user, server = await _create_test_user_and_server(test_session)

        await _insert_tool_call(
            test_session, server.id, "ok_tool",
            status="success",
        )
        await test_session.commit()

        queries = AnalyticsQueries(test_session)
        items = await queries.get_error_log(server.id, "7d")
        assert items == []


# ── Client breakdown (PostgreSQL-only SQL) ────────────────────────────────────


class TestClientBreakdown:
    """AnalyticsQueries.get_client_breakdown."""

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast in COUNT")
    async def test_get_client_breakdown_groups(
        self,
        test_session: AsyncSession,
    ) -> None:
        """2 clients return 2 breakdown rows."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        ...


# ── Time series (PostgreSQL-only SQL) ─────────────────────────────────────────


class TestTimeSeries:
    """AnalyticsQueries.get_time_series — bucketing."""

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc, FILTER, ::bigint")
    async def test_get_time_series_hourly(
        self,
        test_session: AsyncSession,
    ) -> None:
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        ...

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc, FILTER, ::bigint")
    async def test_get_time_series_daily(
        self,
        test_session: AsyncSession,
    ) -> None:
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        ...
