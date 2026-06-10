"""Collision guard: password_changed_at and last_login_at.

These columns are ALREADY added by migration 0007 (which includes
the billing model). Migration 0010 was created on a branch where
0007 didn't have them. This is a no-op in production but exists
to allow `alembic upgrade head` to pass without errors.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-07 00:00:00.000000
"""

from collections.abc import Sequence

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Columns already exist from 0007_add_billing.py — skip to avoid
    # DuplicateColumnError on production.
    pass


def downgrade() -> None:
    # Columns are managed by 0007; nothing extra to undo here.
    pass
