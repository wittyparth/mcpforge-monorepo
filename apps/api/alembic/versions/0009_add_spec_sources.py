"""Add spec_sources table for OpenAPI ingestion (F1).

spec_sources is a record of a fetched/uploaded spec, with the parsed
content stored in R2 (Cloudflare R2, S3-compatible). The DB row holds
the R2 key plus metadata. The actual `mcp_servers.tools_config` is
generated from spec_sources + the user's tool selection.

Revision ID: 0009
Revises: 0007
Create Date: 2026-06-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spec_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),  # url | upload
        sa.Column("r2_key", sa.String(500), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("openapi_version", sa.String(20), nullable=True),
        sa.Column("endpoint_count", sa.Integer(), nullable=True),
        sa.Column("spec_size_bytes", sa.Integer(), nullable=True),
        sa.Column("fetch_status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("fetch_error", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_spec_sources_user_id", "spec_sources", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_spec_sources_user_id", table_name="spec_sources")
    op.drop_table("spec_sources")
