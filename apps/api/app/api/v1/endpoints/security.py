"""Security scanner endpoints (F5) — real implementations.

Replaces the Feature-5 stubs with real CRUD endpoints backed by
SecurityScanRepository and SecurityAckRepository.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.mcp_server_repo import MCPServerRepository
from app.repositories.security_repo import SecurityAckRepository, SecurityScanRepository
from app.schemas.security import (
    AcknowledgeRequest,
    AcknowledgeResponse,
    ScanHistoryResponse,
    ScanResultResponse,
    ScanTriggerResponse,
    SecurityReport,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/servers/{server_id}/security", tags=["security"])


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


@router.post("/scan", response_model=ScanTriggerResponse)
async def trigger_scan(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScanTriggerResponse:
    """Trigger a security scan (runs as a background Celery task)."""
    await _verify_server_ownership(server_id, current_user, session)

    from app.services.security_scanner.tasks import scan_server

    task = scan_server.delay(str(server_id), request_id="")
    logger.info(
        "security_scan_triggered",
        server_id=str(server_id),
        user_id=str(current_user.id),
        task_id=task.id,
    )
    return ScanTriggerResponse(
        scan_id=server_id,
        scan_status="running",
        message="Security scan initiated",
    )


@router.get("/latest", response_model=ScanResultResponse | None)
async def get_latest_scan(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScanResultResponse | None:
    """Get the most recent security scan result. Returns ``null`` if no scan has been run yet."""
    await _verify_server_ownership(server_id, current_user, session)

    scan_repo = SecurityScanRepository(session)
    scan = await scan_repo.get_latest(server_id)
    if not scan:
        logger.info("no_scan_found", server_id=str(server_id), user_id=str(current_user.id))
        return None

    logger.info(
        "scan_fetched",
        server_id=str(server_id),
        user_id=str(current_user.id),
        scan_id=str(scan.id),
    )
    return ScanResultResponse.model_validate(scan)


@router.get("/scans", response_model=ScanHistoryResponse)
async def list_scans(
    server_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScanHistoryResponse:
    """List security scan history for a server (paginated)."""
    await _verify_server_ownership(server_id, current_user, session)

    scan_repo = SecurityScanRepository(session)
    skip = (page - 1) * page_size
    scans = await scan_repo.list_by_server(server_id, skip=skip, limit=page_size)
    total = await scan_repo.count_by_server(server_id)

    next_page = page + 1 if (skip + page_size) < total else None

    logger.info(
        "scans_listed",
        server_id=str(server_id),
        user_id=str(current_user.id),
        total=total,
        page=page,
    )
    return ScanHistoryResponse(
        items=[ScanResultResponse.model_validate(s) for s in scans],
        total=total,
        page=page,
        page_size=page_size,
        next_page=next_page,
    )


@router.post("/{finding_id}/acknowledge", response_model=AcknowledgeResponse)
async def acknowledge_finding(
    server_id: UUID,
    finding_id: str,
    body: AcknowledgeRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AcknowledgeResponse:
    """Acknowledge a security finding (suppresses in future scans)."""
    await _verify_server_ownership(server_id, current_user, session)

    ack_repo = SecurityAckRepository(session)
    ack = await ack_repo.acknowledge(
        server_id=server_id,
        finding_id=finding_id,
        user_id=current_user.id,
        note=body.note,
    )

    logger.info(
        "finding_acknowledged",
        server_id=str(server_id),
        finding_id=finding_id,
        user_id=str(current_user.id),
    )
    return AcknowledgeResponse(
        server_id=server_id,
        finding_id=finding_id,
        acknowledged_at=ack.acknowledged_at,
    )


@router.delete("/{finding_id}/acknowledge", status_code=204, response_model=None)
async def remove_acknowledgment(
    server_id: UUID,
    finding_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove an acknowledgment for a finding."""
    await _verify_server_ownership(server_id, current_user, session)

    ack_repo = SecurityAckRepository(session)
    await ack_repo.remove_acknowledgment(server_id, finding_id)

    logger.info(
        "acknowledgment_removed",
        server_id=str(server_id),
        finding_id=finding_id,
        user_id=str(current_user.id),
    )


@router.get("/report.json", response_model=SecurityReport)
async def export_report(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SecurityReport:
    """Export the latest scan as a full security report."""
    await _verify_server_ownership(server_id, current_user, session)

    scan_repo = SecurityScanRepository(session)
    ack_repo = SecurityAckRepository(session)

    scan = await scan_repo.get_latest(server_id)
    acks = await ack_repo.get_for_server(server_id)

    # Build server name
    server_repo = MCPServerRepository(session)
    server = await server_repo.get_by_id(server_id)
    server_name = server.name if server else ""

    # Build summary parts
    summary_parts: list[str] = []
    if scan:
        parts: list[str] = []
        if scan.critical_count:
            parts.append(f"{scan.critical_count} critical")
        if scan.high_count:
            parts.append(f"{scan.high_count} high")
        if scan.medium_count:
            parts.append(f"{scan.medium_count} medium")
        if scan.info_count:
            parts.append(f"{scan.info_count} info")
        findings_summary = ", ".join(parts) if parts else "No findings"
        summary_parts.append(f"Findings: {findings_summary}")
        summary_parts.append(f"Status: {scan.scan_status}")
    else:
        summary_parts.append("No scan data available")

    if acks:
        summary_parts.append(f"Acknowledged findings: {len(acks)}")

    return SecurityReport(
        server_id=server_id,
        server_name=server_name,
        generated_at=datetime.now(UTC),
        scan=ScanResultResponse.model_validate(scan) if scan else None,
        acknowledgments=[
            AcknowledgeResponse(
                server_id=a.server_id,
                finding_id=a.finding_id,
                acknowledged_at=a.acknowledged_at,
            )
            for a in acks
        ],
        summary=" | ".join(summary_parts),
    )


@router.get("/acknowledgments", response_model=dict[str, Any])
async def list_acknowledgments(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List all acknowledgments for a server."""
    await _verify_server_ownership(server_id, current_user, session)

    ack_repo = SecurityAckRepository(session)
    acks = await ack_repo.get_for_server(server_id)

    logger.info(
        "acknowledgments_listed",
        server_id=str(server_id),
        user_id=str(current_user.id),
        total=len(acks),
    )
    return {
        "items": [
            AcknowledgeResponse(
                server_id=a.server_id,
                finding_id=a.finding_id,
                acknowledged_at=a.acknowledged_at,
            ).model_dump()
            for a in acks
        ],
        "total": len(acks),
    }
