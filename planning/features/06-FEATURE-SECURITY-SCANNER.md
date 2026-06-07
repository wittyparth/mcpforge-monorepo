# Feature 5 — Security Scanner

> **PRD reference:** § 7 Feature 5 (lines 427-471)
> **Build order:** Wave 1, Step 4 (ships before deploy gate)
> **Estimated effort:** 4-5 days for one engineer

---

## 0. TL;DR

Before every deployment, the Security Scanner runs 8+ deterministic rules against the server configuration and produces a color-coded report. Findings are categorized by severity: CRITICAL blocks deployment, HIGH can be overridden with acknowledgment, MEDIUM is a warning, INFO is a best practice. Results are stored, downloadable as JSON, and required for compliance.

The scanner runs as a Celery task triggered by `POST /api/v1/servers/{id}/deploy`. A scan completes in <2 seconds (deterministic analysis, no LLM). User sees results in a confirmation step before deploy proceeds.

---

## 1. Goals & Non-Goals

### 1.1 In scope
- 8 rules: SSRF URL params, no auth on DELETE, no auth on POST/PUT, credential in response, prompt injection in description, large tool set, untagged endpoints, deprecated HTTP methods
- 4 severity levels: CRITICAL, HIGH, MEDIUM, INFO
- Color-coded UI: red/orange/yellow/blue
- Findings: rule_id, severity, title, description, tool triggered, recommended fix, doc link
- Acknowledgment: user can add `# mcpforge:ignore FINDING_ID` annotation in tool description
- Pre-deployment gate: CRITICAL blocks deploy
- Post-deployment: re-run on demand
- JSON export for compliance
- Scan history: last 10 scans per server

### 1.2 Out of scope
- Live traffic analysis (v1.1)
- Dependency vulnerability scanning (v1.1)
- Custom rules by user (v1.1)
- Threat modeling report (v1.2)

---

## 2. Architecture

```
┌────────────────┐         ┌──────────────────┐
│  User clicks   │         │  Main API        │
│  "Deploy"      │────────►│  POST /servers/  │
│                │         │  {id}/deploy     │
└────────────────┘         └────────┬─────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │  Celery worker       │
                        │  (queue=scanner)     │
                        │                      │
                        │  scan_server()       │
                        │  ├─ for each rule:  │
                        │  │   run rule()      │
                        │  │   collect finding │
                        │  └─ write findings  │
                        │     to DB           │
                        └────────┬─────────────┘
                                 │
                                 ▼
                        ┌──────────────────────┐
                        │  Frontend polls or   │
                        │  SSE for scan result │
                        └──────────────────────┘
```

---

## 3. Backend Changes

### 3.1 New files

```
app/services/security_scanner/
├── __init__.py
├── scanner.py                 # Orchestrator (NEW)
├── rules.py                   # 8+ rule definitions (NEW)
├── tasks.py                   # Celery task (NEW)
└── models.py                  # Finding Pydantic models (NEW)

app/api/v1/endpoints/
└── security.py                # /servers/{id}/security/* (NEW)

app/schemas/
└── security.py                # ScanRequest, Finding, etc. (NEW)

tests/
├── test_security_rules.py     # 16 tests (2 per rule)
├── test_security_scanner.py   # 8 tests
└── test_security_endpoints.py # 6 tests
```

### 3.2 Migration `0004_add_security_scans.py`

```python
"""add security_scan_results and security_acknowledgments"""
def upgrade():
    op.create_table(
        "security_scan_results",
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column("server_id", sa.UUID, sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scan_status", sa.String(20), nullable=False),
        sa.Column("findings", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("critical_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("high_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("medium_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("info_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scanned_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("scan_duration_ms", sa.Integer, nullable=True),
    )
    op.create_index("idx_scan_results_server_scanned", "security_scan_results", ["server_id", "scanned_at"])
    
    op.create_table(
        "security_acknowledgments",
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column("server_id", sa.UUID, sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", sa.String(100), nullable=False),
        sa.Column("acknowledged_by", sa.UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.UniqueConstraint("server_id", "finding_id", name="uq_ack_server_finding"),
    )
```

### 3.3 The 8 rules

```python
# app/services/security_scanner/rules.py

RULES = [
    {
        "id": "SSRF_URL_PARAM",
        "severity": "CRITICAL",
        "title": "Tool accepts URL parameter (SSRF risk)",
        "description": "Tools that accept URL parameters and fetch them server-side can be exploited for SSRF attacks.",
        "check_function": "check_ssrf_url_param",
    },
    {
        "id": "NO_AUTH_DELETE",
        "severity": "CRITICAL",
        "title": "DELETE operation without authentication",
        "description": "Unauthenticated DELETE operations can result in unauthorized data deletion.",
        "check_function": "check_no_auth_delete",
    },
    {
        "id": "CREDENTIAL_IN_RESPONSE",
        "severity": "HIGH",
        "title": "Response may include sensitive credentials",
        "description": "Response schemas containing 'password', 'secret', 'token', 'key', or 'private_key' fields can leak credentials.",
        "check_function": "check_credential_in_response",
    },
    {
        "id": "PROMPT_INJECTION_DESC",
        "severity": "HIGH",
        "title": "Tool description may be vulnerable to prompt injection",
        "description": "Descriptions containing markdown links, HTML tags, or 'ignore previous instructions' patterns can be exploited.",
        "check_function": "check_prompt_injection_desc",
    },
    {
        "id": "NO_AUTH_WRITES",
        "severity": "HIGH",
        "title": "Write-capable tools without authentication",
        "description": "Servers with POST/PUT/PATCH tools but no auth scheme configured.",
        "check_function": "check_no_auth_writes",
    },
    {
        "id": "UNTAGGED_ENDPOINTS",
        "severity": "MEDIUM",
        "title": "Endpoints without tags",
        "description": "Untagged endpoints are harder to organize and may indicate incomplete spec.",
        "check_function": "check_untagged_endpoints",
    },
    {
        "id": "DEPRECATED_HTTP_METHODS",
        "severity": "MEDIUM",
        "title": "Deprecated HTTP methods",
        "description": "Tools using deprecated HTTP methods (TRACE, CONNECT).",
        "check_function": "check_deprecated_methods",
    },
    {
        "id": "LARGE_TOOL_SET",
        "severity": "INFO",
        "title": "Large tool set may produce unfocused server",
        "description": "Servers with 50+ tools may confuse LLMs. Consider selecting key tools.",
        "check_function": "check_large_tool_set",
    },
]

def check_ssrf_url_param(tools: list[dict]) -> list[Finding]:
    findings = []
    url_param_names = {"url", "endpoint", "uri", "target", "host", "href", "link", "src", "source"}
    for tool in tools:
        for param in tool.get("inputSchema", {}).get("properties", {}).items():
            if param[0].lower() in url_param_names and param[1].get("type") == "string":
                findings.append(Finding(
                    rule_id="SSRF_URL_PARAM",
                    severity="CRITICAL",
                    tool_name=tool["name"],
                    description=f"Parameter '{param[0]}' is a URL-like string. Could be exploited for SSRF.",
                    recommended_fix="Validate the URL is on an allowlist of approved hosts before fetching.",
                    doc_link="https://mcpforge.io/docs/security/ssrf",
                ))
    return findings

def check_no_auth_delete(tools: list[dict], auth_scheme: str) -> list[Finding]:
    if auth_scheme != "none":
        return []
    return [
        Finding(
            rule_id="NO_AUTH_DELETE",
            severity="CRITICAL",
            tool_name=t["name"],
            description=f"DELETE method on tool '{t['name']}' with no authentication configured.",
            recommended_fix="Add Bearer or API Key authentication before deploying destructive tools.",
        )
        for t in tools if t["method"] == "DELETE"
    ]

# ... 6 more rules following same pattern
```

### 3.4 Celery task

```python
@celery_app.task(name="app.services.security_scanner.tasks.scan_server", bind=True, max_retries=2)
def scan_server(self, server_id: str, request_id: str = ""):
    start = time.time()
    async def run():
        async with async_session_factory() as session:
            server = await MCPServerRepository(session).get_by_id(UUID(server_id))
            if not server:
                return
            
            tools = server.tools_config.get("tools", [])
            all_findings = []
            for rule in RULES:
                check_fn = globals()[rule["check_function"]]
                findings = check_fn(tools, server.auth_scheme)
                all_findings.extend(findings)
            
            # Apply acknowledgments
            acks = await SecurityAckRepository(session).get_for_server(UUID(server_id))
            acked_ids = {a.finding_id for a in acks}
            all_findings = [f for f in all_findings if f.rule_id not in acked_ids]
            
            # Persist
            counts = {"critical": 0, "high": 0, "medium": 0, "info": 0}
            for f in all_findings:
                counts[f.severity.value] += 1
            
            await SecurityScanRepository(session).create(
                server_id=UUID(server_id),
                scan_status="completed",
                findings=[f.model_dump() for f in all_findings],
                critical_count=counts["critical"],
                high_count=counts["high"],
                medium_count=counts["medium"],
                info_count=counts["info"],
                scan_duration_ms=int((time.time() - start) * 1000),
            )
            await session.commit()
            
            # Block deploy if critical
            if counts["critical"] > 0:
                await sse_manager.publish(server_id, {"event": "scan_blocked", "findings": [f.model_dump() for f in all_findings if f.severity == Severity.CRITICAL]})
            else:
                await sse_manager.publish(server_id, {"event": "scan_passed", "counts": counts})
    
    asyncio.run(run())
```

### 3.5 New endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/servers/{id}/security/scan` | Run a scan |
| GET | `/api/v1/servers/{id}/security/latest` | Get latest scan result |
| GET | `/api/v1/servers/{id}/security` | List scan history (paginated) |
| POST | `/api/v1/servers/{id}/security/{finding_id}/acknowledge` | Acknowledge a finding (suppress future) |
| DELETE | `/api/v1/servers/{id}/security/{finding_id}/acknowledge` | Remove acknowledgment |
| GET | `/api/v1/servers/{id}/security/report.json` | Download full report (JSON) |

### 3.6 Test plan

16+ tests covering each rule, plus integration tests:
- All 8 rules correctly identify known patterns
- All 8 rules correctly skip non-matching patterns
- Acknowledgments suppress future findings
- CRITICAL findings block deploy
- HIGH findings don't block (just warn)
- JSON export matches stored findings
- Scan history paginates correctly

---

## 4. Frontend Changes

### 4.1 New components

```
src/components/security/
├── security-scan-button.tsx         # Trigger a scan
├── security-findings-list.tsx       # List of findings
├── security-finding-card.tsx        # Single finding
├── severity-badge.tsx               # Color-coded (red/orange/yellow/blue)
├── scan-progress.tsx                # "Scanning..." state
└── security-report-export.tsx       # JSON download
```

### 4.2 New route

`/dashboard/servers/[slug]/security/page.tsx` — security dashboard

### 4.3 New hooks

```typescript
// src/hooks/use-security.ts (NEW)
export function useScan(serverId: string) { ... }
export function useLatestScan(serverId: string) { ... }
export function useAcknowledgeFinding(serverId: string) { ... }
export function useScanHistory(serverId: string) { ... }
```

---

## 5. Database / Migration Plan

Migration `0004_add_security_scans.py` (specified above).

---

## 6. Environment Variables

No new env vars.

---

## 7. Observability

```python
logger.info("security_scan_started", server_id=server_id, request_id=request_id)
logger.info("security_scan_completed", server_id=server_id, critical=counts["critical"], high=counts["high"], medium=counts["medium"], info=counts["info"], duration_ms=duration, request_id=request_id)
logger.warning("security_scan_critical_findings", server_id=server_id, findings=critical_findings_summary, request_id=request_id)
```

---

## 8. Edge Cases

| Case | Response |
|---|---|
| Server has no tools | Scan completes with 0 findings; status = passed |
| Acknowledgment refers to non-existent rule | Logged but ignored; rule still runs |
| User tries to deploy with CRITICAL findings | Return 409 with `error_code=BLOCKED_BY_SCANNER`, list of CRITICAL findings |
| Acknowledgment expires (v1.1 feature) | For v1.0, acknowledgments don't expire |
| User removes the `# mcpforge:ignore` comment from description | Acknowledgment still in DB; future scans honor it (user must explicitly remove ack) |

---

## 9. Definition of Done

- [ ] 8 rules implemented and tested
- [ ] Migration `0004_add_security_scans.py` created
- [ ] Celery task runs in scanner queue
- [ ] Deploy flow triggers scan first
- [ ] CRITICAL blocks deploy
- [ ] Acknowledgments work
- [ ] JSON export works
- [ ] Frontend security dashboard renders all findings
- [ ] Playwright E2E: deploy with CRITICAL is blocked

---

## 10. Build Sequence

1. Migration
2. Rules + scanner service
3. Celery task
4. Endpoints
5. Frontend components + route
6. Hooks
7. E2E tests
8. Manual: create server with DELETE method + no auth → try to deploy → blocked

---

*See `features/05-FEATURE-MCP-GATEWAY.md` for the deploy flow that triggers the scanner.*
