"""Celery tasks for the Security Scanner (F5).

Uses a module-level event loop instead of asyncio.run() so the
SQLAlchemy async engine's connection pool is always pinned to the same
loop -- avoiding Future attached to a different loop errors.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from celery import Task

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.sse import sse_manager
from app.services.security_scanner.scanner import SecurityScanner

logger = get_logger(__name__)

# Module-level event loop -- reused across all task invocations so the
# SQLAlchemy async engine's pool stays pinned to a single loop.
_loop = asyncio.new_event_loop()


async def _scan_async(server_id: str, request_id: str) -> dict[str, Any]:
    """Core async scan logic."""
    async with AsyncSessionLocal() as session:
        logger.info("security_scan_start", server_id=server_id, request_id=request_id)

        await sse_manager.publish(server_id, {
            "event": "scan_started",
            "server_id": server_id,
        })

        scanner = SecurityScanner(session)
        result = await scanner.scan(UUID(server_id))

        summary = {
            "server_id": server_id,
            "critical": result.critical_count,
            "high": result.high_count,
            "medium": result.medium_count,
            "info": result.info_count,
            "scan_duration_ms": result.scan_duration_ms,
        }

        await sse_manager.publish(server_id, {
            "event": "scan_completed",
            **summary,
        })

        if result.critical_count > 0:
            critical_findings = [
                {
                    "id": f["id"],
                    "title": f["title"],
                    "affected_tools": f.get("affected_tools", []),
                }
                for f in result.findings
                if f["severity"] == "critical"
            ]
            await sse_manager.publish(server_id, {
                "event": "scan_blocked",
                "server_id": server_id,
                "critical_findings": critical_findings,
            })

        logger.info(
            "security_scan_complete",
            server_id=server_id,
            request_id=request_id,
            **summary,
        )

        return summary


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.services.security_scanner.tasks.scan_server",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def scan_server(self: Task, server_id: str, request_id: str = "") -> dict[str, Any]:
    """Run a security scan on a server.

    Args:
        server_id: The UUID of the server to scan (as a string).
        request_id: Optional request correlation ID.

    Returns:
        A dict with scan summary (counts, duration).
    """
    return _loop.run_until_complete(_scan_async(server_id, request_id))
