"""Add password_changed_at and last_login_at columns to users table.

These columns are defined in the User SQLAlchemy model (Wave 0 hardening)
but were omitted from migration 0007 (which added stripe_customer_id but
not these). If the DB was created with the original 0007, those columns
don't exist and queries fail with UndefinedColumnError.

This migration can be safely applied regardless of whether the columns
already exist (IF NOT EXISTS would be ideal, but Alembic/PostgreSQL
don't support that for columns — running this twice will fail on the
first duplicate column error; check alembic_version before running).

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_changed_at")
