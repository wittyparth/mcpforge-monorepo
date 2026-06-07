"""Analytics dashboard endpoints (F6) — route stubs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/servers/{server_id}/analytics", tags=["analytics"])


@router.get("", status_code=501)
async def analytics_overview(server_id: UUID) -> None:
    """GET /analytics — top-line numbers for a range. Pending F6."""
    raise NotImplementedFeatureError("Analytics: pending F6")


@router.get("/tools", status_code=501)
async def tool_breakdown(server_id: UUID) -> None:
    """Per-tool call counts, error rates, selection rates. Pending F6."""
    raise NotImplementedFeatureError("Analytics: pending F6")


@router.get("/errors", status_code=501)
async def error_log(server_id: UUID) -> None:
    """Paginated error log (sanitized, no parameter values). Pending F6."""
    raise NotImplementedFeatureError("Analytics: pending F6")


@router.get("/clients", status_code=501)
async def client_breakdown(server_id: UUID) -> None:
    """Breakdown of calls by client (Claude Desktop, Cursor, etc). Pending F6."""
    raise NotImplementedFeatureError("Analytics: pending F6")


@router.get("/timeseries", status_code=501)
async def timeseries(server_id: UUID) -> None:
    """Time-series of calls. Pending F6."""
    raise NotImplementedFeatureError("Analytics: pending F6")


@router.get("/export.csv", status_code=501)
async def export_csv(server_id: UUID) -> None:
    """CSV export of all tool calls. Pending F6."""
    raise NotImplementedFeatureError("Analytics: pending F6")
