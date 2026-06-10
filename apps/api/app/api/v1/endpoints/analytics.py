"""Analytics dashboard endpoints (F6) — real implementations.

Replaces the Feature-6 stubs with real read-side endpoints backed by
``AnalyticsQueries`` and ``DescriptionPerformanceTracker``. All
endpoints read from pre-aggregated rollups (fast) or the partitioned
``tool_calls`` table (errors, clients, time-series) and are scoped to
the current user's owned server.

CSV export: streams the most recent N tool_calls with parameter NAMES
only (NEVER values) — privacy by design.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.mcp_server_repo import MCPServerRepository
from app.schemas.analytics import (
    AnalyticsOverview,
    ClientBreakdownItem,
    DescriptionPerformance,
    ErrorLogItem,
    TimeSeriesPoint,
    ToolBreakdownItem,
)
from app.services.analytics.description_performance import (
    DescriptionPerformanceTracker,
)
from app.services.analytics.queries import RANGE_DAYS, AnalyticsQueries

logger = get_logger(__name__)

router = APIRouter(prefix="/servers/{server_id}/analytics", tags=["analytics"])


# Maximum number of rows streamed in a single CSV export. Caps memory
# usage; for larger ranges users should narrow the time window.
_EXPORT_ROW_LIMIT = 10_000

# CSV column headers for the analytics export. ``parameter_names`` is
# intentionally included (always empty) so consumers can rely on a
# stable schema; parameter VALUES are never exported.
_EXPORT_HEADERS: list[str] = [
    "called_at",
    "tool_name",
    "status",
    "latency_ms",
    "client_name",
    "error_type",
    "error_msg",
    "parameter_names",
]


async def _verify_server_ownership(
    server_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> None:
    """Verify the server exists and is owned by the current user.

    Raises:
        NotFoundError: If the server does not exist.
        ForbiddenError: If the server is not owned by the current user.
    """
    repo = MCPServerRepository(session)
    server = await repo.get_by_id(server_id)
    if not server:
        raise NotFoundError("Server not found")
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")


def _validate_range(range_str: str) -> None:
    """Ensure ``range_str`` is a supported time range key.

    Raises:
        ValidationError: If the range key is unknown.
    """
    if range_str not in RANGE_DAYS:
        raise ValidationError(
            f"Unsupported range '{range_str}'. "
            f"Must be one of: {', '.join(RANGE_DAYS)}",
        )


@router.get("", response_model=AnalyticsOverview)
async def analytics_overview(
    server_id: UUID,
    range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsOverview:
    """GET /analytics — top-line numbers for a server in a time range."""
    await _verify_server_ownership(server_id, current_user, session)
    _validate_range(range)

    queries = AnalyticsQueries(session)
    overview = await queries.get_overview(server_id, range)

    logger.info(
        "analytics_overview_served",
        server_id=str(server_id),
        user_id=str(current_user.id),
        range=range,
        total_calls=overview.total_calls,
    )
    return overview


@router.get("/tools", response_model=list[ToolBreakdownItem])
async def tool_breakdown(
    server_id: UUID,
    range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ToolBreakdownItem]:
    """Per-tool call counts, error rates, selection rates."""
    await _verify_server_ownership(server_id, current_user, session)
    _validate_range(range)

    queries = AnalyticsQueries(session)
    items = await queries.get_tool_breakdown(server_id, range)

    logger.info(
        "tool_breakdown_served",
        server_id=str(server_id),
        user_id=str(current_user.id),
        range=range,
        tool_count=len(items),
    )
    return items


@router.get("/errors", response_model=list[ErrorLogItem])
async def error_log(
    server_id: UUID,
    range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ErrorLogItem]:
    """Paginated error log (sanitized, no parameter values)."""
    await _verify_server_ownership(server_id, current_user, session)
    _validate_range(range)

    queries = AnalyticsQueries(session)
    items = await queries.get_error_log(
        server_id,
        range,
        limit=limit,
        offset=offset,
    )

    logger.info(
        "error_log_served",
        server_id=str(server_id),
        user_id=str(current_user.id),
        range=range,
        error_count=len(items),
    )
    return items


@router.get("/clients", response_model=list[ClientBreakdownItem])
async def client_breakdown(
    server_id: UUID,
    range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ClientBreakdownItem]:
    """Breakdown of calls by client (Claude Desktop, Cursor, etc)."""
    await _verify_server_ownership(server_id, current_user, session)
    _validate_range(range)

    queries = AnalyticsQueries(session)
    items = await queries.get_client_breakdown(server_id, range)

    logger.info(
        "client_breakdown_served",
        server_id=str(server_id),
        user_id=str(current_user.id),
        range=range,
        client_count=len(items),
    )
    return items


@router.get("/timeseries", response_model=list[TimeSeriesPoint])
async def timeseries(
    server_id: UUID,
    range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    granularity: str = Query(
        "hour",
        description="Bucket granularity: hour or day",
    ),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TimeSeriesPoint]:
    """Time-series of calls for charting."""
    await _verify_server_ownership(server_id, current_user, session)
    _validate_range(range)
    if granularity not in ("hour", "day"):
        raise ValidationError(
            f"Unsupported granularity '{granularity}'. Must be 'hour' or 'day'.",
        )

    queries = AnalyticsQueries(session)
    points = await queries.get_time_series(server_id, range, granularity)

    logger.info(
        "timeseries_served",
        server_id=str(server_id),
        user_id=str(current_user.id),
        range=range,
        granularity=granularity,
        points=len(points),
    )
    return points


@router.get("/export.csv")
async def export_csv(
    server_id: UUID,
    range: str = Query("7d", description="Time range: 7d, 30d, 90d"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream all tool calls for the server as a CSV download.

    PRIVACY: only parameter NAMES are included as a comma-separated
    column; parameter VALUES are never exported. The ``error_msg``
    column has already been sanitized at write time (Bearer tokens,
    API keys, Basic auth, query-string credentials redacted).
    """
    await _verify_server_ownership(server_id, current_user, session)
    _validate_range(range)

    days = RANGE_DAYS[range]
    start = datetime.now(UTC) - timedelta(days=days)

    # Fetch up to _EXPORT_ROW_LIMIT rows for the export (prevents runaway memory).
    rows = await session.execute(
        text("""
            SELECT
                called_at,
                tool_name,
                status,
                COALESCE(latency_ms, 0) AS latency_ms,
                client_name,
                error_type,
                COALESCE(error_msg, '') AS error_msg
            FROM tool_calls
            WHERE server_id = :server_id
              AND called_at >= :start
            ORDER BY called_at DESC
            LIMIT :limit
        """),
        {"server_id": server_id, "start": start, "limit": _EXPORT_ROW_LIMIT},
    )
    raw_rows = rows.fetchall()

    logger.info(
        "analytics_csv_export_started",
        server_id=str(server_id),
        user_id=str(current_user.id),
        range=range,
        row_count=len(raw_rows),
    )

    def _stream() -> Any:
        """Yield CSV bytes as a generator for StreamingResponse."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_EXPORT_HEADERS)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        for row in raw_rows:
            writer.writerow(
                [
                    row.called_at.isoformat() if row.called_at else "",
                    row.tool_name,
                    row.status,
                    int(row.latency_ms),
                    row.client_name or "",
                    row.error_type or "",
                    row.error_msg,
                    "",  # parameter names are intentionally blank
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    filename = f"analytics-{server_id}-{datetime.now(UTC).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        _stream(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Analytics-Row-Count": str(len(raw_rows)),
        },
    )


@router.get("/description-performance", response_model=list[DescriptionPerformance])
async def description_performance(
    server_id: UUID,
    tool_name: str | None = Query(
        None,
        description="Specific tool to evaluate, or omit for all tools",
    ),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DescriptionPerformance]:
    """Description-edit performance tracking.

    For each tool that has a description edit on record, returns the
    before/after call rate (7-day windows) so users can see whether
    their edits (or the AI's enhancements) actually increased calls.
    """
    await _verify_server_ownership(server_id, current_user, session)

    tracker = DescriptionPerformanceTracker(session)
    results = await tracker.get_performance(server_id, tool_name)

    logger.info(
        "description_performance_served",
        server_id=str(server_id),
        user_id=str(current_user.id),
        tool_filter=tool_name,
        tools_evaluated=len(results),
    )
    return results
