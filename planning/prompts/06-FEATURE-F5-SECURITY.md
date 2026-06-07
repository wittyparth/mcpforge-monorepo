# 06 — Feature 5: Security Scanner (Sequential in Integration Phase)

> **When to use:** After F1 lands. Can run in parallel with F2/F4/F7, but recommend running in integration phase so findings inform final design.
> **Produces:** A scanner that runs 8+ deterministic rules before deploy, with color-coded findings, blocking on CRITICAL.

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
4. .planning/09-INFRA-MIGRATIONS.md
5. AGENTS.md
6. .planning/features/06-FEATURE-SECURITY-SCANNER.md
7. apps/api/app/services/security_scanner/ (does NOT exist
   yet — you create)
8. The mcp_servers.tools_config shape from F1
9. apps/api/alembic/versions/0004_add_security_scans.py (from
   Skeleton — verify it exists)

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: F5 — Security Scanner
Feature plan: .planning/features/06-FEATURE-SECURITY-SCANNER.md
Build order: Run in integration phase (after F4) OR parallel Wave
              1 (with F2, F4, F7). Recommend integration phase
              so security findings can inform gateway F4.
Prerequisites: F1 must be merged. Migration 0004 must be applied.

═══════════════════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════════════════

D1. **app/services/security_scanner/rules.py**
    - 8 security rules per PRD § 7.5 and plan § 3.3:
      - SSRF_URL_PARAM (CRITICAL)
      - NO_AUTH_DELETE (CRITICAL)
      - CREDENTIAL_IN_RESPONSE (HIGH)
      - PROMPT_INJECTION_DESC (HIGH)
      - NO_AUTH_WRITES (HIGH)
      - UNTAGGED_ENDPOINTS (MEDIUM)
      - DEPRECATED_HTTP_METHODS (MEDIUM)
      - LARGE_TOOL_SET (INFO)
    - Each rule is a function: check_<rule_id>(tools,
      auth_scheme) -> list[Finding]
    - 16 tests (2 per rule: positive + negative)

D2. **app/services/security_scanner/scanner.py**
    - SecurityScanner class with scan(server_id) method
    - Iterates rules, collects findings
    - Applies acknowledgments from DB
    - Persists result with counts
    - 8 tests

D3. **app/services/security_scanner/tasks.py**
    - scan_server Celery task
    - 6 tests in eager mode

D4. **app/schemas/security.py**
    - Finding, FindingSeverity enum, ScanResultResponse
    - AcknowledgeRequest

D5. **app/api/v1/endpoints/security.py**
    - POST /api/v1/servers/{id}/security/scan
    - GET /api/v1/servers/{id}/security/latest
    - GET /api/v1/servers/{id}/security
    - POST /api/v1/servers/{id}/security/{finding_id}/acknowledge
    - DELETE /api/v1/servers/{id}/security/{finding_id}/acknowledge
    - GET /api/v1/servers/{id}/security/report.json
    - Replaces 501 stubs from Skeleton
    - 6 tests

D6. **app/repositories/security_repo.py**
    - SecurityScanRepository, SecurityAckRepository
    - CRUD methods

D7. **Frontend types:** Finding, FindingSeverity,
    ScanResultResponse
D8. **Frontend hooks** in `apps/web/src/hooks/use-security.ts`:
    useScan, useLatestScan, useAcknowledgeFinding,
    useScanHistory
D9. **Frontend components** in
    `apps/web/src/components/security/`:
    - security-scan-button.tsx
    - security-findings-list.tsx
    - security-finding-card.tsx
    - severity-badge.tsx (color-coded red/orange/yellow/blue)
    - scan-progress.tsx
    - security-report-export.tsx
D10. **Frontend route:**
    `/dashboard/servers/[slug]/security/page.tsx`
D11. **Wire into deploy flow:** When user clicks Deploy (F4
    will add this endpoint), trigger a scan first. CRITICAL
    findings block deploy.
D12. **Tests:** ≥30 backend, ≥5 Vitest, 1 Playwright
    (10-security-scan.spec.ts)

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE
═══════════════════════════════════════════════════════════════════════

1. Schemas (security.py)
2. Rules + 16 tests
3. Scanner service + 8 tests
4. Celery task + 6 tests
5. Repositories
6. Endpoints + 6 tests
7. Deploy integration (F4's deploy endpoint should call
   scanner first; coordinate with F4 agent if running
   parallel)
8. Frontend types + API + hooks
9. Frontend components
10. Frontend route
11. Vitest + Playwright
12. Full CI
13. Manual: deploy a server with DELETE method + no auth →
    try to deploy → blocked

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[All from master template] Plus F5-specific:
[ ] 8 rules implemented and tested (16 tests)
[ ] Migration 0004 applied
[ ] Celery task runs in scanner queue
[ ] CRITICAL findings block deploy (verify: 409 response)
[ ] Acknowledgments suppress future findings (verify: re-scan
    after ack shows the finding gone)
[ ] JSON export works
[ ] Frontend dashboard renders all 4 severity levels with
    correct colors
[ ] 30+ backend tests passing

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

[Standard format]
```

---

## Reviewer's checklist

1. **Test all 8 rules** with a malicious spec — each must trigger.
2. **Test deploy-blocking**: try to deploy a server with DELETE method + no auth — must 409.
3. **Test acknowledgment**: ack a finding, re-scan, verify it's gone.
4. **Performance**: scan completes in <2 seconds.
5. **No false positives**: scan a "clean" server (all GET, with auth, descriptions fine) — should return 0 CRITICAL/HIGH.
