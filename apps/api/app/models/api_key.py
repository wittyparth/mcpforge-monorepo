"""API key model (F7 — programmatic access).

Plaintext key returned ONCE at creation. Format:
`mcpforge_live_<32 random base62 chars>`. The full plaintext is hashed
with SHA-256 (these are high-entropy; bcrypt would be overkill) and
the hash is stored in `key_hash`. The first 8 chars of the plaintext
are stored in `key_prefix` for UI display.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.user import User


class ApiKey(Base, UUIDMixin, TimestampMixin):
    """An API key for programmatic access to the MCPForge API."""

    __tablename__ = "api_keys"
    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    team: Mapped[Team | None] = relationship("Team", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey {self.name} {self.key_prefix}>"
