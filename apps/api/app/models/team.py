"""Team models (F7).

- `Team` is a multi-user organization.
- `TeamMembership` is the join table with a role.
- `TeamInvitation` is a pending email invite with a unique token.

The team owner is recorded on `Team.owner_id`. The `TeamMembership.role`
enum is `admin | editor | viewer` — validated at the service layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.audit_log import AuditLog
    from app.models.billing import Subscription
    from app.models.mcp_server import MCPServer


class Team(Base, UUIDMixin, TimestampMixin):
    """A team / organization."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String(20), default="team")

    memberships: Mapped[list[TeamMembership]] = relationship(
        "TeamMembership", back_populates="team", cascade="all, delete-orphan"
    )
    invitations: Mapped[list[TeamInvitation]] = relationship(
        "TeamInvitation", back_populates="team", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="team", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list[ApiKey]] = relationship(
        "ApiKey", back_populates="team", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list[Subscription]] = relationship(
        "Subscription", back_populates="team", cascade="all, delete-orphan"
    )
    servers: Mapped[list[MCPServer]] = relationship(
        "MCPServer", back_populates="team", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Team {self.name}>"


class TeamMembership(Base):
    """A user's membership in a team with a role.

    Composite PK on (team_id, user_id). The base classes are NOT used
    because we don't want UUIDMixin (we have a composite key) or
    TimestampMixin (we only have joined_at, not updated_at — you can't
    "update" a membership, you can only change role or remove).
    """

    __tablename__ = "team_memberships"

    team_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin | editor | viewer
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invited_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    team: Mapped[Team] = relationship("Team", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<TeamMembership {self.team_id}/{self.user_id} {self.role}>"


class TeamInvitation(Base, UUIDMixin, TimestampMixin):
    """A pending invitation to join a team."""

    __tablename__ = "team_invitations"

    team_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    invited_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    team: Mapped[Team] = relationship("Team", back_populates="invitations")

    def __repr__(self) -> str:
        return f"<TeamInvitation {self.email} {self.team_id}>"
