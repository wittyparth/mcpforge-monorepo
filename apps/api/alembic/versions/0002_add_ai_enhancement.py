"""Add AI-enhancement fields to mcp_servers.

Adds columns tracked by the AI Description Engine (F2):
- description_review_status: pending | in_progress | review | accepted | rejected
- last_ai_run_at: when the engine last ran on this server
- ai_enhancement_cost_cents: cumulative cents spent (cost transparency)
- original_tools_config: JSONB snapshot before AI ran, for "revert all"

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column(
            "description_review_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column(
        "mcp_servers",
        sa.Column("last_ai_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mcp_servers",
        sa.Column(
            "ai_enhancement_cost_cents",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "mcp_servers",
        sa.Column("original_tools_config", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_servers", "original_tools_config")
    op.drop_column("mcp_servers", "ai_enhancement_cost_cents")
    op.drop_column("mcp_servers", "last_ai_run_at")
    op.drop_column("mcp_servers", "description_review_status")
