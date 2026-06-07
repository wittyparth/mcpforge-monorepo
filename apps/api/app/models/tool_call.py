"""Tool call telemetry (F6 — Analytics).

Two tables:
- `tool_calls` is partitioned by `called_at` (RANGE) for efficient
  time-range queries and cheap retention via `DROP PARTITION`. The
  gateway writes a row per call.
- `analytics_rollups` is a flat aggregate table; the Celery beat task
  `aggregate_hourly` writes to it every hour at :05. The dashboard
  reads from rollups for fast charting.

NEVER store parameter values in `tool_calls` — the gateway code that
populates this table is the only enforcement point. PII / credentials
in parameters would leak through analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ToolCall(Base, TimestampMixin):
    """A single tool call invocation (partitioned by called_at)."""

    __tablename__ = "tool_calls"
    __table_args__ = (
        # Composite PK is (id, called_at) per partitioning requirement.
        # We omit it here because partitioned tables are created via raw SQL
        # in the Alembic migration; this ORM model is for read/write access.
        {"postgresql_partition_by": "RANGE (called_at)"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    server_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )

    def __repr__(self) -> str:
        return f"<ToolCall {self.tool_name} {self.called_at}>"


class AnalyticsRollup(Base, UUIDMixin, TimestampMixin):
    """An hourly or daily aggregate of tool calls for a server/tool."""

    __tablename__ = "analytics_rollups"

    server_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granularity: Mapped[str] = mapped_column(String(10), nullable=False)  # hour | day
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<AnalyticsRollup {self.server_id} {self.granularity} {self.bucket_start}>"
