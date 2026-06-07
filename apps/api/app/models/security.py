"""Security scan models (F5).

- `SecurityScanResult` stores a single scan's findings JSONB + counts.
- `SecurityAcknowledgment` records that a user has accepted a specific
  finding (e.g., SSRF that is mitigated by an upstream proxy). One row
  per (server_id, finding_id) — enforced by unique constraint.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.mcp_server import MCPServer
    from app.models.user import User


class SecurityScanResult(Base, UUIDMixin, TimestampMixin):
    """A completed security scan (F5)."""

    __tablename__ = "security_scan_results"

    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )
    scan_status: Mapped[str] = mapped_column(String(20), nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    high_count: Mapped[int] = mapped_column(Integer, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, default=0)
    info_count: Mapped[int] = mapped_column(Integer, default=0)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scan_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<SecurityScanResult {self.server_id} {self.scan_status}>"


class SecurityAcknowledgment(Base, UUIDMixin, TimestampMixin):
    """A user's acknowledgment of a specific security finding."""

    __tablename__ = "security_acknowledgments"
    __table_args__ = (
        # Unique per (server_id, finding_id) — a finding can only be acked once.
        # We declare this via __table_args__ rather than a UniqueConstraint kwarg
        # so SQLAlchemy emits it as a named constraint matching the Alembic migration.
        __import__("sqlalchemy").UniqueConstraint(
            "server_id", "finding_id", name="uq_ack_server_finding"
        ),
    )

    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_id: Mapped[str] = mapped_column(String(100), nullable=False)
    acknowledged_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SecurityAcknowledgment {self.server_id}/{self.finding_id}>"
