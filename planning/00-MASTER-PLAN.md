# 00 — MCPForge Master Plan

> **For AI agents:** This is the source of truth for HOW we build MCPForge v1.0. Read `CURRENT-STATE.md` first to know where the code lives, then come here for architecture, principles, and build order. Read your specific feature plan (`features/NN-FEATURE-*.md`) for step-by-step instructions.

---

## 0. TL;DR

MCPForge is a hosted, AI-augmented OpenAPI → MCP server platform. Seven v1.0 features split into four waves. Each feature ships alone, behind feature flags, with full tests, before the next begins. We optimize for **production-grade correctness** over feature breadth. No stubs, no `pass` statements, no half-built UI. Every dependency, every endpoint, every error path is real.

**Core moat:** the AI Description Engine. Zero competitors do it well. arxiv 2602.18914 proves 260% selection lift. This is what we sell.

**Target:** 2,000 registered users, 500 active deployed servers, 50K tool calls in 60 days.

---

## 1. Non-Negotiable Principles

These are the rules every PR must satisfy. If a change violates one, it does not merge.

### 1.1 Quality

1. **No stubs in shipped code.** Every endpoint, every model field, every UI state has real production logic. `TODO`, `pass`, `NotImplementedError`, and "coming soon" pages are forbidden on `main`.
2. **Strict typing everywhere.** Python: mypy strict, no `Any`. TypeScript: TS strict + `noUncheckedIndexedAccess`, no `any` / `@ts-ignore` / `@ts-expect-error`. New packages must type 100% of public surface.
3. **Every external call is wrapped** with timeout, retry, structured logging, and a typed exception. `httpx`, `openai` (used for all LLM providers via OpenAI-compatible protocol), `prance`, `mcp` SDK — all wrapped.
4. **Errors are typed.** `AppError` subclasses map to HTTP status via the global exception handler. New error categories require new `AppError` subclasses and explicit handler tests.
5. **Every new service has tests.** Minimum: 1 happy + 2 edge cases + 1 error case. Tests live in the same package, mirror the source tree.
6. **Every new endpoint has OpenAPI documentation** (Pydantic gives this free) **and a manual test path** in the corresponding `test_*.py`.

### 1.2 Privacy & Security

1. **No parameter values stored anywhere.** Analytics records parameter *names*; never *values*. Tool call logs sanitize bodies. Error messages redact credentials.
2. **Credentials are encrypted at rest.** AES-256-GCM via `cryptography.fernet` (master key from env). PRD mentions AWS KMS; for free-tier deployment, Fernet is acceptable with documented upgrade path.
3. **Credentials are decrypted only inside the gateway** at request time. The main API never holds plaintext credentials.
4. **No credentials in logs, ever.** `structlog` processor strips `Authorization`, `api_key`, `bearer`, `password`, `secret` from any log record before emission.
5. **httpOnly + Secure + SameSite cookies for all auth tokens.** No localStorage. No `Authorization` header storage in JS.
6. **SSRF blocklist in the gateway.** Outbound requests to `10.x`, `172.16.x`, `192.168.x`, `169.254.x` (AWS metadata), `127.x` are blocked at the gateway level. The user-facing API is never a proxy for arbitrary URLs.
7. **CSRF protection** for cookie-based auth (double-submit cookie or `Origin` header check). Required because we use `SameSite=none` in production for cross-origin AI tool clients.

### 1.3 Cost & Performance

1. **AI calls use prompt caching.** The OpenAPI spec prefix is cached; cache reads cost 10% of base input. Estimated 80% cost reduction for the AI Engine.
2. **Rate limits per server.** Free: 500 calls/month, burst 60/hour. Pro: 10K/month, burst 1K/hour. Team: 100K/month, burst 10K/hour. Limit enforcement in Redis token bucket.
3. **Gateway latency budget.** P50 overhead < 100ms, P95 < 250ms (PRD § 9.3). The gateway caches server config in Redis (5-min TTL, invalidate on update) so DB hits are amortized.
4. **Background work is async.** Spec parsing, AI description generation, security scans, analytics aggregation all run in Celery workers. The request thread never blocks on AI.
5. **Structured logging in JSON for prod, colored for dev.** Every log record has `request_id`, `user_id`, `server_id` where applicable. Tracing via OpenTelemetry (Phase 1.1, stub the API now).

### 1.4 Code Organization

1. **Routes = HTTP plumbing only.** No business logic in route handlers. Logic goes in services.
2. **Services = business logic only.** No raw SQL or Pydantic-in-Pydantic-out logic. Repos handle DB.
3. **Repositories = DB queries only.** Return ORM models or `None`. No business decisions.
4. **Pydantic schemas are the only thing that crosses layer boundaries.** ORM models never leave the service layer. Service responses are Pydantic. Routes serialize Pydantic.
5. **Async everywhere.** No sync DB calls. No sync HTTP. No `time.sleep`. Use `asyncio.sleep`, `httpx.AsyncClient`, `redis.asyncio`.
6. **One feature per PR** (generally). Easier to review, revert, trace.

### 1.5 Testing

1. **Unit tests live next to the code they test** (`tests/test_<module>.py`).
2. **Integration tests** for service+repo combinations.
3. **E2E tests with Playwright** for the top 3 user flows: register→create server→playground; build server with AI enhancement; deploy and call from external MCP client.
4. **Test fixtures are in `conftest.py`**, not scattered. New fixtures are added to `conftest.py`, not inlined.
5. **CI gates**: lint + type-check + tests must pass before merge. No exceptions.

### 1.6 Documentation

1. **Every feature plan has a "Definition of Done" section** with checkable items.
2. **Every endpoint has a docstring** explaining its purpose, request, response, errors, and rate limit.
3. **Every service method has a docstring** explaining what it does, what it returns, and what errors it raises.
4. **Public API responses never break** without a major version bump.

---

## 2. Architecture

### 2.1 System Overview

```
                    ┌─────────────────────────────────────────────────────┐
                    │              Browser (apps/web, Next.js 15)            │
                    │   Landing │ Auth │ Builder │ Playground │ Analytics    │
                    │   Dashboard │ Server Settings │ Team │ Billing         │
                    └──────────────────────┬──────────────────────────────────┘
                                           │ HTTPS, credentials: include
                    ┌──────────────────────▼──────────────────────────────────┐
                    │      Edge: Render/Cloudflare (TLS, rate limit)           │
                    └──────┬───────────────────────────────┬──────────────────┘
                           │                               │
              ┌────────────▼──────────┐      ┌─────────────▼──────────────┐
              │   Main API (FastAPI)  │      │   MCP Gateway (FastAPI)    │
              │   :8000                │      │   :8001 (or same process)  │
              │   • auth, users        │      │   • /mcp/v1/{slug}/sse     │
              │   • servers CRUD       │      │   • /mcp/v1/{slug}/        │
              │   • tools CRUD         │      │   • tools/list, tools/call │
              │   • analytics queries  │      │   • credential decryption  │
              │   • team, billing      │      │   • SSRF guard             │
              │   • spec ingest        │      │   • rate limit (Redis)     │
              │   • SSE build progress │      │   • structured logging     │
              └────────────┬──────────┘      └─────────────┬──────────────┘
                           │                               │
              ┌────────────▼──────────┐      ┌─────────────▼──────────────┐
              │   Celery workers      │      │   Anthropic Claude API     │
              │   (3 queues)          │      │   (claude-sonnet-4-6)      │
              │   • ai (F2)            │      └────────────────────────────┘
              │   • scanner (F5)       │
              │   • analytics (F6)    │
              └────────────┬──────────┘
                           │
              ┌────────────▼────────────────────────────────────────────────┐
              │   PostgreSQL 16 (Neon free tier)                              │
              │   • users, mcp_servers, credentials, server_versions         │
              │   • tool_calls (partitioned by day, F6)                      │
              │   • teams, team_memberships, audit_logs, api_keys (F7)       │
              │   • ai_enhancement_jobs (F2), security_scan_results (F5)     │
              └───────────────────────────────────────────────────────────────┘
                           │
              ┌────────────▼────────────────────────────────────────────────┐
              │   Redis 7 (Upstash free tier)                                 │
              │   • Celery broker + result backend                            │
              │   • Rate limit counters (token bucket per server)             │
              │   • Server config cache (5-min TTL)                           │
              │   • SSE session map + playground ephemeral state              │
              │   • Refresh token rotation tracking                           │
              └───────────────────────────────────────────────────────────────┘
                           │
              ┌────────────▼────────────────────────────────────────────────┐
              │   Cloudflare R2 (S3-compatible, 10GB free tier)              │
              │   • OpenAPI spec files (uploaded)                             │
              │   • Security report exports (JSON)                            │
              │   • Audit log archives (>90 days)                             │
              └───────────────────────────────────────────────────────────────┘
```

### 2.2 Service Boundaries (the "consolidated services" decision)

PRD § 9.1 originally proposed 3 services (main API, gateway, playground). For free-tier cost efficiency, we run them as **logical modules in a single FastAPI process** at first, with clear internal boundaries so they can be split later:

- `app/api/v1/` — Main API routes (port 8000)
- `app/gateway/` — Gateway routes (`/mcp/v1/{slug}/...`), mounted in same process
- `app/playground/` — WebSocket playground routes (`/ws/playground/...`), mounted in same process

When traffic justifies (PRD mentions 8-20 gateway replicas at prod scale), we split into 3 Render services.

**Why this matters:** The internal modules must not import each other across module boundaries. Gateway code cannot import from `app.api`. They share `app.core` and `app.services`.

### 2.3 Process Topology (in this repo) — **what we actually deploy**

This matches the existing `render.yaml` and `Dockerfile` in the repo. We do NOT deploy to AWS ECS / Fargate / RDS / ElastiCache. Those are the PRD's hypothetical production architecture — for v1.0 free tier, the entire backend runs on a single Render Docker service with Neon + Upstash as managed services.

```
uvicorn (single Render Docker process)
├── app.main:app                 ← FastAPI app factory
│   ├── /api/v1/*               ← Main API router
│   ├── /mcp/v1/{slug}/*        ← Gateway router
│   ├── /ws/playground/{slug}   ← Playground WebSocket
│   └── /health, /api/v1/.../health

celery worker (separate Render Docker service, free tier)
├── queue=ai                    ← F2 AI Description Engine
├── queue=scanner               ← F5 Security Scanner
└── queue=analytics             ← F6 Analytics aggregation

celery beat (separate process, F6+)
└── schedules analytics_aggregate every 5 minutes
```

### 2.4 Data Flow for a User Building a Server

```
1. User pastes OpenAPI URL → POST /api/v1/specs/fetch
   → spec_ingestion service fetches URL, validates
   → returns parsed spec + extracted tool list
2. User reviews tools, selects subset → PUT /api/v1/servers/{id}/tools
   → mcp_servers.tools_config updated
   → server_version row inserted
3. User clicks "Build Server" → POST /api/v1/servers/{id}/build
   → mcp_servers.status = "building"
   → Celery task enqueued: enhance_all_descriptions
   → returns job_id
4. Frontend opens SSE: GET /api/v1/servers/{id}/build-status
   → Server streams progress events
5. Celery worker (queue=ai)
   → for each tool: call LLM provider (OpenAI-compatible) with prompt template + cache spec prefix
   → parse response, score quality on 4 dimensions
   → write back to mcp_servers.tools_config
   → emit SSE event "tool_enhanced"
6. When all done: server.status = "review"
7. User reviews enhanced descriptions in UI
8. User clicks "Deploy" → POST /api/v1/servers/{id}/deploy
   → security_scanner task enqueued
   → Celery worker (queue=scanner) runs scan
   → results emitted via SSE
9. If scan OK: server.status = "active"
   → Gateway cache invalidated for this slug
   → Now reachable at https://mcpforge.io/mcp/v1/{slug}
```

### 2.5 Data Flow for a Tool Call (post-deployment)

```
MCP client → GET /mcp/v1/{slug}/sse
           → POST /mcp/v1/{slug}/message {"jsonrpc":"2.0","method":"tools/call",...}
           
Gateway:
  1. Check rate limit (Redis) → if exceeded, return -32000 (RateLimitExceeded)
  2. Look up server config (Redis cache, fallback DB) → if not found, 404
  3. Validate arguments against tool.inputSchema → if invalid, -32602
  4. Decrypt credentials (Fernet) → never logged
  5. Build HTTP request: method + base_url + path + headers + body
  6. SSRF check on resolved IP → if internal, -32000 (UpstreamError)
  7. Execute via httpx.AsyncClient with 5s timeout, retry once on 429
  8. Truncate response if > 100KB, base64-encode binaries, strip HTML
  9. Async-fire analytics event to Celery (no await)
  10. Format as MCP JSON-RPC result
  11. Return via SSE
```

---

## 3. Tech Stack Decisions (locked)

### 3.1 Backend
| Concern | Choice | Why (and what we explicitly chose NOT to use) |
|---|---|---|
| Web framework | FastAPI 0.115+ | Async, OpenAPI docs for free, type-driven. NOT Django (too heavy, not async-first). |
| ORM | SQLAlchemy 2.0 async | Existing. NOT Tortoise ORM (less mature, fewer migrations tools). |
| Migrations | Alembic 1.14+ | Existing, async-compatible via env.py. NOT Prisma (JS-only). |
| Validation | Pydantic v2 | Existing. NOT dataclasses (no validation). |
| Database | PostgreSQL 16 (Neon free tier) | JSONB for tools_config, partitioning for tool_calls. NOT MongoDB (relational for users/teams). |
| Cache/queue | Redis 7 (Upstash free tier) | Existing. NOT Memcached (no pub/sub for Celery). |
| Async jobs | **Celery 5.4+** (NEW) | Mature, monitoring (Flower), priority queues, rate limit. NOT RQ (no priorities), NOT ARQ (async-only, less ecosystem), NOT Dramatiq (smaller community). |
| LLM client | **openai 1.50+ (AsyncOpenAI) + base_url** (NEW) | OpenAI-compatible protocol works with DeepSeek, OpenAI, Anthropic (via proxy), OpenCode Go, OpenRouter, custom. Switch model/base_url via .env. Primary: `deepseek-v4-flash` on `https://api.deepseek.com/v1`. |
| OpenAPI parsing | **openapi-spec-validator 0.9+ + prance 25+** (NEW) | Standard combination. NOT openapi-core (overkill, we don't need request validation). |
| MCP SDK | **`mcp` Python SDK 1.x** (NEW) | Official, used by FastMCP. NOT raw protocol (reinvents the wheel). |
| Credentials encryption | **`cryptography[fernet]` 44+** (NEW) | Symmetric AES-128-CBC + HMAC, simple key management. NOT AWS KMS (free-tier compatible alternative, with documented upgrade). |
| Auth | JWT (HS256) in httpOnly cookies | Existing. Migrate to **Argon2id** for password hashing (per PRD § 13). |
| HTTP client | httpx 0.28+ | Existing. Used both for spec fetch and gateway outbound calls. |
| Logging | structlog 24+ | Existing, JSON in prod. |
| Email | **Resend** (NEW) or **SendGrid** | Resend has the best DX for transactional. Phase 1.1; for v1.0, email verification is "console link" for the demo. |
| Error tracking | **Sentry** (NEW) | Per PRD § 12. Use `sentry-sdk[fastapi]`. |
| Testing | pytest 8.3 + pytest-asyncio + httpx | Existing. Add `factory-boy` for fixtures if needed. |
| Linting | ruff 0.8 + mypy 1.13 strict | Existing. |
| API docs | Pydantic → OpenAPI → Swagger UI | Free with FastAPI. |

### 3.2 Frontend
| Concern | Choice | Why |
|---|---|---|
| Framework | Next.js 15 App Router | Existing. Server Components for SSR data, client components for interactivity. |
| UI primitives | shadcn/ui (15 components installed, will add more) | Existing. NOT Material UI (heavy). NOT Mantine (limited customization). |
| Styling | Tailwind v4 + CSS variables | Existing. Light/dark themes already configured. |
| Server state | TanStack Query v5 | Existing. Best-in-class for caching/invalidation. |
| Client state | Zustand v5 | Existing. Only for ephemeral UI state (e.g., auth gate isLoaded flag). |
| Forms | react-hook-form 7 + Zod 3 | Existing. Type-safe, performant. |
| Code editor | **Monaco Editor** (NEW, via `@monaco-editor/react`) | For tool description editor (F1, F2) and JSON response viewer (F3). |
| Resizable panels | **react-resizable-panels** (NEW) | For description side-by-side editor (F2) and 4-panel playground (F3). |
| Tabs | **@radix-ui/react-tabs** (NEW) | Server detail page tabs (F1, F2, F3, F6). |
| Scroll area | **@radix-ui/react-scroll-area** (NEW) | Long tool lists (F1, F2). |
| Switch | **@radix-ui/react-switch** (NEW) | Server enable/disable (F4). |
| Markdown | **react-markdown** + **remark-gfm** (NEW) | Render tool descriptions in playground (F3). |
| Charts | **Recharts** (NEW) | Analytics dashboard (F6). Best React-native option. |
| Date | **date-fns** (NEW) | Format timestamps in analytics. |
| Toasts | sonner 1.7+ | Existing. |
| Testing | **Vitest** + **@testing-library/react** + **Playwright** (NEW) | Vitest for components, Playwright for E2E. |

### 3.3 Infrastructure
| Concern | Choice | Why |
|---|---|---|
| API hosting | Render free tier (Oregon) | Existing, free, Docker, sleeps after 15min — acceptable for v1.0. Upgrade to paid when traffic justifies. |
| Web hosting | Vercel | Existing, free, Next.js-native. |
| DB | Neon free tier | Existing, free, scales to zero. |
| Cache/queue | Upstash free tier | Existing, free, 10K commands/day. |
| CI/CD | GitHub Actions | Existing. 3-job CI + 2-job deploy. |
| Container | Docker (multi-stage, uv-based) | Existing. |
| Object storage | **Cloudflare R2** (free tier: 10GB/mo, no egress) | Replaces AWS S3 for free tier. R2 has S3-compatible API. PRD mentions S3; R2 is the cost-effective choice. |
| DNS | Cloudflare (free) | Already using CF for R2 + potential future Workers. |
| CDN | Cloudflare | Free, global. |
| Error tracking | **Sentry** (free tier: 5K events/mo) | Per PRD. |
| Email | **Resend** (free tier: 100 emails/day) | For Phase 1.1 email verification. |

### 3.4 New Python Dependencies to Add

Add to `apps/api/pyproject.toml` [project.dependencies]:
```toml
"openai>=1.50.0",  # OpenAI-compatible client; works with DeepSeek, OpenAI, OpenCode Go, OpenRouter, etc.
"openapi-spec-validator>=0.9.0",
"prance>=25.0.0",
"cryptography>=44.0.0",
"mcp>=1.0.0",
"celery[redis]>=5.4.0",
"sentry-sdk[fastapi]>=2.0.0",
"resend>=2.0.0",  # for Phase 1.1 email; safe to install now
"tenacity>=9.0.0",  # for retry helpers
```

Add to `[project.optional-dependencies.dev]`:
```toml
"factory-boy>=3.3.0",  # for test fixtures
"freezegun>=1.5.0",  # for time-sensitive tests
"respx>=0.22.0",  # for mocking httpx
```

### 3.5 New TypeScript Dependencies to Add

Add to `apps/web/package.json`:
```json
{
  "dependencies": {
    "monaco-editor": "^0.52.0",
    "@monaco-editor/react": "^4.6.0",
    "react-resizable-panels": "^2.1.0",
    "@radix-ui/react-tabs": "^1.1.0",
    "@radix-ui/react-scroll-area": "^1.2.0",
    "@radix-ui/react-switch": "^1.1.0",
    "@radix-ui/react-collapsible": "^1.1.0",
    "@radix-ui/react-toggle-group": "^1.1.0",
    "recharts": "^2.15.0",
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "date-fns": "^4.1.0"
  },
  "devDependencies": {
    "vitest": "^2.1.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/user-event": "^14.5.0",
    "jsdom": "^25.0.0",
    "@playwright/test": "^1.49.0"
  }
}
```

---

## 4. Build Order (4 Waves)

Each wave is independent, ships to production behind a feature flag if needed, and is fully tested. No wave is "started" until the prior wave's Definition of Done is met.

### Wave 0 — Foundation Hardening (1 week)
**Why first:** all features depend on these. Quick wins.

1. **Email/password hardening** (Argon2id, HIBP check, account lockout) — see F7 § 4.1, but pull the password bits forward
2. **Refresh token rotation tracking** in Redis (jti claim + blacklist) — see F7 § 4.2
3. **CSRF protection** middleware — see F7 § 4.3
4. **Sentry integration** — wrap FastAPI app with Sentry SDK
5. **Gateway authentication** — JWT check on `/mcp/v1/{slug}/*` and `/ws/playground/{slug}*` (currently NONE)
6. **Health check granularity** — already have `/health` returning DB+Redis; add per-service health
7. **Production logging** — JSON formatter, request_id middleware, no-credentials processor
8. **`docker-compose.yml`** for local dev — Postgres + Redis services

**DoD:**
- [ ] Passwords stored as Argon2id
- [ ] Refresh token rotation invalidated on reuse
- [ ] CSRF token required for all POST/PATCH/DELETE in cookie auth
- [ ] Sentry captures all unhandled exceptions
- [ ] Gateway requires JWT (cookie or header) for all `/mcp/v1/...` routes
- [ ] `docker compose up` brings up Postgres + Redis + API + Celery worker
- [ ] No credentials in any log line (verified by integration test)

### Wave 1 — Core MCP Loop (3 weeks)
**Why second:** the product doesn't exist without these.

1. **Feature 1: OpenAPI Spec Ingestion** — F1 plan
2. **Feature 4: Hosted MCP Gateway** (real impl, not echo) — F4 plan
3. **Feature 2: AI Description Engine** — F2 plan
4. **Feature 5: Security Scanner** — F5 plan (must ship before deploy is allowed)

**DoD for Wave 1:**
- [ ] User can paste OpenAPI URL, get a working MCP server endpoint
- [ ] AI descriptions improve tool quality scores (target average +30 points)
- [ ] Gateway has SSRF protection, rate limiting, credential encryption
- [ ] Security scanner blocks CRITICAL findings
- [ ] End-to-end: register → fetch spec → AI enhance → deploy → call from Claude Desktop

### Wave 2 — Iteration & Insights (2 weeks)
1. **Feature 3: Browser MCP Playground** — F3 plan
2. **Feature 6: Usage Analytics Dashboard** — F6 plan
3. **Description performance tracking** (F6 § 5) — when user edits a description, the next 7 days of call-rate delta is shown

**DoD for Wave 2:**
- [ ] User can call any tool from browser without Claude Desktop
- [ ] Analytics dashboard shows: total calls, per-tool breakdown, error log, client breakdown, time series
- [ ] Description edits track call-rate changes
- [ ] No parameter values ever appear in analytics

### Wave 3 — Monetization & Teams (2 weeks)
1. **Feature 7: Auth, Teams, Server Management** — F7 plan
2. **Stripe billing** (Pro $12/mo, Team $29/seat/mo) — see F7 § 4.7
3. **API Keys for programmatic access** — F7 § 4.6
4. **Registry submission automation** (Smithery, Glama) — PRD § 16

**DoD for Wave 3 (v1.0 launch):**
- [ ] All PRD § 7 acceptance criteria met
- [ ] Pro and Team plans functional
- [ ] Free tier enforces 500 calls/month, 2 servers
- [ ] Teams can invite, change roles, remove
- [ ] API keys with scopes work
- [ ] Description version history with rollback
- [ ] 2,000 registered users, 500 active servers, 50K tool calls in 60 days

---

## 5. Cross-Feature Concerns (must be designed once, used everywhere)

### 5.1 Request ID

Every request gets a UUID v4 `request_id` (HTTP middleware). It's:
- Stored in `contextvars` for the request lifetime
- Injected into every log line
- Returned in the `X-Request-ID` response header
- Passed to Celery tasks (so async work is traceable)

### 5.2 Error Response Shape

All API errors return:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email is required",
    "field": "email",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

`AppError` subclasses set `code` and `message`; `request_id` is added by middleware.

MCP gateway errors follow the JSON-RPC error format:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Rate limit exceeded for this server",
    "data": {"retry_after_seconds": 60}
  }
}
```

### 5.3 Pagination

All list endpoints use cursor-based pagination (PRD's `PaginatedResponse` already exists):
```json
{
  "items": [...],
  "total": 137,
  "page": 1,
  "page_size": 20,
  "next_page": 2  // null if last
}
```

For analytics time-series, use date-range pagination: `?from=2026-06-01&to=2026-06-07`.

### 5.4 Rate Limiting

Three scopes, all Redis-backed token bucket:
1. **Per-IP** (main API): 60 req/min burst, 1000 req/hr sustained. Protects auth endpoints.
2. **Per-user** (main API): 1000 req/hr, 10K req/day. Pro/Team higher.
3. **Per-server** (gateway): based on plan. Free 500/mo, Pro 10K/mo, Team 100K/mo. Per-hour burst limit too.

Implementation: `slowapi` library or custom middleware. Custom is preferred (we need plan-aware limits).

### 5.5 Caching Strategy

| Data | Cache | TTL | Invalidation |
|---|---|---|---|
| Server config (gateway lookup) | Redis | 5 min | On server PATCH, manual `cache_del(server:slug:{slug})` |
| User profile | Redis | 1 min | On user update |
| OpenAPI spec (parsed) | None (re-fetch) | n/a | n/a — we don't cache external resources |
| AI description | mcp_servers.tools_config (DB) | n/a | n/a |
| Tool call aggregate counts | mcp_servers.total_calls, monthly_calls | n/a | atomic UPDATE on every call |

### 5.6 Secrets Management

For free tier, secrets live in env vars (Render dashboard):
- `JWT_SECRET` — auto-generated by Render
- `ENCRYPTION_KEY` — Fernet master key, manually generated, set in Render dashboard
- `LLM_API_KEY` — set in Render dashboard (provider-specific; primary = DeepSeek key)
- `DATABASE_URL`, `REDIS_URL` — set in Render dashboard
- `SENTRY_DSN` — set in Render dashboard

For prod (paid tier), move to Doppler (https://doppler.com) or similar. Documented as a Phase 1.1 task.

### 5.7 Observability

For v1.0:
- **Logs**: structlog JSON, request_id correlation, sent to stdout (Render captures)
- **Errors**: Sentry with environment tag, release tag from git SHA
- **Metrics**: not in v1.0 (Phase 1.1 Prometheus)
- **Tracing**: not in v1.0 (Phase 1.1 OpenTelemetry)

This is the "good enough" set for the launch. Expansion is planned.

---

## 6. Database Schema Evolution

### 6.1 Current schema (0001_initial.py)

Tables: `users`, `mcp_servers`, `credentials`, `server_versions`. See `CURRENT-STATE.md` for field-level detail.

### 6.2 New tables to add

| Migration | Tables | Adds | Wave |
|---|---|---|---|
| `0002_add_ai_enhancement.py` | `mcp_servers` (alter) | `description_review_status`, `last_ai_run_at` | Wave 1 (F2) |
| `0003_add_tool_calls.py` | `tool_calls` (partitioned), indexes | `tool_calls` table + partitions for next 30 days | Wave 2 (F6) |
| `0004_add_security_scans.py` | `security_scan_results` | `security_scan_results` table | Wave 1 (F5) |
| `0005_add_teams.py` | `teams`, `team_memberships`, `audit_logs` | Team tables + audit log | Wave 3 (F7) |
| `0006_add_api_keys.py` | `api_keys` | API key table | Wave 3 (F7) |
| `0007_add_billing.py` | `subscriptions`, `invoices` | Stripe billing | Wave 3 (F7) |
| `0008_add_refresh_token_tracking.py` | `mcp_servers` (alter) + `revoked_tokens` | Token rotation tracking | Wave 0 |

### 6.3 Backwards compatibility

All migrations must be reversible. The `alembic` autogenerate gets us 80% there, but review for:
- Adding `NOT NULL` columns → use nullable or with default
- Dropping columns → rename first, drop in later migration
- Changing types → multi-step migration

---

## 7. API Surface (v1.0)

The full list of endpoints after v1.0 ships. Organized by resource. For each: method, path, request, response, status, errors.

| Resource | Method | Path | Auth | Notes |
|---|---|---|---|---|
| **Auth** | | | | |
| Register | POST | `/api/v1/auth/register` | No | F7 hardening: HIBP, email verify |
| Login | POST | `/api/v1/auth/login` | No | F7 hardening: lockout |
| Logout | POST | `/api/v1/auth/logout` | Optional | Clears cookies |
| Refresh | POST | `/api/v1/auth/refresh` | Cookie | F7: rotation tracking |
| Me | GET | `/api/v1/auth/me` | JWT | |
| GitHub OAuth start | GET | `/api/v1/auth/github` | No | F7: redirect to GitHub |
| GitHub OAuth callback | GET | `/api/v1/auth/github/callback` | No | F7: exchange code, upsert user |
| Verify email | POST | `/api/v1/auth/verify-email` | JWT | F7: Resend integration |
| Forgot password | POST | `/api/v1/auth/forgot-password` | No | F7: Resend email with token |
| Reset password | POST | `/api/v1/auth/reset-password` | No | F7: token + new password |
| **Servers** | | | | |
| List | GET | `/api/v1/servers` | JWT | paginated |
| Create | POST | `/api/v1/servers` | JWT | |
| Get | GET | `/api/v1/servers/{id}` | JWT | |
| Update | PATCH | `/api/v1/servers/{id}` | JWT | |
| Delete | DELETE | `/api/v1/servers/{id}` | JWT | 24h grace period |
| Duplicate | POST | `/api/v1/servers/{id}/duplicate` | JWT | |
| Pause | POST | `/api/v1/servers/{id}/pause` | JWT | |
| Resume | POST | `/api/v1/servers/{id}/resume` | JWT | |
| Deploy | POST | `/api/v1/servers/{id}/deploy` | JWT | Triggers F5 scan first |
| Rollback | POST | `/api/v1/servers/{id}/rollback` | JWT | Body: `{version: N}` |
| Versions | GET | `/api/v1/servers/{id}/versions` | JWT | |
| **Build pipeline** | | | | |
| Build status SSE | GET | `/api/v1/servers/{id}/build-status` | JWT | text/event-stream |
| Re-run AI | POST | `/api/v1/servers/{id}/tools/enhance` | JWT | Body: `{tool_names?: string[]}` |
| Accept AI | POST | `/api/v1/servers/{id}/tools/accept` | JWT | |
| **Tools** | | | | |
| List | GET | `/api/v1/servers/{id}/tools` | JWT | With quality scores |
| Update | PATCH | `/api/v1/servers/{id}/tools/{name}` | JWT | |
| **Spec ingestion** | | | | |
| Fetch | POST | `/api/v1/specs/fetch` | JWT | Body: `{url, headers?}` |
| Upload | POST | `/api/v1/specs/upload` | JWT | multipart/form-data, ≤5MB |
| Get tools | GET | `/api/v1/specs/{spec_id}/tools` | JWT | Parsed tools list |
| **Credentials** | | | | |
| Add/update | POST | `/api/v1/servers/{id}/credentials` | JWT | Body: `{env_var_name, value, auth_scheme}` |
| Test | POST | `/api/v1/servers/{id}/credentials/test` | JWT | Dry-run request |
| Get | GET | `/api/v1/servers/{id}/credentials` | JWT | Never returns value |
| Delete | DELETE | `/api/v1/servers/{id}/credentials` | JWT | |
| **Security** | | | | |
| Scan | POST | `/api/v1/servers/{id}/security/scan` | JWT | Async, returns job_id |
| Get result | GET | `/api/v1/servers/{id}/security/latest` | JWT | |
| Acknowledge | POST | `/api/v1/servers/{id}/security/{finding_id}/acknowledge` | JWT | |
| Report export | GET | `/api/v1/servers/{id}/security/report.json` | JWT | |
| **Analytics** | | | | |
| Overview | GET | `/api/v1/servers/{id}/analytics` | JWT | `?range=7d\|30d\|90d` |
| Tools breakdown | GET | `/api/v1/servers/{id}/analytics/tools` | JWT | |
| Errors | GET | `/api/v1/servers/{id}/analytics/errors` | JWT | paginated |
| Clients | GET | `/api/v1/servers/{id}/analytics/clients` | JWT | |
| Time series | GET | `/api/v1/servers/{id}/analytics/timeseries` | JWT | `?granularity=hour\|day` |
| Export | GET | `/api/v1/servers/{id}/analytics/export.csv` | JWT | |
| **Team** | | | | |
| Get team | GET | `/api/v1/team` | JWT | |
| Invite | POST | `/api/v1/team/invite` | JWT (admin) | Body: `{email, role}` |
| Update member | PATCH | `/api/v1/team/members/{user_id}` | JWT (admin) | Body: `{role}` |
| Remove | DELETE | `/api/v1/team/members/{user_id}` | JWT (admin) | |
| Audit log | GET | `/api/v1/team/audit-log` | JWT (admin) | |
| **API Keys** | | | | |
| List | GET | `/api/v1/api-keys` | JWT | |
| Create | POST | `/api/v1/api-keys` | JWT | Returns plaintext once |
| Revoke | DELETE | `/api/v1/api-keys/{id}` | JWT | |
| **Billing** | | | | |
| Plans | GET | `/api/v1/billing/plans` | No | List available plans |
| Subscribe | POST | `/api/v1/billing/subscribe` | JWT | Body: `{plan, stripe_payment_method}` |
| Portal | POST | `/api/v1/billing/portal` | JWT | Returns Stripe customer portal URL |
| Webhook | POST | `/api/v1/billing/webhook` | Stripe sig | Idempotent |
| **MCP Gateway** | | | | |
| Health | GET | `/mcp/v1/{slug}/health` | No | |
| SSE transport | GET | `/mcp/v1/{slug}/sse` | JWT (cookie/header) | text/event-stream |
| HTTP transport | POST | `/mcp/v1/{slug}/` | JWT | application/json |
| **Playground** | | | | |
| WebSocket | WS | `/ws/playground/{slug}?token=...` | JWT | |
| **System** | | | | |
| Health | GET | `/health` | No | DB + Redis check |
| API health | GET | `/api/v1/servers/health` | No | |
| Metrics | GET | `/metrics` | No | Phase 1.1 (Prometheus) |

That's **60+ endpoints**. Each is documented in its feature plan with full request/response schemas.

---

## 8. Frontend Surface (v1.0)

### 8.1 Pages (after v1.0)

| Path | Component | Feature |
|---|---|---|
| `/` | `app/page.tsx` | Landing (exists) |
| `/login` | `(auth)/login` | Login (exists) |
| `/register` | `(auth)/register` | Register (exists) |
| `/forgot-password` | `(auth)/forgot-password` (NEW) | F7 |
| `/reset-password?token=` | `(auth)/reset-password` (NEW) | F7 |
| `/dashboard` | `(dashboard)/dashboard` | Dashboard home (exists) |
| `/dashboard/servers` | `(dashboard)/servers` | List (exists) |
| `/dashboard/servers/new` | `(dashboard)/servers/new` | Create (exists, will add OpenAPI tab) |
| `/dashboard/servers/[slug]` | `(dashboard)/servers/[slug]` | Detail (PLACEHOLDER → real tabs) |
| `/dashboard/servers/[slug]/tools` | (NEW) | Tool workspace + description editor (F1, F2) |
| `/dashboard/servers/[slug]/playground` | (NEW) | 4-panel playground (F3) |
| `/dashboard/servers/[slug]/analytics` | (NEW) | Analytics dashboard (F6) |
| `/dashboard/servers/[slug]/settings` | (NEW) | Server settings, credentials, versions (F4, F5) |
| `/dashboard/servers/[slug]/security` | (NEW) | Security scanner results (F5) |
| `/dashboard/servers/[slug]/versions` | (NEW) | Version history (F4) |
| `/dashboard/team` | (NEW) | Team management (F7) |
| `/dashboard/team/invite` | (NEW) | Invite flow (F7) |
| `/dashboard/billing` | (NEW) | Stripe checkout/portal (F7) |
| `/dashboard/settings` | `(dashboard)/settings` | Profile (exists, will add password/2FA) |

### 8.2 Component tree additions

```
src/components/
├── ui/                          (existing + new shadcn primitives)
├── auth/                        (existing + forgot/reset forms)
├── dashboard/                   (existing + new)
│   ├── server-tabs.tsx          (NEW: server detail tab nav)
│   ├── quality-score-badge.tsx  (NEW: color-coded 0-100 badge, F2)
│   ├── tool-workspace.tsx       (NEW: tool list with toggles, F1)
│   ├── tool-row.tsx             (NEW: single tool with badges, F1)
│   ├── description-editor.tsx   (NEW: side-by-side Monaco, F2)
│   ├── description-comparison.tsx (NEW: diff view, F2)
│   ├── playground/              (NEW)
│   │   ├── playground-page.tsx
│   │   ├── tool-browser.tsx
│   │   ├── tool-form.tsx        (auto-generated form from schema)
│   │   ├── response-viewer.tsx
│   │   └── call-log.tsx
│   ├── analytics/               (NEW)
│   │   ├── overview-cards.tsx
│   │   ├── tool-breakdown.tsx
│   │   ├── error-log.tsx
│   │   ├── client-breakdown.tsx
│   │   └── time-series-chart.tsx
│   ├── security/                (NEW)
│   │   ├── findings-table.tsx
│   │   ├── finding-card.tsx
│   │   └── security-report.tsx
│   ├── team/                    (NEW)
│   │   ├── members-table.tsx
│   │   ├── invite-form.tsx
│   │   └── audit-log.tsx
│   └── billing/                 (NEW)
│       ├── plan-cards.tsx
│       └── payment-form.tsx
└── shared/                      (NEW)
    ├── empty-state.tsx
    ├── loading-spinner.tsx
    ├── error-banner.tsx
    ├── copy-to-clipboard.tsx
    └── pagination.tsx
```

### 8.3 Hook additions

```
src/hooks/
├── use-auth.ts                  (existing + useForgotPassword, useResetPassword, useVerifyEmail)
├── use-servers.ts               (existing + useUpdateServer, useDeleteServer, usePauseServer, useResumeServer, useDeployServer, useRollbackServer, useVersions)
├── use-spec.ts                  (NEW: useFetchSpec, useUploadSpec, useSpecTools)
├── use-tools.ts                 (NEW: useTools, useUpdateTool, useEnhanceTools, useAcceptEnhancement)
├── use-credentials.ts           (NEW: useSetCredential, useTestCredential, useGetCredentialMeta, useDeleteCredential)
├── use-security.ts              (NEW: useScan, useLatestScan, useAcknowledgeFinding)
├── use-playground.ts            (NEW: WebSocket session, tool call, call log)
├── use-analytics.ts             (NEW: useOverview, useToolsBreakdown, useErrors, useClients, useTimeSeries, useExport)
├── use-team.ts                  (NEW: useTeam, useInvite, useUpdateMember, useRemoveMember, useAuditLog)
├── use-api-keys.ts              (NEW: useApiKeys, useCreateApiKey, useRevokeApiKey)
├── use-billing.ts               (NEW: usePlans, useSubscribe, usePortal)
└── use-toast.ts                 (existing)
```

---

## 9. Definition of Done (overall v1.0)

When ALL of these are true, we ship:

### Product
- [ ] All 7 PRD features implemented per their plans
- [ ] All 3 user flows (A, B, C in PRD § 8) work end-to-end
- [ ] Landing page, pricing page, dashboard all polished
- [ ] Demo video recorded (paste Stripe URL → deployed MCP in 90s)

### Engineering
- [ ] All endpoints have tests (unit + integration)
- [ ] All top 3 user flows have Playwright E2E
- [ ] Lint + type-check + tests pass in CI
- [ ] `pnpm build` succeeds for all packages
- [ ] `docker compose up` brings up full stack
- [ ] Staging environment deployed and verified

### Security
- [ ] All credentials encrypted (Fernet)
- [ ] SSRF guard in gateway
- [ ] Rate limits per server, per user, per IP
- [ ] CSRF protection on cookie-auth
- [ ] Sentry captures errors
- [ ] No secrets in git history (verified)
- [ ] Argon2id for password hashing
- [ ] HIBP check on registration

### Quality
- [ ] Average tool quality score on Stripe MCP server: > 85/100
- [ ] Gateway P95 latency overhead: < 250ms
- [ ] AI enhancement per tool: < 3s
- [ ] Build pipeline for 15 tools: < 30s end-to-end

### Business
- [ ] Free tier enforces limits (500 calls/mo, 2 servers, 3 AI enhancements/mo)
- [ ] Pro plan ($12/mo) functional
- [ ] Team plan ($29/seat/mo) functional
- [ ] Stripe webhooks working
- [ ] Pricing page accurate

### Launch readiness
- [ ] HackerNews post drafted
- [ ] Twitter thread drafted
- [ ] 20 beta users onboarded
- [ ] Smithery/Glama submission prepared

---

## 10. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Render free tier cold starts (~30s) | Bad first-impression UX | High | Accept for v1.0; upgrade to $7/mo when 100+ active users. Alternative: Cloudflare Workers. |
| Anthropic rate limits hit during batch | Build pipeline fails | Medium | Implement exponential backoff with jitter (tenacity). Cache the spec prefix to reduce token pressure. |
| SSRF attack via tool parameters | Security incident | Low | Blocklist internal IPs in gateway, validate URL params server-side, document the threat model. |
| OpenAPI spec is malicious | Resource exhaustion, RCE | Low | Sandbox parsing in subprocess? No — accept the risk for v1.0, document it. Future: run parser in worker with resource limits. |
| Generated MCP server has poor descriptions | Product not useful | High | AI Engine is the core. Average quality score must be > 80 to be competitive. A/B test against Glama. |
| Celery worker crashes mid-build | User stuck | Medium | Persist job state in DB (ai_enhancement_jobs table). On worker restart, resume. |
| Playwright tests flaky | CI failures | Medium | Use `data-testid` selectors, not text. Retry-once policy. Run in serial mode. |
| Neon free tier scales to zero (~2s cold start) | First DB query slow | High | Accept for v1.0. Render container has same cold-start issue, so total first request is ~32s. Document. |
| Stripe integration broken | Billing broken | Low | Use Stripe SDK test mode, run webhook integration tests on every deploy. |
| Email delivery broken (Resend) | Users can't verify email | Low | Phase 1.1 feature; for v1.0, "verify by clicking link in console log" is fine. |
| Concurrent updates to tools_config | Last-write-wins | Medium | Use `version` field on mcp_servers; PATCH requires `If-Match: <version>` header (optimistic concurrency). |
| User uploads malicious OpenAPI spec | Service degraded | Low | 5MB limit (PRD), spec-validator catches malformed, parser catches malicious, timeout on parsing. |
| Cost overrun from AI | Bills spike | Medium | Hard cap: `MAX_AI_CREDITS_PER_USER` per day. Free tier: 3/month. Pro: unlimited but rate-limited to 100/day. |
| Token theft (XSS) | Account compromise | Low | httpOnly cookies, CSP header, no inline scripts. |
| Sentry quota exceeded | Errors not captured | Low | Sentry free tier = 5K events/mo. Sample 10% in prod. |
| Uptime SLA (PRD 99.9%) | Service-level breach | Medium | Multi-AZ only on paid tier; for v1.0, 99.9% is a stretch goal. Single AZ = ~99.5% realistic. |

---

## 11. Open Questions (need human input)

These are decisions I can't make alone. Tagged with priority.

### P0 (block Wave 0)
- None — Wave 0 is mechanical.

### P1 (block Wave 1)
- **Q1:** Should the spec upload go to S3 (or R2) immediately, or store in DB blob for v1.0? (Affects F1.)
- **Q2:** For OAuth2 upstream APIs, do we support v1.0 or defer to v1.2? (PRD says v1.2, so defer — but confirm.)
- **Q3:** When user pauses a server, do we keep credentials encrypted for quick resume, or decrypt+discard? (Affects F4, F7.)
- **Q4:** AI enhancement of 200+ tools in parallel — do we cap concurrency per user (e.g., 5 concurrent LLM calls)? Affects cost ceiling.

### P2 (block Wave 3)
- **Q5:** Stripe or LemonSqueezy for billing? (Stripe has better DX but stricter KYC. LemonSqueezy is merchant-of-record, simpler for indie.)
- **Q6:** When a user downgrades from Team to Pro, do we keep their team data, delete after 30 days, or delete immediately? (Affects F7.)
- **Q7:** Should we charge for additional AI enhancements beyond the plan limit ($0.10 each?) or hard cap? (Affects F2, F7.)

### P3 (informational, can decide later)
- **Q8:** Custom domain support (e.g., `mcp.yourcompany.com`)? (PRD doesn't mention; nice-to-have.)
- **Q9:** MCP server templates marketplace (PRD v2.0)? Not v1.0.
- **Q10:** Should MCPForge have its own MCP server (PRD § 16 mentions yes)? Affects Wave 3 launch.

---

## 12. What This Plan is NOT

- **Not a Gantt chart.** Build order is the commitment; exact week boundaries are flexible.
- **Not a staffing plan.** Whoever implements it can be 1 dev or 5.
- **Not a marketing plan.** PRD § 16 covers that.
- **Not exhaustive.** Each feature plan has the detail. This doc is the spine.

---

*See `01-COMPETITOR-ANALYSIS.md` for the competitive context that informs this plan. See `09-INFRA-MIGRATIONS.md` for the DB/infra evolution. See `features/` for per-feature deep dives.*
