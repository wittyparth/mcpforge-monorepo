"""MCP Server model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, ForeignKey, ForeignKeyConstraint, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.credential import Credential
    from app.models.server_version import ServerVersion
    from app.models.user import User


class MCPServer(Base, UUIDMixin, TimestampMixin):
    """An MCP server created by a user from an OpenAPI spec."""

    __tablename__ = "mcp_servers"

    __table_args__ = (
        # Indexes per PRD section 10
        __import__("sqlalchemy").Index("idx_servers_slug", "slug"),
        __import__("sqlalchemy").Index("idx_servers_user_id", "user_id"),
        # Defer FK to break circular dependency with credentials.server_id
        ForeignKeyConstraint(
            ["credential_id"], ["credentials.id"],
            use_alter=True, name="fk_mcp_servers_credential_id",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="building"
    )  # building | active | paused | error

    # Source spec
    spec_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    spec_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Auth configuration
    auth_scheme: Mapped[str] = mapped_column(String(20), default="none")
    auth_header_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    credential_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # Tool configuration
    tools_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Transport
    transport_mode: Mapped[str] = mapped_column(String(20), default="sse")

    # Stats (cached)
    total_calls: Mapped[int] = mapped_column(BigInteger, default=0)
    monthly_calls: Mapped[int] = mapped_column(Integer, default=0)
    last_call_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1)

    # AI enhancement (F2)
    description_review_status: Mapped[str] = mapped_column(String(20), default="pending")
    last_ai_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ai_enhancement_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    original_tools_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Team ownership (F7)
    team_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    owner: Mapped[User] = relationship("User", back_populates="servers", foreign_keys=[user_id])
    team: Mapped[object | None] = relationship("Team", back_populates="servers")
    credentials: Mapped[list[Credential]] = relationship(
        "Credential", back_populates="server", cascade="all, delete-orphan",
        foreign_keys="Credential.server_id",
    )
    versions: Mapped[list[ServerVersion]] = relationship(
        "ServerVersion",
        back_populates="server",
        cascade="all, delete-orphan",
        foreign_keys="ServerVersion.server_id",
    )

    def __repr__(self) -> str:
        return f"<MCPServer {self.slug}>"
