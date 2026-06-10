"""Pydantic schemas for the Security Scanner (F5)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    """A single security finding from the scanner."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Stable finding ID, e.g., 'SSRF_URL_PARAM'")
    severity: Literal["critical", "high", "medium", "info"]
    title: str
    description: str
    affected_tools: list[str] = Field(default_factory=list)
    remediation: str
    references: list[str] = Field(default_factory=list, description="URLs to OWASP, CWE, etc.")


class ScanRequest(BaseModel):
    """POST /api/v1/servers/{id}/security/scan — kick off a scan."""

    force: bool = Field(default=False, description="Re-scan even if a recent result exists")


class ScanResultResponse(BaseModel):
    """Response for GET /api/v1/servers/{id}/security/latest."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    server_id: UUID
    scan_status: Literal["running", "completed", "failed"]
    findings: list[Finding]
    critical_count: int
    high_count: int
    medium_count: int
    info_count: int
    scanned_at: datetime
    scan_duration_ms: int | None


class AcknowledgeRequest(BaseModel):
    """POST /api/v1/servers/{id}/security/{finding_id}/acknowledge."""

    note: str | None = None


class AcknowledgeResponse(BaseModel):
    """Response for an acknowledge request."""

    server_id: UUID
    finding_id: str
    acknowledged_at: datetime


class FindingSeverity(str, Enum):
    """Severity levels for security findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    INFO = "info"


class ScanTriggerResponse(BaseModel):
    """Response when a security scan is initiated."""

    scan_id: UUID
    scan_status: str = "running"
    message: str = "Security scan initiated"


class ScanHistoryResponse(BaseModel):
    """Paginated list of scan results for a server."""

    items: list[ScanResultResponse]
    total: int
    page: int
    page_size: int
    next_page: int | None = None


class SecurityReport(BaseModel):
    """JSON export of a server's security posture."""

    model_config = ConfigDict(from_attributes=True)

    server_id: UUID
    server_name: str = ""
    generated_at: datetime
    scan: ScanResultResponse | None = None
    acknowledgments: list[AcknowledgeResponse] = Field(default_factory=list)
    summary: str = ""


class DeployBlockedResponse(BaseModel):
    """Response when a deploy is blocked due to critical security findings."""

    blocked: bool = True
    reason: str = "Security scan found CRITICAL findings"
    critical_findings: list[Finding] = Field(default_factory=list)
    scan_id: UUID | None = None
