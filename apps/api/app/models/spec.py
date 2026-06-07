"""Spec source model (F1 — OpenAPI ingestion).

A `SpecSource` records a fetched or uploaded OpenAPI document. The raw
spec is stored in Cloudflare R2 (S3-compatible); the DB row holds
metadata + the R2 key. Parsing happens on demand, not at insert time.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class SpecSource(Base, UUIDMixin, TimestampMixin):
    """An OpenAPI spec source (URL or upload)."""

    __tablename__ = "spec_sources"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # url | upload
    r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    openapi_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    endpoint_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spec_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    fetch_status: Mapped[str] = mapped_column(String(20), default="pending")
    fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"<SpecSource {self.id} {self.source_type}>"
