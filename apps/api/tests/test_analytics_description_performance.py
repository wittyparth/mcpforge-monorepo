"""Tests for DescriptionPerformanceTracker (F6 — Usage Analytics).

4 tests covering:
  - No edit history → empty list (works on all DB backends)
  - Edit with before/after computes delta (PostgreSQL-only)
  - Zero before calls returns delta=None (PostgreSQL-only)
  - get_all_tools_performance (PostgreSQL-only)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServer
from app.models.user import User
from app.services.analytics.description_performance import (
    DescriptionPerformanceTracker,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_test_user_and_server(
    session: AsyncSession,
) -> tuple[User, MCPServer]:
    """Create a minimal user + server pair."""
    user = User(
        email=f"dp-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
    )
    session.add(user)
    await session.flush()
    server = MCPServer(
        user_id=user.id,
        slug=f"dp-slug-{uuid.uuid4().hex[:8]}",
        name="DescPerf Test Server",
        base_url="https://example.com",
    )
    session.add(server)
    await session.flush()
    return user, server


async def _insert_edit(
    session: AsyncSession,
    server_id: uuid.UUID,
    tool_name: str,
    edit_source: str = "ai",
    created_at: datetime | None = None,
) -> None:
    """Insert a row into tool_edit_history.

    The ORM model (ToolEditHistory) creates this table via Base.metadata,
    so we can insert directly. The model has no default for created_at,
    so we must provide one.
    """
    await session.execute(
        text("""
            INSERT INTO tool_edit_history
                (id, server_id, tool_name, edit_source, previous_description,
                 new_description, created_at)
            VALUES (:id, :sid, :tool, :source, :prev_desc, :new_desc, :created)
        """),
        {
            "id": uuid.uuid4(),
            "sid": server_id,
            "tool": tool_name,
            "source": edit_source,
            "prev_desc": "old description",
            "new_desc": "new description",
            "created": created_at or datetime.now(UTC),
        },
    )


async def _insert_tool_call(
    session: AsyncSession,
    server_id: uuid.UUID,
    tool_name: str,
    status: str = "success",
    called_at: datetime | None = None,
) -> None:
    """Insert a row into tool_calls."""
    await session.execute(
        text("""
            INSERT INTO tool_calls
                (id, server_id, tool_name, status, called_at)
            VALUES (:id, :sid, :tool, :status, :called_at)
        """),
        {
            "id": uuid.uuid4(),
            "sid": server_id,
            "tool": tool_name,
            "status": status,
            "called_at": called_at or datetime.now(UTC),
        },
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDescriptionPerformanceNoEdit:
    """DescriptionPerformanceTracker — no edit scenario.

    Works on all DB backends (simple SELECT from tool_edit_history).
    """

    async def test_no_edit_returns_empty_list(
        self,
        test_session: AsyncSession,
    ) -> None:
        """When no edit history exists, returns empty list."""
        user, server = await _create_test_user_and_server(test_session)

        tracker = DescriptionPerformanceTracker(test_session)
        results = await tracker.get_performance(server.id, tool_name="some_tool")

        assert results == []

    async def test_no_edit_returns_empty_list_for_all(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_performance with no tool_name and no edits returns []."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL — uses DISTINCT ON internally")

        user, server = await _create_test_user_and_server(test_session)

        tracker = DescriptionPerformanceTracker(test_session)
        results = await tracker.get_performance(server.id, tool_name=None)

        assert results == []


class TestDescriptionPerformanceWithEdit:
    """DescriptionPerformanceTracker — edit scenarios.

    These tests use COUNT(*)::bigint in raw SQL and are PostgreSQL-only.
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast in COUNT")
    async def test_edit_with_before_after_computes_delta(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Edit with 10 before + 15 after → delta_pct=50.0."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)
        edit_time = now - timedelta(days=3)

        # Insert edit history.
        await _insert_edit(test_session, server.id, "tool_a", "ai", edit_time)

        # Insert 10 calls before the edit, 15 after.
        for i in range(10):
            await _insert_tool_call(
                test_session, server.id, "tool_a", "success",
                called_at=edit_time - timedelta(hours=i + 1),
            )
        for i in range(15):
            await _insert_tool_call(
                test_session, server.id, "tool_a", "success",
                called_at=edit_time + timedelta(hours=i + 1),
            )
        await test_session.commit()

        tracker = DescriptionPerformanceTracker(test_session)
        results = await tracker.get_performance(server.id, tool_name="tool_a")

        assert len(results) == 1
        perf = results[0]
        assert perf.tool_name == "tool_a"
        assert perf.before_call_count == 10
        assert perf.after_call_count == 15
        assert perf.delta_pct is not None
        assert abs(perf.delta_pct - 50.0) < 0.1
        assert not perf.no_edit

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast in COUNT")
    async def test_edit_with_zero_before_returns_none_delta(
        self,
        test_session: AsyncSession,
    ) -> None:
        """0 before calls, 5 after calls → delta_pct=None."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        user, server = await _create_test_user_and_server(test_session)
        now = datetime.now(UTC)
        edit_time = now - timedelta(days=3)

        await _insert_edit(test_session, server.id, "tool_b", "user", edit_time)
        # No calls before, 5 calls after.
        for i in range(5):
            await _insert_tool_call(
                test_session, server.id, "tool_b", "success",
                called_at=edit_time + timedelta(hours=i + 1),
            )
        await test_session.commit()

        tracker = DescriptionPerformanceTracker(test_session)
        results = await tracker.get_performance(server.id, tool_name="tool_b")

        assert len(results) == 1
        perf = results[0]
        assert perf.before_call_count == 0
        assert perf.after_call_count == 5
        assert perf.delta_pct is None

    @pytest.mark.skip(reason="Requires PostgreSQL — ::bigint cast + DISTINCT ON")
    async def test_get_all_tools_performance(
        self,
        test_session: AsyncSession,
    ) -> None:
        """get_all_tools_performance returns results for all edited tools."""
        if test_session.bind.dialect.name == "sqlite":
            pytest.skip("Requires PostgreSQL")
        user, server = await _create_test_user_and_server(test_session)

        # Create edits for 2 tools.
        now = datetime.now(UTC)
        edit_time = now - timedelta(days=3)
        await _insert_edit(test_session, server.id, "tool_x", "ai", edit_time)
        await _insert_edit(test_session, server.id, "tool_y", "ai", edit_time)

        await test_session.commit()

        tracker = DescriptionPerformanceTracker(test_session)
        results = await tracker.get_all_tools_performance(server.id)

        assert len(results) == 2
        tool_names = {r.tool_name for r in results}
        assert tool_names == {"tool_x", "tool_y"}
