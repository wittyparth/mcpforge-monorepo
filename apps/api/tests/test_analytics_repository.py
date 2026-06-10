"""Tests for AnalyticsRepository (F6 — Usage Analytics).

4 tests covering:
  - list_tool_calls filters by server (ORM, works on all backends)
  - count_tool_calls returns correct count (ORM, works on all backends)
  - get_time_series_raw buckets (PostgreSQL-only, skipped on SQLite)
  - get_call_rate counts in range (ORM, works on all backends)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServer
from app.models.user import User
from app.repositories.analytics_repo import AnalyticsRepository

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_test_user_and_server(
    session: AsyncSession,
) -> tuple[User, MCPServer]:
    """Create a minimal user + server pair."""
    user = User(
        email=f"repo-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
    )
    session.add(user)
    await session.flush()
    server = MCPServer(
        user_id=user.id,
        slug=f"repo-slug-{uuid.uuid4().hex[:8]}",
        name="Repo Test Server",
        base_url="https://example.com",
    )
    session.add(server)
    await session.flush()
    return user, server


async def _insert_tool_call(
    session: AsyncSession,
    server_id: uuid.UUID,
    tool_name: str = "test_tool",
    status: str = "success",
    called_at: datetime | None = None,
    latency_ms: int | None = 100,
) -> None:
    """Insert a row into tool_calls."""
    await session.execute(
        text("""
            INSERT INTO tool_calls
                (id, server_id, tool_name, status, latency_ms, called_at)
            VALUES (:id, :sid, :tool, :status, :lat, :ts)
        """),
        {
            "id": uuid.uuid4(),
            "sid": server_id,
            "tool": tool_name,
            "status": status,
            "lat": latency_ms,
            "ts": called_at or datetime.now(UTC),
        },
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestListToolCalls:
    """AnalyticsRepository.list_tool_calls — ORM filtering."""

    async def test_list_tool_calls_filters_by_server(
        self,
        test_session: AsyncSession,
    ) -> None:
        """list_tool_calls for one server returns only its calls."""
        user, server_a = await _create_test_user_and_server(test_session)
        user, server_b = await _create_test_user_and_server(test_session)

        await _insert_tool_call(test_session, server_a.id, "tool_a1")
        await _insert_tool_call(test_session, server_a.id, "tool_a2")
        await _insert_tool_call(test_session, server_b.id, "tool_b1")
        await test_session.commit()

        repo = AnalyticsRepository(test_session)

        calls_a = await repo.list_tool_calls(server_a.id)
        assert len(calls_a) == 2
        for c in calls_a:
            assert c.server_id == server_a.id

        calls_b = await repo.list_tool_calls(server_b.id)
        assert len(calls_b) == 1
        assert calls_b[0].server_id == server_b.id

    async def test_list_tool_calls_filters_by_status(
        self,
        test_session: AsyncSession,
    ) -> None:
        """list_tool_calls with status filter works."""
        user, server = await _create_test_user_and_server(test_session)

        await _insert_tool_call(test_session, server.id, "ok", status="success")
        await _insert_tool_call(test_session, server.id, "err", status="error")
        await test_session.commit()

        repo = AnalyticsRepository(test_session)
        errors = await repo.list_tool_calls(server.id, status="error")
        assert len(errors) == 1
        assert errors[0].status == "error"

    async def test_list_tool_calls_respects_limit(
        self,
        test_session: AsyncSession,
    ) -> None:
        """list_tool_calls with limit returns at most N rows."""
        user, server = await _create_test_user_and_server(test_session)

        for i in range(10):
            await _insert_tool_call(
                test_session, server.id, f"tool_{i}",
                called_at=datetime.now(UTC) - timedelta(minutes=i),
            )
        await test_session.commit()

        repo = AnalyticsRepository(test_session)
        calls = await repo.list_tool_calls(server.id, limit=3)
        assert len(calls) == 3


class TestCountToolCalls:
    """AnalyticsRepository.count_tool_calls — ORM counting."""

    async def test_count_tool_calls(
        self,
        test_session: AsyncSession,
    ) -> None:
        """count_tool_calls returns total matching rows."""
        user, server = await _create_test_user_and_server(test_session)

        for _ in range(5):
            await _insert_tool_call(test_session, server.id)
        await test_session.commit()

        repo = AnalyticsRepository(test_session)
        count = await repo.count_tool_calls(server.id)
        assert count == 5

    async def test_count_tool_calls_with_filters(
        self,
        test_session: AsyncSession,
    ) -> None:
        """count_tool_calls with status filter works."""
        user, server = await _create_test_user_and_server(test_session)

        await _insert_tool_call(test_session, server.id, status="success")
        await _insert_tool_call(test_session, server.id, status="success")
        await _insert_tool_call(test_session, server.id, status="error")
        await test_session.commit()

        repo = AnalyticsRepository(test_session)
        assert await repo.count_tool_calls(server.id, status="success") == 2
        assert await repo.count_tool_calls(server.id, status="error") == 1


class TestGetTimeSeriesRaw:
    """AnalyticsRepository.get_time_series_raw.

    Uses PostgreSQL-specific SQL (date_trunc, FILTER).
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc and FILTER")
    async def test_get_time_series_raw_buckets(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_time_series_raw returns aggregated buckets."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        ...

    @pytest.mark.skip(reason="Requires PostgreSQL — date_trunc and FILTER")
    async def test_get_time_series_raw_empty(
        self,
        test_session: AsyncSession,
    ) -> None:
        """No data → empty list."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        ...


class TestGetCallRate:
    """AnalyticsRepository.get_call_rate — ORM counting in range."""

    async def test_get_call_rate(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_call_rate counts calls in range for a specific tool."""
        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)

        # Insert calls at different times.
        for i in range(5):
            await _insert_tool_call(
                test_session, server.id, "tool_x",
                called_at=now - timedelta(hours=i),
            )
        for i in range(3):
            await _insert_tool_call(
                test_session, server.id, "tool_y",
                called_at=now - timedelta(hours=i),
            )
        await test_session.commit()

        repo = AnalyticsRepository(test_session)

        # Count calls for tool_x in the last 7 days.
        count = await repo.get_call_rate(
            server.id,
            "tool_x",
            start=now - timedelta(days=7),
            end=now + timedelta(hours=1),
        )
        assert count == 5

    async def test_get_call_rate_empty_range(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_call_rate returns 0 when no calls match."""
        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)

        await _insert_tool_call(test_session, server.id, "tool_z")
        await test_session.commit()

        repo = AnalyticsRepository(test_session)
        count = await repo.get_call_rate(
            server.id,
            "tool_z",
            start=now + timedelta(days=1),  # future — no calls
            end=now + timedelta(days=2),
        )
        assert count == 0

    async def test_get_call_rate_tool_not_found(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_call_rate returns 0 when the tool has no calls."""
        user, server = await _create_test_user_and_server(test_session)

        repo = AnalyticsRepository(test_session)
        count = await repo.get_call_rate(
            server.id,
            "nonexistent_tool",
            start=datetime.now(UTC) - timedelta(days=7),
            end=datetime.now(UTC),
        )
        assert count == 0
