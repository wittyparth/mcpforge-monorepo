"""Add security_scan_results + security_acknowledgments tables.

security_scan_results stores the JSONB findings array from the F5 scanner.
security_acknowledgments records that a user has reviewed and accepted
specific findings (e.g., SSRF that is mitigated by an upstream proxy).

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_scan_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_status", sa.String(20), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("high_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("medium_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("info_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("scan_duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_scan_results_server_scanned",
        "security_scan_results",
        ["server_id", sa.text("scanned_at DESC")],
    )

    op.create_table(
        "security_acknowledgments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", sa.String(100), nullable=False),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
        sa.UniqueConstraint("server_id", "finding_id", name="uq_ack_server_finding"),
    )


def downgrade() -> None:
    op.drop_table("security_acknowledgments")
    op.drop_index("idx_scan_results_server_scanned", table_name="security_scan_results")
    op.drop_table("security_scan_results")
