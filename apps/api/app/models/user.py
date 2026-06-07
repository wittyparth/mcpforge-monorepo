"""User model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.credential import Credential
    from app.models.mcp_server import MCPServer
    from app.models.server_version import ServerVersion


class User(Base, UUIDMixin, TimestampMixin):
    """User account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)

    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    plan: Mapped[str] = mapped_column(String(20), default="free")
    plan_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ai_enhancement_credits: Mapped[int] = mapped_column(Integer, default=3)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    servers: Mapped[list[MCPServer]] = relationship(
        "MCPServer", back_populates="owner", cascade="all, delete-orphan"
    )
    credentials: Mapped[list[Credential]] = relationship(
        "Credential", back_populates="user", cascade="all, delete-orphan"
    )
    changed_versions: Mapped[list[ServerVersion]] = relationship(
        "ServerVersion", back_populates="changed_by_user", foreign_keys="ServerVersion.changed_by"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
