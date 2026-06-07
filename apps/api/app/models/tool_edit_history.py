"""Tool description edit history (F2 — AI enhancement + edit tracking).

When a user edits a tool description (or the AI Engine proposes one and
the user accepts/rejects), a row is appended here. The next 7 days of
call-rate delta is computed against the description at that point in
time, supporting the "did the AI improve the description?" loop.

Currently used by F6 § 5 (description performance tracking). Kept in
the skeleton so the schema is locked before F6 needs it.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.mcp_server import MCPServer
    from app.models.user import User


class ToolEditHistory(Base, UUIDMixin):
    """An immutable record of a tool description change."""

    __tablename__ = "tool_edit_history"

    server_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    edited_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    edit_source: Mapped[str] = mapped_column(String(20), nullable=False)
    # edit_source: ai | user | revert
    previous_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<ToolEditHistory {self.tool_name} {self.edit_source}>"
