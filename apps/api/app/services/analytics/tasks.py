"""Celery tasks for F6 (Usage Analytics).

Uses a module-level event loop instead of asyncio.run() so the
SQLAlchemy async engine's connection pool is always pinned to the same
loop -- avoiding Future attached to a different loop errors.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from celery import Task

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.analytics.aggregator import AnalyticsAggregator
from app.services.analytics.partition_manager import PartitionManager
from app.services.analytics.recorder import AnalyticsRecorder

logger = get_logger(__name__)

# Module-level event loop -- reused across all task invocations so the
# SQLAlchemy async engine's pool stays pinned to a single loop.
_loop = asyncio.new_event_loop()


# ── record_tool_call ────────────────────────────────────────────────


async def _record_tool_call_async(
    server_id: str,
    tool_name: str,
    status: str,
    latency_ms: int | None,
    response_size_bytes: int | None,
    error_type: str | None,
    error_msg: str | None,
    client_name: str | None,
) -> dict[str, Any]:
    """Core async record-tool-call logic.

    Opens a session, delegates to AnalyticsRecorder (which handles
    its own commit/rollback internally), and returns a confirmation dict.
    """
    async with AsyncSessionLocal() as session:
        recorder = AnalyticsRecorder(session)
        await recorder.record_tool_call(
            server_id=UUID(server_id),
            tool_name=tool_name,
            status=status,
            latency_ms=latency_ms,
            response_size_bytes=response_size_bytes,
            error_type=error_type,
            error_msg=error_msg,
            client_name=client_name,
        )

    logger.info(
        "tool_call_recorded",
        server_id=server_id,
        tool=tool_name,
        status=status,
    )
    return {"recorded": True, "tool": tool_name}


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.services.analytics.tasks.record_tool_call",
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def record_tool_call(
    self: Task,
    server_id: str,
    tool_name: str,
    status: str,
    latency_ms: int | None = None,
    response_size_bytes: int | None = None,
    error_type: str | None = None,
    error_msg: str | None = None,
    client_name: str | None = None,
) -> dict[str, Any]:
    """Record a tool call event.

    Called from the gateway hot path as a fire-and-forget Celery task.
    Retries up to 3 times on transient failures.
    """
    try:
        return _loop.run_until_complete(
            _record_tool_call_async(
                server_id=server_id,
                tool_name=tool_name,
                status=status,
                latency_ms=latency_ms,
                response_size_bytes=response_size_bytes,
                error_type=error_type,
                error_msg=error_msg,
                client_name=client_name,
            ),
        )
    except Exception as exc:
        logger.warning("record_tool_call_retrying", error=str(exc))
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("record_tool_call_failed", error=str(exc))
            return {"recorded": False, "error": str(exc)}
        # self.retry() always raises -- this line is unreachable but
        # required to satisfy mypy's [return] check.
        return {"recorded": False, "error": str(exc)}


# ── aggregate_hourly ────────────────────────────────────────────────


async def _aggregate_hourly_async() -> dict[str, Any]:
    """Core async hourly aggregation logic.

    Computes the previous full hour, ensures the unique index exists,
    runs the hourly rollup, and conditionally runs the daily rollup
    if a day boundary was crossed.
    """
    now = datetime.now(UTC)
    hour_bucket = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    async with AsyncSessionLocal() as session:
        aggregator = AnalyticsAggregator(session)
        await aggregator.ensure_unique_index()
        count = await aggregator.aggregate_hour(hour_bucket)

        daily_aggregated = False
        if hour_bucket.date() < now.date():
            day = hour_bucket.date()
            await aggregator.aggregate_daily(day)
            daily_aggregated = True

        await session.commit()

        logger.info(
            "hourly_aggregation_complete",
            hour=hour_bucket.isoformat(),
            rows=count,
        )
        return {
            "hour": hour_bucket.isoformat(),
            "rows_written": count,
            "daily_aggregated": daily_aggregated,
        }


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.services.analytics.tasks.aggregate_hourly",
    max_retries=2,
    acks_late=True,
)
def aggregate_hourly(self: Task) -> dict[str, Any]:
    """Aggregate the previous full hour of tool call data.

    Runs via Celery beat every hour at :05 past the hour.
    """
    try:
        return _loop.run_until_complete(_aggregate_hourly_async())
    except Exception as exc:
        logger.warning("hourly_aggregation_retrying", error=str(exc))
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("hourly_aggregation_failed", error=str(exc))
            return {"error": str(exc), "rows_written": 0, "daily_aggregated": False}
        # self.retry() always raises -- this line is unreachable but
        # required to satisfy mypy's [return] check.
        return {"error": "unreachable", "rows_written": 0, "daily_aggregated": False}


# ── create_partitions ───────────────────────────────────────────────


async def _create_partitions_async() -> dict[str, Any]:
    """Core async partition creation logic."""
    manager = PartitionManager()
    count = await manager.ensure_partitions(days_ahead=7)
    logger.info("partitions_created", count=count, days_ahead=7)
    return {"partitions_created": count, "days_ahead": 7}


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.services.analytics.tasks.create_partitions",
    max_retries=1,
    acks_late=True,
)
def create_partitions(self: Task) -> dict[str, Any]:
    """Create daily partitions for the next 7 days.

    Runs via Celery beat daily at 00:30 UTC.
    """
    try:
        return _loop.run_until_complete(_create_partitions_async())
    except Exception as exc:
        logger.warning("create_partitions_retrying", error=str(exc))
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("create_partitions_failed", error=str(exc))
            return {"error": str(exc), "partitions_created": 0}
        # self.retry() always raises -- this line is unreachable but
        # required to satisfy mypy's [return] check.
        return {"error": "unreachable", "partitions_created": 0}


# ── cleanup_old_partitions ──────────────────────────────────────────


async def _cleanup_old_partitions_async(retention_days: int) -> dict[str, Any]:
    """Core async partition cleanup logic."""
    manager = PartitionManager()
    count = await manager.cleanup_old_partitions(retention_days=retention_days)
    logger.info("partitions_cleaned_up", count=count, retention_days=retention_days)
    return {"partitions_dropped": count, "retention_days": retention_days}


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.services.analytics.tasks.cleanup_old_partitions",
    max_retries=1,
    acks_late=True,
)
def cleanup_old_partitions(self: Task, retention_days: int = 7) -> dict[str, Any]:
    """Drop partitions older than retention_days.

    Runs via Celery beat weekly on Sundays at 03:00 UTC.
    """
    try:
        return _loop.run_until_complete(
            _cleanup_old_partitions_async(retention_days=retention_days),
        )
    except Exception as exc:
        logger.warning("cleanup_partitions_retrying", error=str(exc))
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("cleanup_partitions_failed", error=str(exc))
            return {"error": str(exc), "partitions_dropped": 0}
        # self.retry() always raises -- this line is unreachable but
        # required to satisfy mypy's [return] check.
        return {"error": "unreachable", "partitions_dropped": 0}
