"""ServerVersion model — stores configuration snapshots for rollback."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.mcp_server import MCPServer
    from app.models.user import User


class ServerVersion(Base, UUIDMixin, TimestampMixin):
    """Snapshot of a server's tool configuration at a point in time."""

    __tablename__ = "server_versions"

    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    tools_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    server: Mapped[MCPServer] = relationship(
        "MCPServer", back_populates="versions", foreign_keys=[server_id]
    )
    changed_by_user: Mapped[User | None] = relationship(
        "User", back_populates="changed_versions", foreign_keys=[changed_by]
    )

    def __repr__(self) -> str:
        return f"<ServerVersion {self.server_id} v{self.version}>"
