# 02 — Wave 0 + Skeleton (Sequential, ~1 week)

> **When to use:** First agent. Sequential. Nothing else starts until this lands.
> **Produces:** Hardened auth, all interfaces locked, all routes stubbed, docker-compose for local dev, regenerated shared types.
> **Why this matters:** This agent's output is the contract that unblocks all 4 parallel feature agents. Quality here is the most leveraged.

---

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order, no skipping):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
   (focus on § 4 Wave 0 + § 5.1-5.7 cross-cutting concerns + § 11
   open questions)
4. .planning/09-INFRA-MIGRATIONS.md
5. AGENTS.md
6. apps/api/app/core/security.py (current bcrypt + JWT — you
   will REPLACE this)
7. apps/api/app/main.py (current FastAPI app factory — you
   will EXTEND this)
8. apps/api/app/api/deps.py (current auth dependencies — you
   will REPLACE get_current_user with locked version)
9. apps/api/alembic/versions/0001_initial.py (current
   migration — you'll add 8 more)

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Two deliverables, in order. A is "make it safe"; B is "lock the
contracts." Both must ship.

═══════════════════════════════════════════════════════════════════════
DELIVERABLE A — Wave 0 (security hardening)
═══════════════════════════════════════════════════════════════════════

From 00-MASTER-PLAN.md § 4 + § 5:

A1. **Argon2id migration.** Replace bcrypt in
    `apps/api/app/core/security.py` and
    `apps/api/app/services/auth_service.py` with
    passlib's `CryptContext(schemes=["argon2"], ...)`. Existing
    users' passwords need to be rehashed on next successful
    login (dual-verify: try argon2, fall back to bcrypt, on
    bcrypt success rehash and save). Add migration
    `009_password_argon2.py` if needed (or just a one-off
    script in `apps/api/scripts/rehash_passwords.py`).

A2. **HIBP check on register.** Add
    `apps/api/app/services/auth/hibp.py` that calls
    `https://api.pwnedpasswords.com/range/{sha1_prefix}` with
    k-anonymity. Integrate into `auth_service.register`. Reject
    breached passwords (return 422 with `error_code=
    PASSWORD_BREACHED`).

A3. **Account lockout.** Add
    `apps/api/app/services/auth/lockout.py` (Redis-backed).
    After 5 failed logins, lock for 15 minutes. Reset on
    successful login. Add to `auth_service.login`.

A4. **Refresh token rotation.** Modify
    `apps/api/app/core/security.py` `create_refresh_token` to
    include a `jti` claim (UUID v4). Add
    `apps/api/app/services/auth/token_rotation.py` that uses
    Redis to track used jtis. On `refresh`, check if jti is
    revoked; if yes (reuse detected), revoke ALL of the user's
    tokens and return 401.

A5. **CSRF protection.** Add
    `apps/api/app/core/middleware/csrf.py`. Use
    double-submit cookie pattern. Set `csrf_token` cookie on
    login. On state-changing requests (POST/PUT/PATCH/DELETE),
    require `X-CSRF-Token` header to match the cookie. Allow
    `/api/v1/auth/refresh` (it uses cookie auth, no body).
    Register in `app/main.py` BEFORE auth middleware.

A6. **Sentry init.** Add `sentry-sdk[fastapi]` to deps. In
    `app/main.py`, init Sentry if `SENTRY_DSN` is set. Sample
    rate 10% in prod, 100% in dev. Add `before_send` hook to
    strip `Authorization` and request bodies for credential
    routes.

A7. **Request ID middleware.** Add
    `apps/api/app/core/middleware/request_id.py`. Generate
    UUID v4 per request, store in `contextvars.ContextVar`,
    inject into `X-Request-ID` response header, propagate to
    all structlog log records in that request.

A8. **Sensitive log filter.** Add
    `apps/api/app/core/logging.py` `strip_sensitive_processor`.
    Strips any log field whose key contains
    `authorization`, `api_key`, `password`, `secret`, `token`,
    `cookie`, `bearer`. Also strips those substrings from
    string values recursively. Use JSON renderer in prod,
    console renderer in dev.

A9. **Gateway auth lock-down.** In
    `apps/api/app/api/deps.py`, replace `get_current_user` (or
    add `get_current_user_required`) that RAISES on
    unauthorized. Apply to ALL gateway routes:
    `app/gateway/mcp_server.py` and `app/playground/ws.py`.
    Currently these have NO auth. F4 will fully implement
    the gateway logic; you just add the auth check.

A10. **Health check polish.** Extend `GET /health` to also
    ping Celery worker (via `celery_app.control.ping()` with
    2s timeout). Return shape: `{"status": "ok", "version":
    "0.1.0", "db": "ok", "redis": "ok", "worker": "ok"|"down"}`.

A11. **Per-IP rate limit.** Add
    `apps/api/app/core/middleware/rate_limit.py`. 60 req/min
    per IP for general endpoints; 5 req/min for
    `/api/v1/auth/login` and `/api/v1/auth/register`. Use
    Redis token bucket.

A12. **docker-compose.yml at repo root.** Services:
    postgres:16-alpine (port 5432, healthcheck pg_isready),
    redis:7-alpine (port 6379, healthcheck redis-cli ping),
    api (builds from apps/api/Dockerfile, port 8000,
    depends_on healthy postgres + redis, runs
    `alembic upgrade head && uvicorn ...`),
    worker (same image, runs `celery -A app.core.celery_app
    worker -Q default -l info` — just stubs a "default" queue
    for now; AI/scanner/analytics queues come in their
    respective features). Add `healthcheck` to each.

A13. **Dockerfile.dev in apps/api/.** Multi-stage like the
    prod Dockerfile but installs dev deps (pytest, ruff,
    mypy). Mounts code as volume for live reload. CMD:
    `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.

A14. **Tests for all of the above.** 12+ new test files.
    Use `fakeredis` for Redis, `respx` for httpx. Total: ≥40
    new tests, all passing.

═══════════════════════════════════════════════════════════════════════
DELIVERABLE B — The Skeleton (THE contract for future agents)
═══════════════════════════════════════════════════════════════════════

This is the most important part of your work. After you finish,
every future feature agent will read your skeleton and code
against it without ambiguity.

B1. **8 new Alembic migrations** in `apps/api/alembic/versions/`,
    numbered 0002-0009 (existing is 0001). For each:
    - File: `NNNN_description.py` with both `upgrade()` and
      `downgrade()`.
    - Run `alembic upgrade head` (must succeed).
    - Run `alembic downgrade -1 && alembic upgrade head` (both
      must succeed on a fresh DB).
    - Migrations (per 09-INFRA-MIGRATIONS.md § 2):
      - 0002: mcp_servers AI fields
      - 0003: tool_calls (partitioned) + analytics rollups
      - 0004: security_scan_results + security_acknowledgments
      - 0005: teams + team_memberships + team_invitations +
              audit_logs + mcp_servers.team_id/owner_user_id
      - 0006: api_keys
      - 0007: subscriptions + invoices + users.stripe_customer_id
      - 0008: (skip if using Redis for refresh token rotation)
      - 0009: spec_sources (for F1)

B2. **All 14+ SQLAlchemy models** in `apps/api/app/models/`.
    - New files: `spec.py`, `tool_call.py`, `security.py`
      (scan results + acknowledgments), `team.py`
      (Team + TeamMembership + TeamInvitation),
      `audit_log.py`, `api_key.py`, `billing.py`
      (Subscription + Invoice), `tool_edit_history.py`
    - Update existing: `mcp_server.py` (add new fields),
      `user.py` (add stripe_customer_id, password_changed_at,
      last_login_at), `credential.py` (add rotated_by,
      last_used_at).
    - Update `app/models/__init__.py` to export ALL models.
    - Each model has full relationships, indexes, and a
      `__repr__` for debugging.

B3. **All Pydantic schemas** in `apps/api/app/schemas/`.
    Reference the request/response shapes from
    09-INFRA-MIGRATIONS.md § 7 API Surface table. New files
    for each domain:
    - `openapi_spec.py` (SpecFetchRequest,
      SpecUploadResponse, ToolDefinition, etc.)
    - `credential.py`
    - `tool.py`
    - `ai_description.py` (AIQualityScore, AIImprovementItem,
      AIEnhancedTool, BuildEvent, AIEnhancementRequest)
    - `gateway.py` (ConnectPanelResponse, TestConnectionResponse,
      PauseResponse, DeployRequest)
    - `playground.py` (PlaygroundSessionInfo,
      ShareTestRequest)
    - `security.py` (Finding, ScanResultResponse,
      AcknowledgeRequest)
    - `analytics.py` (AnalyticsOverview, ToolBreakdownItem,
      ErrorLogItem, TimeSeriesPoint, ClientBreakdownItem)
    - `team.py` (TeamCreate, TeamInvite, TeamMember,
      TeamMemberUpdate, AuditLogItem)
    - `api_key.py` (ApiKeyCreate, ApiKeyResponse)
    - `billing.py` (PlanInfo, SubscribeRequest, PortalResponse,
      WebhookEvent)

B4. **All route stub files** in
    `apps/api/app/api/v1/endpoints/`. Each is a FastAPI APIRouter
    with all endpoints declared but bodies return 501:
    ```python
    from fastapi import APIRouter
    from app.core.exceptions import NotImplementedFeatureError

    router = APIRouter(prefix="/specs", tags=["specs"])

    @router.post("/fetch", status_code=501)
    async def fetch_spec():
        raise NotImplementedFeatureError("OpenAPI Ingestion: pending F1")
    ```
    New files:
    - `specs.py` (5 endpoints)
    - `tools.py` (3 endpoints)
    - `credentials.py` (4 endpoints)
    - `build.py` (4 endpoints, including the SSE)
    - `security.py` (6 endpoints)
    - `analytics.py` (6 endpoints)
    - `team.py` (6 endpoints)
    - `api_keys.py` (3 endpoints)
    - `billing.py` (4 endpoints)
    - `gateway_admin.py` (deploy/pause/resume/connect)
    - Update `auth.py` (add forgot/reset/verify/github)

    `NotImplementedFeatureError` is a new AppError subclass
    that returns 501 with `{"error": {"code":
    "NOT_IMPLEMENTED"}}`. Define it in
    `app/core/exceptions.py`. The exception handler converts
    it to a proper JSON response.

B5. **Register all routes** in
    `apps/api/app/api/v1/router.py`. The router aggregates
    all v1 routers.

B6. **Update app/main.py** to include all routers. Add
    Sentry init, request_id middleware, CSRF middleware, rate
    limit middleware. Keep the existing `/health` and
    `/mcp/v1/{slug}/*` routes working.

B7. **Regenerate shared types.** Start the backend locally,
    then:
    ```
    cd packages/shared-types
    API_URL=http://localhost:8000 pnpm fetch
    pnpm generate
    ```
    The new `api-types.d.ts` should contain ALL endpoint
    operations. Run `pnpm type-check` in apps/web — must pass
    with no manual changes needed to the frontend (the
    skeleton doesn't break existing code).

B8. **Verify the CI suite** with the skeleton in place.
    `pnpm type-check && pnpm lint && pnpm test` all pass.

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE (follow IN ORDER)
═══════════════════════════════════════════════════════════════════════

Phase A — Foundations (2 days):
  1. Add deps: argon2-cffi, httpx (already), respx, freezegun,
     factory-boy, sentry-sdk[fastapi], aioboto3, openai>=1.50
  2. Create `app/core/encryption.py` (Fernet)
  3. Create `app/core/middleware/request_id.py`
  4. Create `app/core/logging.py` `strip_sensitive_processor`
     + JSON/console renderers
  5. Update `app/core/config.py` with new env vars
  6. Create `app/core/exceptions.py` add NotImplementedFeatureError
  7. Update `app/main.py` to wire Sentry, middlewares
  8. Update `app/core/security.py` Argon2id + jti

Phase B — Auth hardening (2 days):
  9. Create `app/services/auth/hibp.py` + tests
  10. Create `app/services/auth/lockout.py` + tests
  11. Create `app/services/auth/token_rotation.py` + tests
  12. Update `app/services/auth_service.py` to integrate HIBP,
      lockout, rotation
  13. Create `app/services/auth/password.py` for rehash-on-login
      + test
  14. Update `app/api/v1/endpoints/auth.py` for new flows

Phase C — Gateway auth + rate limit (1 day):
  15. Update `app/api/deps.py` with `get_current_user_required`
  16. Apply auth dependency to gateway + playground routes
  17. Create `app/core/middleware/csrf.py`
  18. Create `app/core/middleware/rate_limit.py`
  19. Update `app/main.py` to register middlewares
  20. Tests for all

Phase D — Docker (1 day):
  21. Create `docker-compose.yml` at repo root
  22. Create `apps/api/Dockerfile.dev`
  23. Test: `docker compose up` brings up stack
  24. `docker compose exec api alembic upgrade head` succeeds
  25. `curl http://localhost:8000/health` returns 200

Phase E — Skeleton (2 days):
  26. Create all 8 Alembic migrations (0002-0009)
  27. Run each migration up + down + up to verify
  28. Create all SQLAlchemy models
  29. Update `app/models/__init__.py` to export all
  30. Create all Pydantic schemas
  31. Create all route stub files with NotImplementedFeatureError
  32. Update `app/api/v1/router.py` and `app/main.py`
  33. Regenerate shared types
  34. Run full CI suite

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

Wave 0 (Deliverable A):
[ ] Passwords stored as Argon2id (verify by inspecting
    users.password_hash — starts with $argon2)
[ ] HIBP check on register (test: register with "password"
    — should reject with PASSWORD_BREACHED)
[ ] Account lockout after 5 failed logins (test: 6th
    login attempt returns 423 with retry-after)
[ ] Refresh token rotation in Redis (test: reuse old
    refresh token — all user sessions invalidated)
[ ] CSRF middleware applied (test: POST from different
    origin without X-CSRF-Token returns 403)
[ ] Sentry captures unhandled exceptions (test: trigger
    unhandled exception in a test endpoint — verify Sentry
    receives it)
[ ] No credentials in any log line (test: write a test that
    logs Authorization header, assert it's redacted in the
    output)
[ ] docker compose up brings up full stack with health
[ ] /health returns db:ok, redis:ok, worker:ok (or down
    gracefully if worker hasn't started)
[ ] All gateway routes require JWT auth

Skeleton (Deliverable B):
[ ] All 8 migrations exist, are reversible, apply to fresh DB
[ ] All 14+ models importable, no circular imports
[ ] All schemas importable, all examples in docstrings
[ ] All 50+ routes registered and return 501 with proper
    error shape
[ ] /openapi.json lists every endpoint
[ ] packages/shared-types/api-types.d.ts regenerated with
    all endpoints (run pnpm gen:api-types, verify ~2000+
    lines)
[ ] apps/web pnpm type-check passes without frontend
    changes (the skeleton is backward-compatible)
[ ] Backend pytest passes (all existing 17 tests still
    pass, plus all new ones)
[ ] pnpm lint passes
[ ] mypy --strict passes (no Any, no # type: ignore in new
    code)
[ ] ruff check passes

═══════════════════════════════════════════════════════════════════════
FINAL VERIFICATION
═══════════════════════════════════════════════════════════════════════

cd /Users/parthu/Coding/MCP/mcpforge-monorepo
pnpm type-check
pnpm lint
cd apps/api && uv run pytest --cov=app --cov-report=term-missing
cd apps/web && pnpm test
cd apps/api && uv run mypy app
cd apps/api && uv run ruff check app
docker compose up -d
sleep 5
curl http://localhost:8000/health
curl http://localhost:8000/openapi.json | head -100
docker compose down

All must pass. If anything fails, fix it.

═══════════════════════════════════════════════════════════════════════
REPORT BACK (use this exact format)
═══════════════════════════════════════════════════════════════════════

## Deliverable: Wave 0 + Skeleton
## Status: COMPLETE | PARTIAL | BLOCKED
## Wave 0:
- Argon2id: yes/no
- HIBP: yes/no
- Lockout: yes/no
- Token rotation: yes/no
- CSRF: yes/no
- Sentry: yes/no
- Request ID: yes/no
- Sensitive log filter: yes/no
- Gateway auth: yes/no
- Rate limit: yes/no
- Docker: yes/no
## Skeleton:
- Migrations: 8/8 applied
- Models: <N> total
- Schemas: <N> files
- Route stubs: <N> endpoints
- Shared types regenerated: yes/no
- /openapi.json endpoints: <N>
## Files created: <list>
## Files modified: <list>
## Tests: <N> passing, 0 failing
## Definition of Done: <X>/<Y> items checked
## Open issues / follow-ups:
- <list, or "none">
## Ready for next phase: yes/no

If PARTIAL or BLOCKED, explain why. Do NOT claim complete
if Wave 0 has TODOs or Skeleton has missing route stubs.
```

---

## Reviewer's checklist (you, after the agent finishes)

Before unblocking the next phase, verify:

1. **Skeleton completeness:** open `/openapi.json` and count paths. Should be 50+ paths.
2. **Schema quality:** open `packages/shared-types/api-types.d.ts`. Should be 2000+ lines.
3. **Auth hardened:** try logging in with a known breached password. Should fail.
4. **CSRF:** try a POST from `evil.com` without the CSRF token. Should 403.
5. **All migrations apply:** `alembic upgrade head` on a fresh DB succeeds.
6. **Test coverage:** `pytest --cov=app` should show ≥60% coverage overall.
7. **No regressions:** all Phase 1 tests still pass.

If any of these fail, do NOT proceed to F1. Send the agent back.
