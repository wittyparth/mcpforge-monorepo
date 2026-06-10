"""Partition management for the ``tool_calls`` partitioned table (F6 — Analytics).

Creates daily partitions ahead of time and drops old partitions for retention.
Uses raw SQL and its own database session — intended for Celery beat tasks.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)

_PARTITION_TABLE_PREFIX = "tool_calls_"
_PARTITION_NAME_PATTERN = re.compile(
    rf"^{_PARTITION_TABLE_PREFIX}(\d{{4}}_\d{{2}}_\d{{2}})$",
)

# Max days ahead to create partitions in a single run.
_MAX_DAYS_AHEAD = 365


class PartitionManager:
    """Manages daily partitions for the ``tool_calls`` partitioned table.

    All methods open their own database session since partition operations
    are admin-level and typically run from Celery beat, not from request
    handlers.
    """

    async def ensure_partitions(self, days_ahead: int = 7) -> int:
        """Create daily partitions for today + ``days_ahead`` days.

        Existing partitions are detected via :meth:`list_partitions` and
        skipped. The operation is idempotent.

        Args:
            days_ahead: Number of future days to create partitions for
                (max ``_MAX_DAYS_AHEAD``).

        Returns:
            Number of new partitions created.
        """
        if days_ahead < 0:
            raise ValueError("days_ahead must be non-negative")
        if days_ahead > _MAX_DAYS_AHEAD:
            raise ValueError(f"days_ahead exceeds maximum of {_MAX_DAYS_AHEAD}")

        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        created = 0

        async with AsyncSessionLocal() as session:
            existing = await self._fetch_partition_names(session)
            existing_names = {p["name"] for p in existing}

            for offset in range(days_ahead + 1):
                day_start = today + timedelta(days=offset)
                partition_name = (
                    f"{_PARTITION_TABLE_PREFIX}{day_start.strftime('%Y_%m_%d')}"
                )

                if partition_name in existing_names:
                    continue

                day_end = day_start + timedelta(days=1)
                stmt = text(f"""
                    CREATE TABLE {partition_name} PARTITION OF tool_calls
                    FOR VALUES FROM (:start) TO (:end)
                """)
                await session.execute(
                    stmt,
                    {
                        "start": day_start.isoformat(),
                        "end": day_end.isoformat(),
                    },
                )
                created += 1

            await session.commit()

        logger.info(
            "partitions_created",
            count=created,
            days_ahead=days_ahead,
        )
        return created

    async def cleanup_old_partitions(self, retention_days: int = 7) -> int:
        """Drop partitions older than ``retention_days``.

        The current day's partition is never dropped, even if it is the
        only partition within the retention window.

        Args:
            retention_days: Age in days beyond which partitions are dropped.

        Returns:
            Number of partitions dropped.
        """
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = today_start - timedelta(days=retention_days)
        dropped = 0

        async with AsyncSessionLocal() as session:
            partitions = await self._fetch_partition_names(session)

            for p in partitions:
                range_start = p["range_start"]
                if range_start is None:
                    continue
                # Never drop the current day's partition.
                if range_start >= today_start:
                    continue
                if range_start < cutoff:
                    stmt = text(f"DROP TABLE IF EXISTS {p['name']}")
                    await session.execute(stmt)
                    dropped += 1

            await session.commit()

        logger.info(
            "old_partitions_dropped",
            count=dropped,
            retention_days=retention_days,
        )
        return dropped

    async def list_partitions(self) -> list[dict[str, Any]]:
        """Return metadata for all existing ``tool_calls`` partitions.

        Returns:
            A list of dicts with keys ``name`` (str), ``range_start``
            (datetime or None), and ``range_end`` (datetime or None).
        """
        async with AsyncSessionLocal() as session:
            return await self._fetch_partition_names(session)

    @staticmethod
    async def _fetch_partition_names(
        session: Any,  # noqa: ANN401 — AsyncSession duck-typed for import safety
    ) -> list[dict[str, Any]]:
        """Query ``pg_inherits`` for all ``tool_calls`` partitions.

        Args:
            session: An active DB session (``AsyncSession``).

        Returns:
            List of partition dicts with ``name``, ``range_start``,
            ``range_end``.
        """
        result = await session.execute(
            text("""
                SELECT
                    inhrelid::regclass::text AS partition_name
                FROM pg_inherits
                WHERE inhparent = 'tool_calls'::regclass
                ORDER BY 1
            """),
        )
        rows = result.fetchall()

        partitions: list[dict[str, Any]] = []
        for row in rows:
            name: str = row[0]
            entry: dict[str, Any] = {
                "name": name,
                "range_start": None,
                "range_end": None,
            }
            match = _PARTITION_NAME_PATTERN.match(name)
            if match:
                date_str = match.group(1).replace("_", "-")
                try:
                    day_start = datetime.fromisoformat(date_str).replace(
                        tzinfo=UTC,
                    )
                    entry["range_start"] = day_start
                    entry["range_end"] = day_start + timedelta(days=1)
                except (ValueError, TypeError):
                    pass
            partitions.append(entry)

        return partitions
