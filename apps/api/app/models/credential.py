"""Credential model — stores encrypted API credentials for MCP servers.

# TODO(phase-2): Use AWS KMS for key management instead of local encryption.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.mcp_server import MCPServer
    from app.models.user import User


class Credential(Base, UUIDMixin, TimestampMixin):
    """Encrypted API credential for an MCP server."""

    __tablename__ = "credentials"

    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    env_var_name: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_key_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    rotated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    server: Mapped[MCPServer] = relationship(
        "MCPServer", back_populates="credentials", foreign_keys=[server_id]
    )
    user: Mapped[User] = relationship("User", back_populates="credentials")

    def __repr__(self) -> str:
        return f"<Credential {self.env_var_name}>"
