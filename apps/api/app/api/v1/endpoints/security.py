"""Security scanner endpoints (F5) — route stubs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/servers/{server_id}/security", tags=["security"])


@router.post("/scan", status_code=501)
async def trigger_scan(server_id: UUID) -> None:
    """Trigger a security scan (Celery job). Pending F5."""
    raise NotImplementedFeatureError("Security Scanner: pending F5")


@router.get("/latest", status_code=501)
async def get_latest_scan(server_id: UUID) -> None:
    """Get the most recent scan result. Pending F5."""
    raise NotImplementedFeatureError("Security Scanner: pending F5")


@router.get("/scans", status_code=501)
async def list_scans(server_id: UUID) -> None:
    """List all scans for a server (paginated). Pending F5."""
    raise NotImplementedFeatureError("Security Scanner: pending F5")


@router.post("/{finding_id}/acknowledge", status_code=501)
async def acknowledge_finding(server_id: UUID, finding_id: str) -> None:
    """Acknowledge a specific finding. Pending F5."""
    raise NotImplementedFeatureError("Security Scanner: pending F5")


@router.get("/report.json", status_code=501)
async def export_report(server_id: UUID) -> None:
    """Export the latest scan as JSON. Pending F5."""
    raise NotImplementedFeatureError("Security Scanner: pending F5")


@router.get("/acknowledgments", status_code=501)
async def list_acknowledgments(server_id: UUID) -> None:
    """List all acknowledgments for a server. Pending F5."""
    raise NotImplementedFeatureError("Security Scanner: pending F5")
