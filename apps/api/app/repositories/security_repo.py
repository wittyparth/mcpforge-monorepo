"""Security scan and acknowledgment data access layer.

- ``SecurityScanRepository`` — CRUD for ``SecurityScanResult``
- ``SecurityAckRepository`` — CRUD for ``SecurityAcknowledgment``
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.security import SecurityAcknowledgment, SecurityScanResult


class SecurityScanRepository:
    """Repository for SecurityScanResult CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        server_id: UUID,
        scan_status: str,
        findings: list[dict[str, Any]] | None = None,
        critical_count: int = 0,
        high_count: int = 0,
        medium_count: int = 0,
        info_count: int = 0,
        scan_duration_ms: int | None = None,
    ) -> SecurityScanResult:
        """Create a new security scan result."""
        scan = SecurityScanResult(
            server_id=server_id,
            scan_status=scan_status,
            findings=findings or [],
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            info_count=info_count,
            scanned_at=datetime.now(UTC),
            scan_duration_ms=scan_duration_ms,
        )
        self.session.add(scan)
        await self.session.flush()
        return scan

    async def get_latest(self, server_id: UUID) -> SecurityScanResult | None:
        """Get the most recent scan result for a server."""
        result = await self.session.execute(
            select(SecurityScanResult)
            .where(SecurityScanResult.server_id == server_id)
            .order_by(desc(SecurityScanResult.scanned_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, scan_id: UUID) -> SecurityScanResult | None:
        """Get a scan result by its UUID."""
        result = await self.session.execute(
            select(SecurityScanResult).where(SecurityScanResult.id == scan_id)
        )
        return result.scalar_one_or_none()

    async def list_by_server(
        self,
        server_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[SecurityScanResult]:
        """List scan results for a server (newest first)."""
        result = await self.session.execute(
            select(SecurityScanResult)
            .where(SecurityScanResult.server_id == server_id)
            .order_by(desc(SecurityScanResult.scanned_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_server(self, server_id: UUID) -> int:
        """Count scan results for a server."""
        result = await self.session.execute(
            select(func.count(SecurityScanResult.id)).where(
                SecurityScanResult.server_id == server_id
            )
        )
        return result.scalar() or 0

    async def delete_older_than(
        self,
        server_id: UUID,
        keep_count: int = 20,
    ) -> int:
        """Delete old scans beyond the most recent ``keep_count``.

        Returns the number of deleted rows.
        """
        # Subquery: IDs of the most recent ``keep_count`` scans to keep
        keep_ids = (
            select(SecurityScanResult.id)
            .where(SecurityScanResult.server_id == server_id)
            .order_by(desc(SecurityScanResult.scanned_at))
            .limit(keep_count)
            .scalar_subquery()
        )
        stmt = delete(SecurityScanResult).where(
            SecurityScanResult.server_id == server_id,
            SecurityScanResult.id.notin_(keep_ids),
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        # rowcount is on CursorResult but type stubs don't expose it
        return result.rowcount  # type: ignore[attr-defined, no-any-return]


class SecurityAckRepository:
    """Repository for SecurityAcknowledgment CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def acknowledge(
        self,
        *,
        server_id: UUID,
        finding_id: str,
        user_id: UUID,
        note: str | None = None,
    ) -> SecurityAcknowledgment:
        """Acknowledge a security finding.

        Raises ``ConflictError`` if the finding is already acknowledged.
        """
        ack = SecurityAcknowledgment(
            server_id=server_id,
            finding_id=finding_id,
            acknowledged_by=user_id,
            acknowledged_at=datetime.now(UTC),
            note=note,
        )
        self.session.add(ack)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"Finding '{finding_id}' is already acknowledged for this server"
            ) from exc
        return ack

    async def remove_acknowledgment(
        self,
        server_id: UUID,
        finding_id: str,
    ) -> bool:
        """Remove an acknowledgment. Returns True if one was removed."""
        stmt = delete(SecurityAcknowledgment).where(
            SecurityAcknowledgment.server_id == server_id,
            SecurityAcknowledgment.finding_id == finding_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        # rowcount is on CursorResult but type stubs don't expose it
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

    async def get_for_server(
        self,
        server_id: UUID,
    ) -> list[SecurityAcknowledgment]:
        """Get all acknowledgments for a server (newest first)."""
        result = await self.session.execute(
            select(SecurityAcknowledgment)
            .where(SecurityAcknowledgment.server_id == server_id)
            .order_by(SecurityAcknowledgment.acknowledged_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_server_and_finding(
        self,
        server_id: UUID,
        finding_id: str,
    ) -> SecurityAcknowledgment | None:
        """Get a specific acknowledgment for a server and finding."""
        result = await self.session.execute(
            select(SecurityAcknowledgment).where(
                SecurityAcknowledgment.server_id == server_id,
                SecurityAcknowledgment.finding_id == finding_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_for_server(self, server_id: UUID) -> int:
        """Count acknowledgments for a server."""
        result = await self.session.execute(
            select(func.count(SecurityAcknowledgment.id)).where(
                SecurityAcknowledgment.server_id == server_id
            )
        )
        return result.scalar() or 0
