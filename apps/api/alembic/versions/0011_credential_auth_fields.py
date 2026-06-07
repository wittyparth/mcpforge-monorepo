"""Add auth_scheme and auth_header_name columns to credentials table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "credentials",
        sa.Column("auth_scheme", sa.String(20), nullable=False, server_default="bearer"),
    )
    op.add_column(
        "credentials",
        sa.Column("auth_header_name", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("credentials", "auth_header_name")
    op.drop_column("credentials", "auth_scheme")
