"""Add teams, team_memberships, team_invitations, audit_logs, mcp_servers.owner/team columns.

This is the F7 multi-user-organization foundation. New servers set
`owner_user_id` (always) and optionally `team_id`; legacy servers keep
`user_id` and have `owner_user_id=NULL` (we look up via `user_id` for
backwards compat).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── teams ─────────────────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default=sa.text("'team'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
    )

    # ── team_memberships ──────────────────────────────────────────────────
    op.create_table(
        "team_memberships",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"]),
    )
    op.create_index("idx_memberships_user_id", "team_memberships", ["user_id"])

    # ── team_invitations ─────────────────────────────────────────────────
    op.create_table(
        "team_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token", sa.String(100), nullable=False, unique=True),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"]),
    )
    op.create_index("idx_invitations_token", "team_invitations", ["token"])
    op.create_index("idx_invitations_email", "team_invitations", ["email"])

    # ── mcp_servers: add team_id and owner_user_id ───────────────────────
    op.add_column("mcp_servers", sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("mcp_servers", sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("idx_servers_team_id", "mcp_servers", ["team_id"])
    op.create_foreign_key(
        "fk_servers_team_id",
        "mcp_servers",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_servers_owner_user_id",
        "mcp_servers",
        "users",
        ["owner_user_id"],
        ["id"],
    )

    # ── audit_logs ───────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_audit_team_created", "audit_logs", ["team_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_user_created", "audit_logs", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("idx_audit_action", table_name="audit_logs")
    op.drop_index("idx_audit_user_created", table_name="audit_logs")
    op.drop_index("idx_audit_team_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_constraint("fk_servers_owner_user_id", "mcp_servers", type_="foreignkey")
    op.drop_constraint("fk_servers_team_id", "mcp_servers", type_="foreignkey")
    op.drop_index("idx_servers_team_id", table_name="mcp_servers")
    op.drop_column("mcp_servers", "owner_user_id")
    op.drop_column("mcp_servers", "team_id")
    op.drop_index("idx_invitations_email", table_name="team_invitations")
    op.drop_index("idx_invitations_token", table_name="team_invitations")
    op.drop_table("team_invitations")
    op.drop_index("idx_memberships_user_id", table_name="team_memberships")
    op.drop_table("team_memberships")
    op.drop_table("teams")
