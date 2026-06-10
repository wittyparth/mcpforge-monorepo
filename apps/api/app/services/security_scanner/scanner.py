"""SecurityScanner orchestrator (F5).

Iterates all rules, collects findings, applies acknowledgments, persists result.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.security import SecurityScanResult
from app.repositories.mcp_server_repo import MCPServerRepository
from app.repositories.security_repo import SecurityAckRepository, SecurityScanRepository
from app.services.security_scanner.rules import RULES

logger = get_logger(__name__)


class SecurityScanner:
    """Orchestrates security scan execution.

    Iterates all rules, collects findings, applies acknowledgments, persists result.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.scan_repo = SecurityScanRepository(session)
        self.ack_repo = SecurityAckRepository(session)
        self.server_repo = MCPServerRepository(session)

    async def scan(self, server_id: UUID) -> SecurityScanResult:
        """Run all rules against the server's tools_config and persist results.

        Args:
            server_id: UUID of the server to scan.

        Returns:
            The persisted ``SecurityScanResult`` ORM model.

        Raises:
            NotFoundError: If the server does not exist.
        """
        start = time.time()

        # 1. Load server and extract tools
        server = await self.server_repo.get_by_id(server_id)
        if server is None:
            raise NotFoundError(f"Server {server_id} not found")

        tools: list[dict[str, Any]] = server.tools_config.get("tools", [])

        # 2. Run all rules
        all_findings: list[dict[str, Any]] = []
        for rule in RULES:
            if rule["requires_auth"]:
                findings = rule["check"](tools, server.auth_scheme)
            else:
                findings = rule["check"](tools)
            all_findings.extend(findings)

        # 3. Apply acknowledgments
        acks = await self.ack_repo.get_for_server(server_id)
        acked_ids: set[str] = {a.finding_id for a in acks}
        active_findings = [f for f in all_findings if f["id"] not in acked_ids]

        # 4. Count findings by severity
        critical_count = sum(1 for f in active_findings if f["severity"] == "critical")
        high_count = sum(1 for f in active_findings if f["severity"] == "high")
        medium_count = sum(1 for f in active_findings if f["severity"] == "medium")
        info_count = sum(1 for f in active_findings if f["severity"] == "info")

        scan_duration_ms = int((time.time() - start) * 1000)

        # 5. Persist scan result
        result = await self.scan_repo.create(
            server_id=server_id,
            scan_status="completed",
            findings=active_findings,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            info_count=info_count,
            scan_duration_ms=scan_duration_ms,
        )

        logger.info(
            "security_scan_completed",
            server_id=str(server_id),
            total_findings=len(active_findings),
            critical=critical_count,
            high=high_count,
            medium=medium_count,
            info=info_count,
            duration_ms=scan_duration_ms,
        )

        return result
