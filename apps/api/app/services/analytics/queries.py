"""Analytics query service (F6 — Analytics).

Read-side access patterns for the analytics dashboard. All methods return
Pydantic response schemas defined in ``app.schemas.analytics``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.schemas.analytics import (
    AnalyticsOverview,
    ClientBreakdownItem,
    ErrorLogItem,
    TimeSeriesPoint,
    ToolBreakdownItem,
)

logger = get_logger(__name__)

# Supported time range presets.
RANGE_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}


class AnalyticsQueries:
    """Read-side queries for the analytics dashboard.

    All time-range queries use the ``RANGE_DAYS`` lookup to convert a
    short range key (e.g. ``'7d'``) into a date offset.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the query service with a DB session.

        Args:
            session: An active SQLAlchemy async session.
        """
        self.session = session

    async def get_overview(
        self,
        server_id: UUID,
        range_str: str,
    ) -> AnalyticsOverview:
        """Return top-line analytics numbers for a server.

        Args:
            server_id: The target server UUID.
            range_str: Time range key (``'7d'``, ``'30d'``, or ``'90d'``).

        Returns:
            An ``AnalyticsOverview`` with aggregated metrics.

        Raises:
            ValidationError: If ``range_str`` is not a supported key.
        """
        days = RANGE_DAYS.get(range_str)
        if days is None:
            raise ValidationError(
                f"Unsupported range '{range_str}'. Must be one of: {', '.join(RANGE_DAYS)}",
            )

        start = datetime.now(UTC) - timedelta(days=days)

        # Aggregate from rollups.
        rollup_result = await self.session.execute(
            text("""
                SELECT
                    COALESCE(SUM(call_count), 0)::bigint AS total_calls,
                    COALESCE(SUM(error_count), 0)::bigint AS total_errors,
                    AVG(avg_latency_ms) AS avg_latency
                FROM analytics_rollups
                WHERE server_id = :server_id
                  AND granularity = 'hour'
                  AND bucket_start >= :start
            """),
            {"server_id": server_id, "start": start},
        )
        rollup_row = rollup_result.one()

        total_calls: int = rollup_row.total_calls
        total_errors: int = rollup_row.total_errors
        avg_latency: float | None = rollup_row.avg_latency

        # Unique clients from raw tool_calls.
        client_result = await self.session.execute(
            text("""
                SELECT COUNT(DISTINCT client_name) AS unique_clients
                FROM tool_calls
                WHERE server_id = :server_id
                  AND called_at >= :start
            """),
            {"server_id": server_id, "start": start},
        )
        client_row = client_result.one()
        unique_clients: int = client_row.unique_clients

        error_rate = (
            total_errors / total_calls if total_calls > 0 else 0.0
        )

        # NOTE: p95 is set to avg_latency; a dedicated percentile
        # computation will be added in a future migration.
        p95 = avg_latency if avg_latency is not None else 0.0

        overview = AnalyticsOverview(
            server_id=server_id,
            range=range_str,
            total_calls=total_calls,
            total_errors=total_errors,
            error_rate=min(error_rate, 1.0),
            unique_clients=unique_clients,
            avg_latency_ms=avg_latency if avg_latency is not None else 0.0,
            p95_latency_ms=p95,
        )

        logger.info(
            "analytics_overview_fetched",
            server_id=str(server_id),
            range=range_str,
        )
        return overview

    async def get_tool_breakdown(
        self,
        server_id: UUID,
        range_str: str,
    ) -> list[ToolBreakdownItem]:
        """Return per-tool call breakdown for a server.

        Args:
            server_id: The target server UUID.
            range_str: Time range key.

        Returns:
            List of ``ToolBreakdownItem`` ordered by call count descending.
        """
        days = RANGE_DAYS.get(range_str)
        if days is None:
            raise ValidationError(
                f"Unsupported range '{range_str}'. Must be one of: {', '.join(RANGE_DAYS)}",
            )

        start = datetime.now(UTC) - timedelta(days=days)

        # Grand total for selection-rate denominator.
        total_result = await self.session.execute(
            text("""
                SELECT COALESCE(SUM(call_count), 0)::bigint AS total
                FROM analytics_rollups
                WHERE server_id = :server_id
                  AND granularity = 'hour'
                  AND bucket_start >= :start
            """),
            {"server_id": server_id, "start": start},
        )
        total_calls: int = total_result.scalar_one()

        rows = await self.session.execute(
            text("""
                SELECT
                    tool_name,
                    COALESCE(SUM(call_count), 0)::bigint AS call_count,
                    COALESCE(SUM(error_count), 0)::bigint AS error_count,
                    AVG(avg_latency_ms) AS avg_latency_ms
                FROM analytics_rollups
                WHERE server_id = :server_id
                  AND granularity = 'hour'
                  AND bucket_start >= :start
                  AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY call_count DESC
            """),
            {"server_id": server_id, "start": start},
        )
        items: list[ToolBreakdownItem] = []
        for row in rows:
            selection_rate = (
                row.call_count / total_calls if total_calls > 0 else 0.0
            )
            items.append(
                ToolBreakdownItem(
                    tool_name=row.tool_name,
                    call_count=row.call_count,
                    error_count=row.error_count,
                    avg_latency_ms=row.avg_latency_ms if row.avg_latency_ms is not None else 0.0,
                    selection_rate=min(selection_rate, 1.0),
                ),
            )

        return items

    async def get_error_log(
        self,
        server_id: UUID,
        range_str: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ErrorLogItem]:
        """Return error log entries for a server.

        Reads directly from ``tool_calls`` (not rollups) to capture full
        error details.

        Args:
            server_id: The target server UUID.
            range_str: Time range key.
            limit: Maximum rows to return.
            offset: Number of rows to skip.

        Returns:
            List of ``ErrorLogItem`` ordered by time descending.
        """
        days = RANGE_DAYS.get(range_str)
        if days is None:
            raise ValidationError(
                f"Unsupported range '{range_str}'. Must be one of: {', '.join(RANGE_DAYS)}",
            )

        start = datetime.now(UTC) - timedelta(days=days)

        rows = await self.session.execute(
            text("""
                SELECT
                    called_at,
                    tool_name,
                    COALESCE(error_type, 'Other') AS error_type,
                    COALESCE(error_msg, '') AS error_msg,
                    client_name
                FROM tool_calls
                WHERE server_id = :server_id
                  AND status != 'success'
                  AND called_at >= :start
                ORDER BY called_at DESC
                LIMIT :limit
                OFFSET :offset
            """),
            {
                "server_id": server_id,
                "start": start,
                "limit": limit,
                "offset": offset,
            },
        )
        return [
            ErrorLogItem(
                called_at=row.called_at,
                tool_name=row.tool_name,
                error_type=row.error_type,
                error_msg=row.error_msg,
                client_name=row.client_name,
            )
            for row in rows
        ]

    async def get_client_breakdown(
        self,
        server_id: UUID,
        range_str: str,
    ) -> list[ClientBreakdownItem]:
        """Return per-client call breakdown for a server.

        Args:
            server_id: The target server UUID.
            range_str: Time range key.

        Returns:
            List of ``ClientBreakdownItem`` ordered by call count descending.
        """
        days = RANGE_DAYS.get(range_str)
        if days is None:
            raise ValidationError(
                f"Unsupported range '{range_str}'. Must be one of: {', '.join(RANGE_DAYS)}",
            )

        start = datetime.now(UTC) - timedelta(days=days)

        rows = await self.session.execute(
            text("""
                SELECT
                    COALESCE(client_name, 'Unknown') AS client_name,
                    COUNT(*)::bigint AS call_count,
                    MAX(called_at) AS last_seen
                FROM tool_calls
                WHERE server_id = :server_id
                  AND called_at >= :start
                GROUP BY client_name
                ORDER BY call_count DESC
            """),
            {"server_id": server_id, "start": start},
        )
        return [
            ClientBreakdownItem(
                client_name=row.client_name,
                call_count=row.call_count,
                last_seen=row.last_seen,
            )
            for row in rows
        ]

    async def get_time_series(
        self,
        server_id: UUID,
        range_str: str,
        granularity: str = "hour",
    ) -> list[TimeSeriesPoint]:
        """Return time-series data for charting.

        When ``granularity='hour'`` and the range is recent (<24 h), raw
        ``tool_calls`` are queried for accuracy. Otherwise, rollups are
        used.

        Args:
            server_id: The target server UUID.
            range_str: Time range key.
            granularity: ``'hour'`` or ``'day'``.

        Returns:
            List of ``TimeSeriesPoint`` ordered by bucket ascending.
        """
        days = RANGE_DAYS.get(range_str)
        if days is None:
            raise ValidationError(
                f"Unsupported range '{range_str}'. Must be one of: {', '.join(RANGE_DAYS)}",
            )
        if granularity not in ("hour", "day"):
            raise ValidationError(
                f"Unsupported granularity '{granularity}'. Must be 'hour' or 'day'.",
            )

        start = datetime.now(UTC) - timedelta(days=days)

        if granularity == "hour":
            # Read raw tool_calls for fine-grained accuracy.
            rows = await self.session.execute(
                text("""
                    SELECT
                        date_trunc('hour', called_at) AS bucket_start,
                        COUNT(*)::bigint AS call_count,
                        COUNT(*) FILTER (WHERE status != 'success')::bigint AS error_count,
                        AVG(latency_ms) AS avg_latency_ms
                    FROM tool_calls
                    WHERE server_id = :server_id
                      AND called_at >= :start
                    GROUP BY date_trunc('hour', called_at)
                    ORDER BY bucket_start ASC
                """),
                {"server_id": server_id, "start": start},
            )
        else:
            # Read from daily rollups.
            rows = await self.session.execute(
                text("""
                    SELECT
                        bucket_start,
                        COALESCE(call_count, 0)::bigint AS call_count,
                        COALESCE(error_count, 0)::bigint AS error_count,
                        avg_latency_ms
                    FROM analytics_rollups
                    WHERE server_id = :server_id
                      AND granularity = 'day'
                      AND bucket_start >= :start
                    ORDER BY bucket_start ASC
                """),
                {"server_id": server_id, "start": start},
            )

        return [
            TimeSeriesPoint(
                bucket_start=row.bucket_start,
                call_count=row.call_count,
                error_count=row.error_count,
                avg_latency_ms=row.avg_latency_ms,
            )
            for row in rows
        ]
