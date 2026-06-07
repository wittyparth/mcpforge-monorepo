"""Add tool_calls (partitioned by day) + analytics_rollups.

tool_calls is partitioned by `called_at` (RANGE) for:
- Efficient time-range queries (analytics dashboard, error log).
- Cheap retention: drop old partitions in a Celery beat job.

Analytics_rollups is a flat table of hourly aggregates per server+tool.
Written by the analytics Celery task, read by the dashboard.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tool_calls (parent partitioned table) ────────────────────────────
    op.execute(
        """
        CREATE TABLE tool_calls (
            id                  UUID DEFAULT gen_random_uuid(),
            server_id           UUID NOT NULL,
            tool_name           VARCHAR(200) NOT NULL,
            status              VARCHAR(20) NOT NULL,
            error_type          VARCHAR(100),
            error_msg           TEXT,
            latency_ms          INTEGER,
            response_size_bytes INTEGER,
            client_name         VARCHAR(100),
            called_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, called_at)
        ) PARTITION BY RANGE (called_at);
        """
    )
    op.create_index(
        "idx_tool_calls_server_id_called_at",
        "tool_calls",
        ["server_id", "called_at"],
    )
    op.create_index(
        "idx_tool_calls_tool_name_called_at",
        "tool_calls",
        ["tool_name", "called_at"],
    )
    op.create_index(
        "idx_tool_calls_status_called_at",
        "tool_calls",
        ["status", "called_at"],
        postgresql_where=sa.text("status != 'success'"),
    )

    # ── Pre-create partitions for current and next month ──────────────────
    # Celery beat creates future partitions daily; here we cover the next 60 days.
    from datetime import UTC, datetime, timedelta

    today = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for month_offset in range(3):
        month_start = today + timedelta(days=32 * month_offset)
        month_start = month_start.replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        partition_name = f"tool_calls_{month_start.strftime('%Y_%m')}"
        op.execute(
            f"""
            CREATE TABLE {partition_name} PARTITION OF tool_calls
            FOR VALUES FROM ('{month_start.isoformat()}') TO ('{next_month.isoformat()}');
            """
        )

    # ── analytics_rollups ─────────────────────────────────────────────────
    op.create_table(
        "analytics_rollups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(200), nullable=True),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granularity", sa.String(10), nullable=False),  # hour | day
        sa.Column("call_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "idx_rollups_server_bucket",
        "analytics_rollups",
        ["server_id", "bucket_start"],
    )
    op.create_index(
        "idx_rollups_granularity",
        "analytics_rollups",
        ["granularity", "bucket_start"],
    )


def downgrade() -> None:
    op.drop_index("idx_rollups_granularity", table_name="analytics_rollups")
    op.drop_index("idx_rollups_server_bucket", table_name="analytics_rollups")
    op.drop_table("analytics_rollups")
    op.drop_index("idx_tool_calls_status_called_at", table_name="tool_calls")
    op.drop_index("idx_tool_calls_tool_name_called_at", table_name="tool_calls")
    op.drop_index("idx_tool_calls_server_id_called_at", table_name="tool_calls")
    op.execute("DROP TABLE tool_calls CASCADE;")
