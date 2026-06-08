"""sync schema with models

Revision ID: a442dec80a86
Revises: 0011
Create Date: 2026-06-08 02:49:28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a442dec80a86"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New tables from later-phase models ────────────────────────
    op.create_table(
        "tool_edit_history",
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("edited_by", sa.UUID(), nullable=True),
        sa.Column("edit_source", sa.String(length=20), nullable=False),
        sa.Column("previous_description", sa.Text(), nullable=True),
        sa.Column("new_description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["edited_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Missing updated_at columns ────────────────────────────────
    for table in [
        "analytics_rollups",
        "api_keys",
        "invoices",
        "spec_sources",
        "team_invitations",
        "tool_calls",
    ]:
        op.add_column(
            table,
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )

    op.add_column("credentials", sa.Column("rotated_by", sa.UUID(), nullable=True))
    op.add_column("credentials", sa.Column("last_used_at", sa.DateTime(), nullable=True))
    op.add_column("tool_calls", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))

    op.add_column(
        "security_acknowledgments",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "security_acknowledgments",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.add_column(
        "security_scan_results",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "security_scan_results",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )

    # ── Foreign keys ──────────────────────────────────────────────
    op.create_foreign_key(
        "fk_credentials_rotated_by", "credentials", "users", ["rotated_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_mcp_servers_credential_id", "mcp_servers", "credentials", ["credential_id"], ["id"],
        use_alter=True,
    )


def downgrade() -> None:
    for table in [
        "tool_calls",
        "team_invitations",
        "spec_sources",
        "invoices",
        "api_keys",
        "analytics_rollups",
    ]:
        op.drop_column(table, "updated_at")
    op.drop_column("tool_calls", "created_at")
    op.drop_column("credentials", "last_used_at")
    op.drop_column("credentials", "rotated_by")
    op.drop_column("security_scan_results", "updated_at")
    op.drop_column("security_scan_results", "created_at")
    op.drop_column("security_acknowledgments", "updated_at")
    op.drop_column("security_acknowledgments", "created_at")
    op.drop_constraint("fk_mcp_servers_credential_id", "mcp_servers", type_="foreignkey")
    op.drop_constraint("fk_credentials_rotated_by", "credentials", type_="foreignkey")
    op.drop_table("tool_edit_history")
