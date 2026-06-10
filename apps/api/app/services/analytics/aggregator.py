"""Analytics rollup aggregation service (F6 — Analytics).

Aggregates raw ``tool_calls`` data into ``analytics_rollups`` at hourly and
daily granularity. Designed to run from Celery beat but can be called
on-demand for backfill.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

_UNIQUE_INDEX_NAME = "uq_rollups_server_tool_bucket_gran"


class AnalyticsAggregator:
    """Builds and maintains the ``analytics_rollups`` aggregate table.

    ``aggregate_hour`` and ``aggregate_daily`` ensure the unique index
    exists before running (idempotent ``CREATE UNIQUE INDEX IF NOT EXISTS``).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the aggregator with a DB session.

        Args:
            session: An active SQLAlchemy async session.
        """
        self.session = session

    async def ensure_unique_index(self) -> None:
        """Create the unique index for upsert idempotently.

        The index is on ``(server_id, tool_name, bucket_start, granularity)``
        and enables ``ON CONFLICT`` in the aggregate INSERT statements.
        """
        await self.session.execute(
            text(f"""
                CREATE UNIQUE INDEX IF NOT EXISTS {_UNIQUE_INDEX_NAME}
                ON analytics_rollups (server_id, tool_name, bucket_start, granularity)
            """),
        )
        await self.session.flush()

    async def aggregate_hour(self, hour_bucket: datetime | None = None) -> int:
        """Aggregate one hour of ``tool_calls`` data into ``analytics_rollups``.

        If ``hour_bucket`` is ``None``, the previous full hour is used
        (i.e., if it is currently 14:35, it aggregates 13:00–14:00).

        Args:
            hour_bucket: The start of the hour bucket to aggregate.
                If ``None``, defaults to the previous full hour.

        Returns:
            Number of rollup rows written (updated + inserted).
        """
        await self.ensure_unique_index()

        if hour_bucket is None:
            now = datetime.now(UTC)
            hour_bucket = now.replace(
                minute=0, second=0, microsecond=0,
            ) - timedelta(hours=1)

        start = hour_bucket.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)

        stmt = text("""
            INSERT INTO analytics_rollups
                (id, server_id, tool_name, bucket_start, granularity,
                 call_count, error_count, avg_latency_ms)
            SELECT
                gen_random_uuid(),
                server_id,
                tool_name,
                date_trunc('hour', called_at) AS bucket,
                'hour' AS granularity,
                COUNT(*) AS call_count,
                COUNT(*) FILTER (WHERE status != 'success') AS error_count,
                AVG(latency_ms) AS avg_latency_ms
            FROM tool_calls
            WHERE called_at >= :start AND called_at < :end
            GROUP BY server_id, tool_name, date_trunc('hour', called_at)
            ON CONFLICT (server_id, tool_name, bucket_start, granularity)
            DO UPDATE SET
                call_count = EXCLUDED.call_count,
                error_count = EXCLUDED.error_count,
                avg_latency_ms = EXCLUDED.avg_latency_ms
        """)

        result = await self.session.execute(
            stmt,
            {"start": start, "end": end},
        )
        await self.session.flush()

        # rowcount is the number of inserted-or-updated rows.
        row_count: int = result.rowcount  # type: ignore[attr-defined]

        logger.info(
            "hour_aggregated",
            hour=hour_bucket.isoformat(),
            rows=row_count,
        )
        return row_count

    async def aggregate_daily(self, day_bucket: date | None = None) -> int:
        """Aggregate one day of hourly rollups into daily rows.

        Reads from ``analytics_rollups`` (where ``granularity = 'hour'``)
        and writes/updates rows with ``granularity = 'day'``.

        If ``day_bucket`` is ``None``, yesterday is used.

        Args:
            day_bucket: The date to aggregate. If ``None``, defaults to
                yesterday.

        Returns:
            Number of daily rollup rows written (updated + inserted).
        """
        await self.ensure_unique_index()

        if day_bucket is None:
            day_bucket = (datetime.now(UTC) - timedelta(days=1)).date()

        start = datetime(
            day_bucket.year, day_bucket.month, day_bucket.day,
            tzinfo=UTC,
        )
        end = start + timedelta(days=1)

        stmt = text("""
            INSERT INTO analytics_rollups
                (id, server_id, tool_name, bucket_start, granularity,
                 call_count, error_count, avg_latency_ms)
            SELECT
                gen_random_uuid(),
                server_id,
                tool_name,
                date_trunc('day', bucket_start) AS bucket,
                'day' AS granularity,
                SUM(call_count) AS call_count,
                SUM(error_count) AS error_count,
                AVG(avg_latency_ms) AS avg_latency_ms
            FROM analytics_rollups
            WHERE granularity = 'hour'
              AND bucket_start >= :start AND bucket_start < :end
            GROUP BY server_id, tool_name, date_trunc('day', bucket_start)
            ON CONFLICT (server_id, tool_name, bucket_start, granularity)
            DO UPDATE SET
                call_count = EXCLUDED.call_count,
                error_count = EXCLUDED.error_count,
                avg_latency_ms = EXCLUDED.avg_latency_ms
        """)

        result = await self.session.execute(
            stmt,
            {"start": start, "end": end},
        )
        await self.session.flush()

        row_count: int = result.rowcount  # type: ignore[attr-defined]

        logger.info(
            "daily_aggregated",
            day=day_bucket.isoformat(),
            rows=row_count,
        )
        return row_count

    async def aggregate_range(self, start: datetime, end: datetime) -> int:
        """Aggregate every hour in the given range for backfill.

        Args:
            start: The start of the range (inclusive).
            end: The end of the range (exclusive).

        Returns:
            Total number of rollup rows written across all hours.
        """
        total = 0
        cursor = start.replace(minute=0, second=0, microsecond=0)
        while cursor < end:
            total += await self.aggregate_hour(cursor)
            cursor += timedelta(hours=1)
        return total
