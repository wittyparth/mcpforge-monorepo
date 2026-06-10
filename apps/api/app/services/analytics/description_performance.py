"""Description performance tracking (F6 — Analytics).

Measures the impact of tool description edits on call rates. Compares call
volume 7 days before and 7 days after a description change. This is the
unique MCPForge differentiator that validates the AI Description Engine.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.schemas.analytics import DescriptionPerformance

logger = get_logger(__name__)

# Number of days to look back/forward for call-rate comparison.
_COMPARISON_WINDOW_DAYS = 7


class DescriptionPerformanceTracker:
    """Tracks how description edits affect tool call rates.

    For each tool that has a description edit history, compares the call
    rate in the 7-day window before and after the edit.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the tracker with a DB session.

        Args:
            session: An active SQLAlchemy async session.
        """
        self.session = session

    async def get_performance(
        self,
        server_id: UUID,
        tool_name: str | None = None,
    ) -> list[DescriptionPerformance]:
        """Return description-edit performance for one or all tools.

        If ``tool_name`` is ``None``, all tools with edit history on the
        server are evaluated.

        Args:
            server_id: The target server UUID.
            tool_name: Specific tool to evaluate, or ``None`` for all.

        Returns:
            A list of ``DescriptionPerformance``, one per tool that has
            edit history.
        """
        if tool_name is not None:
            edits = await self._fetch_edits(server_id, tool_name)
        else:
            edits = await self._fetch_all_edits(server_id)

        performances: list[DescriptionPerformance] = []
        for edit in edits:
            perf = await self._compute_performance(
                server_id=server_id,
                tool_name=edit["tool_name"],
                edited_at=edit["created_at"],
                edit_source=edit["edit_source"],
            )
            performances.append(perf)

        return performances

    async def get_all_tools_performance(
        self,
        server_id: UUID,
    ) -> list[DescriptionPerformance]:
        """Return performance for every tool that has edit history.

        Convenience wrapper around :meth:`get_performance` with
        ``tool_name=None``.

        Args:
            server_id: The target server UUID.

        Returns:
            A list of ``DescriptionPerformance``.
        """
        return await self.get_performance(server_id, tool_name=None)

    async def _compute_performance(
        self,
        server_id: UUID,
        tool_name: str,
        edited_at: datetime,
        edit_source: str,
    ) -> DescriptionPerformance:
        """Compute the before/after call counts for a single edit.

        Args:
            server_id: The server UUID.
            tool_name: The tool name.
            edited_at: When the edit was made.
            edit_source: Who made the edit (``'ai'`` / ``'user'`` /
                ``'revert'``).

        Returns:
            A ``DescriptionPerformance`` with computed delta.
        """
        window_start = edited_at - timedelta(days=_COMPARISON_WINDOW_DAYS)
        window_end = edited_at + timedelta(days=_COMPARISON_WINDOW_DAYS)

        # Before edit.
        before_result = await self.session.execute(
            text("""
                SELECT COUNT(*)::bigint AS cnt
                FROM tool_calls
                WHERE server_id = :server_id
                  AND tool_name = :tool_name
                  AND called_at >= :window_start
                  AND called_at < :edited_at
            """),
            {
                "server_id": server_id,
                "tool_name": tool_name,
                "window_start": window_start,
                "edited_at": edited_at,
            },
        )
        before_count: int = before_result.scalar_one()

        # After edit.
        after_result = await self.session.execute(
            text("""
                SELECT COUNT(*)::bigint AS cnt
                FROM tool_calls
                WHERE server_id = :server_id
                  AND tool_name = :tool_name
                  AND called_at >= :edited_at
                  AND called_at < :window_end
            """),
            {
                "server_id": server_id,
                "tool_name": tool_name,
                "edited_at": edited_at,
                "window_end": window_end,
            },
        )
        after_count: int = after_result.scalar_one()

        # Compute delta.
        delta_pct: float | None = None
        if before_count > 0:
            delta_pct = ((after_count - before_count) / before_count) * 100.0

        # Build human-readable message.
        edit_date = edited_at.strftime("%Y-%m-%d")
        if before_count == 0 and after_count == 0:
            message = (
                f"After description update on {edit_date}, "
                "this tool's call rate could not be determined (no call data)"
            )
        elif before_count == 0:
            message = (
                f"After description update on {edit_date}, "
                f"this tool had {after_count} call(s) (no prior call data)"
            )
        elif delta_pct is not None and abs(delta_pct) < 0.5:
            message = (
                f"After description update on {edit_date}, "
                "this tool's call rate is unchanged"
            )
        elif delta_pct is not None and delta_pct > 0:
            message = (
                f"After description update on {edit_date}, "
                f"this tool's call rate increased {delta_pct:.1f}%"
            )
        elif delta_pct is not None:
            message = (
                f"After description update on {edit_date}, "
                f"this tool's call rate decreased {abs(delta_pct):.1f}%"
            )
        else:
            message = (
                f"After description update on {edit_date}, "
                "this tool's call rate could not be determined (no prior data)"
            )

        return DescriptionPerformance(
            tool_name=tool_name,
            edited_at=edited_at,
            edit_source=edit_source,
            before_call_count=before_count,
            after_call_count=after_count,
            delta_pct=delta_pct,
            message=message,
            no_edit=False,
        )

    async def _fetch_edits(
        self,
        server_id: UUID,
        tool_name: str,
    ) -> list[dict[str, Any]]:
        """Fetch the most recent edit for a specific tool.

        Args:
            server_id: The server UUID.
            tool_name: The tool name.

        Returns:
            A list with zero or one dict (the latest edit for this tool).
        """
        result = await self.session.execute(
            text("""
                SELECT tool_name, edit_source, created_at
                FROM tool_edit_history
                WHERE server_id = :server_id
                  AND tool_name = :tool_name
                  AND edit_source IN ('ai', 'user')
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"server_id": server_id, "tool_name": tool_name},
        )
        rows = result.fetchall()
        return [
            {
                "tool_name": r.tool_name,
                "edit_source": r.edit_source,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    async def _fetch_all_edits(
        self,
        server_id: UUID,
    ) -> list[dict[str, Any]]:
        """Fetch the most recent edit for every tool on the server.

        Uses a ``DISTINCT ON`` to get one row per tool (most recent edit).

        Args:
            server_id: The server UUID.

        Returns:
            List of dicts with the latest edit per tool.
        """
        result = await self.session.execute(
            text("""
                SELECT DISTINCT ON (tool_name)
                    tool_name, edit_source, created_at
                FROM tool_edit_history
                WHERE server_id = :server_id
                  AND edit_source IN ('ai', 'user')
                ORDER BY tool_name, created_at DESC
            """),
            {"server_id": server_id},
        )
        rows = result.fetchall()
        return [
            {
                "tool_name": r.tool_name,
                "edit_source": r.edit_source,
                "created_at": r.created_at,
            }
            for r in rows
        ]
