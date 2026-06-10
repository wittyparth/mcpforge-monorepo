"""Analytics data access layer (F6 — Usage Analytics).

Wraps DB access for the ``tool_calls`` partitioned table and the
``analytics_rollups`` aggregate table.  Methods returning dicts are
designed to feed dashboard chart endpoints directly — no service
layer transformation required.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call import AnalyticsRollup, ToolCall
from app.models.tool_edit_history import ToolEditHistory


class AnalyticsRepository:
    """Read-only queries for usage analytics.

    All methods are async, accept an ``AsyncSession`` via the constructor,
    and return plain ORM rows or serialisable dicts.  Timestamps are
    expected to be timezone-aware (callers pass ``datetime.now(UTC)``).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Tool-call listing / counting
    # ------------------------------------------------------------------

    async def list_tool_calls(
        self,
        server_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        status: str | None = None,
        tool_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCall]:
        """List ``tool_calls`` for a server with optional filters."""
        stmt = select(ToolCall).where(ToolCall.server_id == server_id)
        if since is not None:
            stmt = stmt.where(ToolCall.called_at >= since)
        if until is not None:
            stmt = stmt.where(ToolCall.called_at < until)
        if status is not None:
            stmt = stmt.where(ToolCall.status == status)
        if tool_name is not None:
            stmt = stmt.where(ToolCall.tool_name == tool_name)
        stmt = stmt.order_by(ToolCall.called_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_tool_calls(
        self,
        server_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        status: str | None = None,
        tool_name: str | None = None,
    ) -> int:
        """Count ``tool_calls`` for a server with optional filters."""
        stmt = select(func.count(ToolCall.id)).where(
            ToolCall.server_id == server_id
        )
        if since is not None:
            stmt = stmt.where(ToolCall.called_at >= since)
        if until is not None:
            stmt = stmt.where(ToolCall.called_at < until)
        if status is not None:
            stmt = stmt.where(ToolCall.status == status)
        if tool_name is not None:
            stmt = stmt.where(ToolCall.tool_name == tool_name)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Error queries
    # ------------------------------------------------------------------

    async def list_errors(
        self,
        server_id: UUID,
        *,
        since: datetime,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCall]:
        """List ``tool_calls`` that are not ``'success'`` (errors), newest first."""
        stmt = (
            select(ToolCall)
            .where(
                ToolCall.server_id == server_id,
                ToolCall.called_at >= since,
                ToolCall.status != "success",
            )
            .order_by(ToolCall.called_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_errors(self, server_id: UUID, *, since: datetime) -> int:
        """Count non-``'success'`` ``tool_calls``."""
        stmt = select(func.count(ToolCall.id)).where(
            ToolCall.server_id == server_id,
            ToolCall.called_at >= since,
            ToolCall.status != "success",
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Client queries
    # ------------------------------------------------------------------

    async def list_clients(
        self,
        server_id: UUID,
        *,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """List distinct clients with their call counts and last seen.

        ``NULL`` *client_name* is mapped to ``'Unknown'``.
        """
        result = await self.session.execute(
            select(
                ToolCall.client_name,
                func.count(ToolCall.id).label("call_count"),
                func.max(ToolCall.called_at).label("last_seen"),
            )
            .where(ToolCall.server_id == server_id, ToolCall.called_at >= since)
            .group_by(ToolCall.client_name)
            .order_by(func.count(ToolCall.id).desc())
        )
        rows: list[dict[str, Any]] = []
        for row in result:
            rows.append(
                {
                    "client_name": (
                        row.client_name
                        if row.client_name is not None
                        else "Unknown"
                    ),
                    "call_count": row.call_count,
                    "last_seen": row.last_seen,
                }
            )
        return rows

    async def get_unique_clients(
        self,
        server_id: UUID,
        *,
        since: datetime,
    ) -> int:
        """Count distinct non-null ``client_name`` values in ``tool_calls``."""
        result = await self.session.execute(
            select(func.count(func.distinct(ToolCall.client_name)))
            .where(
                ToolCall.server_id == server_id,
                ToolCall.called_at >= since,
                ToolCall.client_name.isnot(None),
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Time-series
    # ------------------------------------------------------------------

    async def get_time_series_raw(
        self,
        server_id: UUID,
        *,
        since: datetime,
        bucket: str = "hour",
    ) -> list[dict[str, Any]]:
        """Compute time-series buckets directly from ``tool_calls``.

        Uses ``date_trunc`` at the partition level so PostgreSQL can
        prune partitions when the range is narrow enough.
        """
        query = text("""
            SELECT
                date_trunc(:bucket, called_at) AS bucket_start,
                COUNT(*) AS call_count,
                COUNT(*) FILTER (WHERE status != 'success') AS error_count,
                AVG(latency_ms) AS avg_latency_ms
            FROM tool_calls
            WHERE server_id = :server_id AND called_at >= :since
            GROUP BY bucket_start
            ORDER BY bucket_start ASC
        """)
        result = await self.session.execute(
            query,
            {
                "bucket": bucket,
                "server_id": server_id,
                "since": since,
            },
        )
        return [
            {
                "bucket_start": r.bucket_start,
                "call_count": r.call_count,
                "error_count": r.error_count,
                "avg_latency_ms": r.avg_latency_ms,
            }
            for r in result
        ]

    async def get_time_series_from_rollup(
        self,
        server_id: UUID,
        *,
        since: datetime,
        granularity: str,
    ) -> list[dict[str, Any]]:
        """Read time-series from ``analytics_rollups``.

        Returns rows ordered ASC by ``bucket_start``.  The ``granularity``
        parameter must match the rollup's stored value (``'hour'`` or
        ``'day'``).
        """
        result = await self.session.execute(
            select(AnalyticsRollup)
            .where(
                AnalyticsRollup.server_id == server_id,
                AnalyticsRollup.granularity == granularity,
                AnalyticsRollup.bucket_start >= since,
            )
            .order_by(AnalyticsRollup.bucket_start.asc())
        )
        rows = result.scalars().all()
        return [
            {
                "bucket_start": r.bucket_start,
                "call_count": r.call_count,
                "error_count": r.error_count,
                "avg_latency_ms": r.avg_latency_ms,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Dashboard overview
    # ------------------------------------------------------------------

    async def get_overview_from_rollup(
        self,
        server_id: UUID,
        *,
        since: datetime,
    ) -> dict[str, Any]:
        """Aggregate overview from hourly ``analytics_rollups``."""
        result = await self.session.execute(
            select(
                func.sum(AnalyticsRollup.call_count).label("total_calls"),
                func.sum(AnalyticsRollup.error_count).label("total_errors"),
                func.avg(AnalyticsRollup.avg_latency_ms).label("avg_latency_ms"),
            )
            .where(
                AnalyticsRollup.server_id == server_id,
                AnalyticsRollup.granularity == "hour",
                AnalyticsRollup.bucket_start >= since,
            )
        )
        row = result.one()
        return {
            "total_calls": row.total_calls or 0,
            "total_errors": row.total_errors or 0,
            "avg_latency_ms": row.avg_latency_ms,
        }

    async def get_tool_breakdown_from_rollup(
        self,
        server_id: UUID,
        *,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Per-tool breakdown from hourly ``analytics_rollups``."""
        result = await self.session.execute(
            select(
                AnalyticsRollup.tool_name,
                func.sum(AnalyticsRollup.call_count).label("call_count"),
                func.sum(AnalyticsRollup.error_count).label("error_count"),
                func.avg(AnalyticsRollup.avg_latency_ms).label("avg_latency_ms"),
            )
            .where(
                AnalyticsRollup.server_id == server_id,
                AnalyticsRollup.granularity == "hour",
                AnalyticsRollup.bucket_start >= since,
                AnalyticsRollup.tool_name.isnot(None),
            )
            .group_by(AnalyticsRollup.tool_name)
            .order_by(func.sum(AnalyticsRollup.call_count).desc())
        )
        return [
            {
                "tool_name": r.tool_name,
                "call_count": r.call_count,
                "error_count": r.error_count,
                "avg_latency_ms": r.avg_latency_ms,
            }
            for r in result
        ]

    # ------------------------------------------------------------------
    # Description performance tracking
    # ------------------------------------------------------------------

    async def get_call_rate(
        self,
        server_id: UUID,
        tool_name: str,
        *,
        start: datetime,
        end: datetime,
    ) -> int:
        """Count ``tool_calls`` in a ``[start, end)`` range for a tool."""
        result = await self.session.execute(
            select(func.count(ToolCall.id)).where(
                ToolCall.server_id == server_id,
                ToolCall.tool_name == tool_name,
                ToolCall.called_at >= start,
                ToolCall.called_at < end,
            )
        )
        return result.scalar() or 0

    async def get_latest_edit(
        self,
        server_id: UUID,
        tool_name: str,
    ) -> dict[str, Any] | None:
        """Get the most recent ``ToolEditHistory`` row for a tool.

        Returns ``None`` if no edits exist.
        """
        result = await self.session.execute(
            select(ToolEditHistory)
            .where(
                ToolEditHistory.server_id == server_id,
                ToolEditHistory.tool_name == tool_name,
            )
            .order_by(ToolEditHistory.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "changed_at": row.created_at,
            "previous_value": row.previous_description or "",
            "new_value": row.new_description,
            "edit_source": row.edit_source,
        }
