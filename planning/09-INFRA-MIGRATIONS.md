# 09 — Infrastructure, Migrations, and Environment Variables

> **For AI agents:** This is the shared infrastructure plan that every feature plan depends on. Read this BEFORE starting any feature work. It defines the migrations order, the env vars each feature needs, the secrets model, and the deployment topology.

---

## 0. TL;DR

The codebase has a Phase 1 foundation (monorepo, auth, server CRUD, gateway stubs). This doc specifies the changes needed to support all 7 v1.0 features: 8 new Alembic migrations, 1 docker-compose.yml for local dev, 6+ new env vars, and 4 new service modules. All changes are designed to be deployable to the existing Render + Neon + Upstash free tier stack with no architectural surprises.

---

## 1. Migration Order

Alembic migration files live in `apps/api/alembic/versions/`. Naming: `NNNN_description.py`.

| # | File | Purpose | Depends on | Wave |
|---|---|---|---|---|
| `0001_initial` | (EXISTS) | users, mcp_servers, credentials, server_versions | — | Phase 1 |
| `0002_add_ai_enhancement` | NEW | mcp_servers: `description_review_status`, `last_ai_run_at`, `ai_enhancement_cost_cents` | 0001 | Wave 1 (F2) |
| `0003_add_tool_calls` | NEW | tool_calls (partitioned by day), indexes | 0002 | Wave 2 (F6) |
| `0004_add_security_scans` | NEW | security_scan_results, security_acknowledgments | 0003 | Wave 1 (F5) |
| `0005_add_teams` | NEW | teams, team_memberships, audit_logs | 0004 | Wave 3 (F7) |
| `0006_add_api_keys` | NEW | api_keys | 0005 | Wave 3 (F7) |
| `0007_add_billing` | NEW | subscriptions, invoices | 0006 | Wave 3 (F7) |
| `0008_add_refresh_token_tracking` | NEW | revoked_refresh_tokens (or use Redis only) | 0007 | Wave 0 (security hardening) |

**Rules:**
- Each migration must be **reversible** (`upgrade()` and `downgrade()` both work)
- Each migration must be **additive** or **nullable** when modifying existing tables
- After creating each migration, run on fresh DB to verify:
  ```bash
  cd apps/api
  uv run alembic upgrade head
  uv run alembic downgrade -1
  uv run alembic upgrade head
  ```

---

## 2. Migrations — Full Specifications

### 2.1 `0002_add_ai_enhancement.py`

**Adds to `mcp_servers` table:**
- `description_review_status` VARCHAR(20) NOT NULL DEFAULT 'pending' (`pending` | `in_progress` | `review` | `accepted` | `rejected`)
- `last_ai_run_at` TIMESTAMPTZ NULL
- `ai_enhancement_cost_cents` INT NOT NULL DEFAULT 0 (cumulative cents spent on this server's AI runs)
- `original_tools_config` JSONB NULL (snapshot before AI ran, for "revert all" functionality)

**Indexes:** none needed (low-cardinality column).

**Downgrade:** drop all 4 columns.

### 2.2 `0003_add_tool_calls.py`

**Creates `tool_calls` table (partitioned by day):**
```sql
CREATE TABLE tool_calls (
    id              UUID DEFAULT gen_random_uuid(),
    server_id       UUID NOT NULL,
    tool_name       VARCHAR(200) NOT NULL,
    status          VARCHAR(20) NOT NULL,  -- 'success' | 'error' | 'timeout'
    error_type      VARCHAR(100),
    error_msg       TEXT,                   -- sanitized, no credentials
    latency_ms      INT,
    response_size_bytes INT,
    client_name     VARCHAR(100),           -- 'Claude Desktop' | 'Cursor' | 'Unknown'
    called_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, called_at)            -- partition key must be in PK
) PARTITION BY RANGE (called_at);

-- Indexes
CREATE INDEX idx_tool_calls_server_id_called_at ON tool_calls (server_id, called_at);
CREATE INDEX idx_tool_calls_tool_name_called_at ON tool_calls (tool_name, called_at);
CREATE INDEX idx_tool_calls_status_called_at ON tool_calls (status, called_at) WHERE status != 'success';

-- Pre-create partitions for next 30 days + current month
-- Implementation: a Celery beat task creates partitions 7 days ahead daily
```

**Pre-create partitions in the migration itself** for current month + next month. Celery beat handles ongoing creation.

**Notes:**
- Parameter *values* are NEVER stored (enforced in service layer).
- Partition by `called_at` (range) for efficient time-range queries and easy retention (drop old partitions).

**Downgrade:** drop partitions, then drop table.

### 2.3 `0004_add_security_scans.py`

**Creates `security_scan_results` table:**
```sql
CREATE TABLE security_scan_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id       UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    scan_status     VARCHAR(20) NOT NULL,   -- 'running' | 'completed' | 'failed'
    findings        JSONB NOT NULL DEFAULT '[]'::jsonb,  -- array of finding objects
    critical_count  INT NOT NULL DEFAULT 0,
    high_count      INT NOT NULL DEFAULT 0,
    medium_count    INT NOT NULL DEFAULT 0,
    info_count      INT NOT NULL DEFAULT 0,
    scanned_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    scan_duration_ms INT
);
CREATE INDEX idx_scan_results_server_scanned ON security_scan_results (server_id, scanned_at DESC);
```

**Creates `security_acknowledgments` table:**
```sql
CREATE TABLE security_acknowledgments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id       UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    finding_id      VARCHAR(100) NOT NULL,  -- e.g., 'SSRF_URL_PARAM'
    acknowledged_by UUID NOT NULL REFERENCES users(id),
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    note            TEXT
);
CREATE UNIQUE INDEX idx_ack_server_finding ON security_acknowledgments (server_id, finding_id);
```

**Downgrade:** drop both tables.

### 2.4 `0005_add_teams.py`

**Creates `teams` table:**
```sql
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    owner_id    UUID NOT NULL REFERENCES users(id),
    plan        VARCHAR(20) NOT NULL DEFAULT 'team',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NULL
);
```

**Creates `team_memberships` table:**
```sql
CREATE TABLE team_memberships (
    team_id     UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL,  -- 'admin' | 'editor' | 'viewer'
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    invited_by  UUID REFERENCES users(id),
    PRIMARY KEY (team_id, user_id)
);
CREATE INDEX idx_memberships_user_id ON team_memberships (user_id);
```

**Creates `team_invitations` table:**
```sql
CREATE TABLE team_invitations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id      UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    email        VARCHAR(255) NOT NULL,
    role         VARCHAR(20) NOT NULL,
    token        VARCHAR(100) UNIQUE NOT NULL,
    invited_by   UUID NOT NULL REFERENCES users(id),
    expires_at   TIMESTAMPTZ NOT NULL,
    accepted_at  TIMESTAMPTZ NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_invitations_token ON team_invitations (token);
CREATE INDEX idx_invitations_email ON team_invitations (email);
```

**Alters `mcp_servers`:**
- Add `team_id` UUID NULL REFERENCES teams(id) ON DELETE CASCADE
- Add `owner_user_id` UUID NULL REFERENCES users(id) (for backwards compat; new servers set this, old ones have null team_id and we look up via `user_id`)
- Index on `team_id` (faster team-scoped queries)

**Creates `audit_logs` table:**
```sql
CREATE TABLE audit_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id       UUID REFERENCES teams(id) ON DELETE CASCADE,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    action        VARCHAR(100) NOT NULL,  -- 'server.create' | 'server.delete' | 'member.invite' | etc.
    resource_type VARCHAR(50),
    resource_id   UUID,
    metadata      JSONB,
    ip_address    INET,
    user_agent    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_team_created ON audit_logs (team_id, created_at DESC);
CREATE INDEX idx_audit_user_created ON audit_logs (user_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs (action);
```

**Downgrade:** drop all 3 new tables, drop columns from mcp_servers.

### 2.5 `0006_add_api_keys.py`

**Creates `api_keys` table:**
```sql
CREATE TABLE api_keys (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    team_id       UUID REFERENCES teams(id) ON DELETE CASCADE,
    name          VARCHAR(100) NOT NULL,
    key_prefix    VARCHAR(20) NOT NULL,    -- first 8 chars of plaintext, for display
    key_hash      VARCHAR(255) NOT NULL,   -- SHA-256 of full key
    scopes        TEXT[] NOT NULL DEFAULT '{}',  -- {'servers:read', 'servers:write', 'analytics:read'}
    last_used_at  TIMESTAMPTZ NULL,
    expires_at    TIMESTAMPTZ NULL,
    revoked_at    TIMESTAMPTZ NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_api_keys_user_id ON api_keys (user_id);
CREATE UNIQUE INDEX idx_api_keys_key_hash ON api_keys (key_hash);
```

**Notes:**
- Plaintext key returned ONCE at creation
- Format: `mcpforge_live_<32 random base62 chars>` (e.g., `mcpforge_live_AbC123...`)
- Hash with SHA-256, never bcrypt (these are already high-entropy)

**Downgrade:** drop table.

### 2.6 `0007_add_billing.py`

**Creates `subscriptions` table:**
```sql
CREATE TABLE subscriptions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID REFERENCES users(id) ON DELETE CASCADE,
    team_id               UUID REFERENCES teams(id) ON DELETE CASCADE,
    stripe_customer_id    VARCHAR(100),
    stripe_subscription_id VARCHAR(100) UNIQUE,
    plan                  VARCHAR(20) NOT NULL,  -- 'free' | 'pro' | 'team'
    status                VARCHAR(20) NOT NULL,  -- 'active' | 'past_due' | 'canceled' | 'trialing'
    current_period_start  TIMESTAMPTZ,
    current_period_end    TIMESTAMPTZ,
    cancel_at_period_end  BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NULL,
    CHECK (user_id IS NOT NULL OR team_id IS NOT NULL)
);
CREATE INDEX idx_subscriptions_stripe_customer ON subscriptions (stripe_customer_id);
CREATE INDEX idx_subscriptions_user_id ON subscriptions (user_id);
CREATE INDEX idx_subscriptions_team_id ON subscriptions (team_id);
```

**Creates `invoices` table:**
```sql
CREATE TABLE invoices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id     UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    stripe_invoice_id   VARCHAR(100) UNIQUE NOT NULL,
    amount_cents        INT NOT NULL,
    currency            VARCHAR(3) NOT NULL DEFAULT 'usd',
    status              VARCHAR(20) NOT NULL,  -- 'draft' | 'open' | 'paid' | 'uncollectible'
    invoice_pdf_url     TEXT,
    hosted_invoice_url  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_invoices_subscription ON invoices (subscription_id);
```

**Updates `users` table:** (nullable, defaults)
- Add `stripe_customer_id` VARCHAR(100) UNIQUE NULL

**Downgrade:** drop both tables, drop column from users.

### 2.7 `0008_add_refresh_token_tracking.py`

We have two options for refresh token rotation tracking:
1. **DB table** (durable, easy to audit)
2. **Redis with TTL** (faster, auto-expires)

**Recommendation:** Redis. The token rotation is time-bound (7 days), and Redis naturally evicts. Skip the migration, configure in code (F7 hardening).

**If we choose DB anyway:**
```sql
CREATE TABLE revoked_refresh_tokens (
    jti           VARCHAR(100) PRIMARY KEY,  -- JWT ID claim
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revoked_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL  -- 7 days from issue; after this, can be cleaned up
);
CREATE INDEX idx_revoked_user ON revoked_refresh_tokens (user_id);
```

**Downgrade:** drop table.

---

## 3. Environment Variables (Complete List)

### 3.1 Backend (`apps/api/.env`)

| Var | Default | Required? | Phase | Notes |
|---|---|---|---|---|
| `ENVIRONMENT` | `development` | Yes | 1 | development / production / testing |
| `LOG_LEVEL` | `INFO` | Yes | 1 | DEBUG / INFO / WARNING / ERROR |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Yes | 1 | Must use `+asyncpg` prefix |
| `REDIS_URL` | `redis://localhost:6379/0` | Yes | 1 | Use `rediss://` for TLS (Upstash) |
| `JWT_SECRET` | (must be set) | Yes | 1 | Min 32 chars. Use `openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` | No | 1 | |
| `JWT_ACCESS_TTL_MINUTES` | `15` | No | 1 | |
| `JWT_REFRESH_TTL_DAYS` | `7` | No | 1 | |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Yes | 1 | JSON array, exact match only |
| `GITHUB_OAUTH_CLIENT_ID` | (empty) | No | F7 | From GitHub OAuth app |
| `GITHUB_OAUTH_CLIENT_SECRET` | (empty) | No | F7 | From GitHub OAuth app |
| `GITHUB_OAUTH_REDIRECT_URI` | (empty) | No | F7 | `https://api.example.com/api/v1/auth/github/callback` |
| **`LLM_PROVIDER`** | `deepseek` | Yes (F2) | F2 | `deepseek` \| `openai` \| `anthropic` \| `opencode-go` \| `openrouter` \| `custom` |
| **`LLM_BASE_URL`** | `https://api.deepseek.com/v1` | Yes (F2) | F2 | Provider's OpenAI-compatible endpoint |
| **`LLM_MODEL`** | `deepseek-v4-flash` | Yes (F2) | F2 | Primary model name |
| **`LLM_API_KEY`** | (empty) | Yes (F2) | F2 | Provider API key |
| **`LLM_MAX_TOKENS`** | `2000` | No | F2 | Per-request max output tokens |
| **`LLM_TEMPERATURE`** | `0.0` | No | F2 | 0.0 = deterministic (recommended) |
| **`LLM_TIMEOUT_SECONDS`** | `60` | No | F2 | Per-request timeout |
| **`LLM_RETRY_ATTEMPTS`** | `3` | No | F2 | Retries on 429/5xx |
| **`LLM_PROMPT_CACHING_ENABLED`** | `true` | No | F2 | Provider-dependent; ignored if not supported |
| **`LLM_JSON_MODE`** | `true` | No | F2 | Use OpenAI-style `response_format: {type: json_object}` |
| **`ENCRYPTION_KEY`** | (must be set in prod) | Yes (F1+) | F1 | Fernet key. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| **`EMAIL_PROVIDER_API_KEY`** | (empty) | No | F7 | Resend API key |
| **`EMAIL_FROM_ADDRESS`** | `noreply@mcpforge.io` | No | F7 | Verified sender in Resend |
| **`STRIPE_SECRET_KEY`** | (empty) | No | F7 | `sk_test_...` or `sk_live_...` |
| **`STRIPE_WEBHOOK_SECRET`** | (empty) | No | F7 | `whsec_...` |
| **`STRIPE_PRICE_PRO_MONTHLY`** | (empty) | No | F7 | `price_...` from Stripe dashboard |
| **`STRIPE_PRICE_PRO_YEARLY`** | (empty) | No | F7 | |
| **`STRIPE_PRICE_TEAM_SEAT_MONTHLY`** | (empty) | No | F7 | Per-seat pricing |
| **`SENTRY_DSN`** | (empty) | No | W0 | `https://...@sentry.io/...` |
| **`SENTRY_ENVIRONMENT`** | (from `ENVIRONMENT`) | No | W0 | |
| **`SENTRY_TRACES_SAMPLE_RATE`** | `0.1` | No | W0 | 10% in prod, 100% in dev |
| **`R2_BUCKET`** | (empty) | No | F1 | Cloudflare R2 bucket name (e.g. `mcpforge-specs`) |
| `R2_ACCESS_KEY_ID` | (empty) | No | F1 | R2 API token's Access Key ID |
| `R2_SECRET_ACCESS_KEY` | (empty) | No | F1 | R2 API token's Secret Access Key |
| `R2_ACCOUNT_ID` | (empty) | No | F1 | For endpoint URL `https://{accountid}.r2.cloudflarestorage.com` |
| `R2_ENDPOINT_URL` | (empty) | No | F1 | Optional override; auto-derived from R2_ACCOUNT_ID |
| **`MAX_AI_CREDITS_PER_USER_PER_DAY`** | `100` | No | F2 | Cost ceiling |
| **`MAX_SPEC_SIZE_BYTES`** | `5242880` | No | F1 | 5MB |
| **`MAX_SPEC_FETCH_TIMEOUT_SECONDS`** | `10` | No | F1 | For fetching external spec URLs |
| **`RATE_LIMIT_PER_IP_PER_MINUTE`** | `60` | No | W0 | |
| **`RATE_LIMIT_AUTH_PER_IP_PER_MINUTE`** | `5` | No | W0 | Tighter for /auth/* |
| **`RATE_LIMIT_GATEWAY_PER_SERVER_PER_HOUR`** | (plan-dependent) | No | F4 | |
| **`CSRF_SECRET`** | (auto-derive) | No | W0 | For double-submit cookie. Falls back to JWT_SECRET if unset |
| **`STRIPE_LITIGATED_MODE`** | `false` | No | F7 | If true, skip Stripe entirely (for testing) |

### 3.2 Frontend (`apps/web/.env.local`)

| Var | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | No trailing slash |
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` | For OAuth redirects |
| `NEXT_PUBLIC_POSTHOG_KEY` | (empty) | Optional analytics |
| `NEXT_PUBLIC_POSTHOG_HOST` | (empty) | Optional |
| `NEXT_PUBLIC_SENTRY_DSN` | (empty) | F0 — Sentry on the frontend |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | (empty) | F7 — `pk_test_...` or `pk_live_...` |
| `NEXT_PUBLIC_GITHUB_OAUTH_CLIENT_ID` | (empty) | F7 — for the OAuth button |

### 3.3 Per-feature env var matrix

| Feature | New backend env | New frontend env |
|---|---|---|
| Wave 0 (hardening) | SENTRY_DSN, SENTRY_*, CSRF_SECRET, RATE_LIMIT_* | NEXT_PUBLIC_SENTRY_DSN |
| F1 (OpenAPI Ingestion) | ENCRYPTION_KEY, S3_*, MAX_SPEC_SIZE_BYTES, MAX_SPEC_FETCH_TIMEOUT_SECONDS | — |
| F2 (AI Engine) | LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_TIMEOUT_SECONDS, LLM_RETRY_ATTEMPTS, LLM_PROMPT_CACHING_ENABLED, LLM_JSON_MODE, MAX_AI_CREDITS_PER_USER_PER_DAY | — |
| F3 (Playground) | — | — |
| F4 (Gateway) | RATE_LIMIT_GATEWAY_PER_SERVER_PER_HOUR | — |
| F5 (Security Scanner) | — | — |
| F6 (Analytics) | — | — |
| F7 (Auth/Teams/Billing) | GITHUB_OAUTH_*, EMAIL_PROVIDER_*, STRIPE_*, STRIPE_LITIGATED_MODE | NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY, NEXT_PUBLIC_GITHUB_OAUTH_CLIENT_ID |

---

## 4. Secrets Management

### 4.1 Local development

- `apps/api/.env` (gitignored) — copy from `.env.example`, fill in real values
- `apps/web/.env.local` (gitignored) — copy from `.env.example`, fill in real values
- For team development, share secrets via 1Password or Doppler (not in repo)

### 4.2 Production (Render dashboard)

- All `sync: false` env vars set in Render service dashboard
- `JWT_SECRET` auto-generated by Render (`generateValue: true`)
- `ENCRYPTION_KEY` manually generated, manually pasted
- `LLM_API_KEY` (primary provider) — manually pasted
- All others as needed per feature rollout

### 4.3 Secret rotation

- `JWT_SECRET`: rotation invalidates all sessions. Acceptable once a year.
- `ENCRYPTION_KEY`: rotation requires re-encrypting all credentials in `credentials` table. Document a 1-day process; do quarterly.
- `LLM_API_KEY`: rotate via provider console, no data loss.

### 4.4 Production-grade upgrade path (Phase 1.1)

For multi-environment setups (staging, multiple prod regions), move secrets to:
- **Doppler** (https://doppler.com) — free tier for 3 users, $0 for OSS
- **Doppler** (https://doppler.com) — free tier for 3 users, syncs to Render, simple UI

Decision: defer to Phase 1.1. Render env vars are fine for v1.0.

---

## 5. Local Development Setup

### 5.1 Add `docker-compose.yml` at repo root

Services:
- `postgres:16-alpine` (port 5432, healthcheck)
- `redis:7-alpine` (port 6379, healthcheck)
- `api` (builds from `apps/api/Dockerfile.dev`, port 8000)
- `worker` (Celery worker, same image as api)
- `beat` (Celery beat, same image as api)

**Why:** Single command starts full backend stack. No manual Postgres install.

### 5.2 Add `apps/api/Dockerfile.dev`

Multi-stage but with dev deps. Mounts code as volume for live reload. Uses `uvicorn --reload`.

### 5.3 Add Makefile or `package.json` scripts

```bash
# Root
pnpm dev         # turborepo parallel: api + web
pnpm dev:api     # api only (uvicorn + celery worker + beat)
pnpm dev:web     # web only
pnpm dev:db      # docker compose up postgres redis
```

---

## 6. Production Deployment Topology

### 6.1 Current state (Phase 1)

```
Render free tier (Oregon, 1 instance)
├── API process (uvicorn)
└── Migrations run on container start

Neon free tier
└── Single PostgreSQL 16 instance (no replica, scales to zero)

Upstash free tier
└── Single Redis instance (10K commands/day)

Vercel (auto)
└── Next.js frontend
```

### 6.2 Phase 1.0 target state (Wave 1 ships)

Same as current, PLUS:
- Celery worker as separate Render service (free plan OK for low traffic; upgrade when needed)
- S3/R2 bucket for spec storage
- Sentry for error tracking

### 6.3 Production-grade (Phase 1.1+)

```
Render (paid) — multi-instance API + dedicated Celery workers
Neon (paid) — Multi-AZ, read replica for analytics
Upstash (paid) — Redis cluster mode
Cloudflare R2 (paid) — when free tier exhausted
Cloudflare (free) — CDN, DNS, DDoS protection
Sentry (paid) — when free tier 5K events exhausted
```

### 6.4 Deployment process

```bash
# On merge to main:
1. GitHub Actions CI runs:
   - lint + type-check (all packages)
   - backend tests (Postgres + Redis services)
   - frontend build
   - frontend tests (when added)
2. GitHub Actions deploy runs (if CI green):
   - Trigger Vercel deploy
   - Trigger Render deploy hook
3. Render builds Docker image, runs migrations, restarts service
4. Smoke test against /health
5. (Phase 1.1) Run E2E tests against staging
```

### 6.5 Zero-downtime deploys

Render free tier has a brief cold start during deploy. Acceptable for v1.0.
For Phase 1.1 (paid tier): configure Render to keep at least 1 instance running during deploys.

---

## 7. Cost Projections (v1.0 launch)

| Service | Tier | Cost/mo | Notes |
|---|---|---|---|
| Render API | Free | $0 | Sleeps after 15min; acceptable |
| Render Celery worker | Free | $0 | Sleeps; AI jobs run on next wakeup (≤30s) |
| Neon Postgres | Free | $0 | 0.5GB; scales to zero |
| Upstash Redis | Free | $0 | 10K cmd/day; may exceed at 50K tool calls/mo |
| Vercel | Free | $0 | 100GB bandwidth |
| Cloudflare R2 | Free | $0 | 10GB storage, no egress |
| Sentry | Free | $0 | 5K events/mo |
| Resend | Free | $0 | 100 emails/day (Phase 1.1) |
| Anthropic API | Pay-as-you-go | $5-50 | ~$0.01-0.05 per server enhancement (3K enhancements/mo = $30-150) |
| **Total** | | **$5-50/mo** | Plus our time |

At 2,000 users / 500 active servers / 50K tool calls / 1,500 AI enhancements per month:
- Upstash: ~10K-50K commands/day (at upper limit)
- Anthropic: ~$50-100/mo (1,500 × $0.05)
- Sentry: ~10K events/mo (2x over free tier)
- **Total: ~$100-200/mo at launch volume**

---

## 8. Observability

### 8.1 Logging (existing + hardening)

- `structlog` configured in `app/core/logging.py`
- **Add:** JSON formatter for production, colored for development
- **Add:** Request ID middleware (UUID v4 in `X-Request-ID` header, propagated)
- **Add:** Sensitive data filter (strips `Authorization`, `api_key`, `password`, `secret` from log records)
- **Add:** Correlation — request_id, user_id, server_id in every log line
- **Render:** Logs go to stdout, captured by Render's log viewer, searchable via Render dashboard

### 8.2 Error tracking (Wave 0)

- `sentry-sdk[fastapi]` in `apps/api/pyproject.toml`
- Initialize in `app.main`:
  ```python
  if settings.SENTRY_DSN:
      sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT, traces_sample_rate=...)
  ```
- Captures: unhandled exceptions, FastAPI HTTPException with status 500+
- PII: configure `before_send` to strip `Authorization` headers, request bodies for credential routes

### 8.3 Metrics (Phase 1.1, stub now)

- Not in v1.0
- Phase 1.1: Prometheus + Grafana
- For v1.0, just counts in `mcp_servers.total_calls` and `.monthly_calls`

### 8.4 Tracing (Phase 1.1, stub now)

- Not in v1.0
- Phase 1.1: OpenTelemetry
- For v1.0, request_id correlation is enough

### 8.5 Health checks

- `GET /health` (existing) — checks DB + Redis, returns 200 if both up
- `GET /api/v1/servers/health` (existing) — basic, no deps
- `GET /mcp/v1/{slug}/health` (existing) — checks if server exists
- `GET /health/worker` (NEW) — Celery worker liveness via `celery -A app.celery_app inspect ping`

---

## 9. Background Job Architecture

### 9.1 Celery configuration

```python
# app/core/celery_app.py
from celery import Celery

celery_app = Celery('mcpforge', broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_expires=3600,  # 1 hour
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_queue='default',
    task_routes={
        'app.services.ai_description.tasks.*': {'queue': 'ai'},
        'app.services.security_scanner.tasks.*': {'queue': 'scanner'},
        'app.services.analytics.tasks.*': {'queue': 'analytics'},
    },
    task_queues={
        'ai': {'exchange': 'ai', 'routing_key': 'ai'},
        'scanner': {'exchange': 'scanner', 'routing_key': 'scanner'},
        'analytics': {'exchange': 'analytics', 'routing_key': 'analytics'},
    },
    beat_schedule={
        'aggregate-analytics': {
            'task': 'app.services.analytics.tasks.aggregate_hourly',
            'schedule': crontab(minute=5),  # every hour at :05
        },
        'create-tool-call-partitions': {
            'task': 'app.services.analytics.tasks.create_partitions',
            'schedule': crontab(hour=0, minute=30),  # daily
        },
        'cleanup-revoked-tokens': {
            'task': 'app.services.auth.tasks.cleanup_revoked_tokens',
            'schedule': crontab(hour=2, minute=0),  # daily
        },
    },
)
```

### 9.2 Worker deployment (Render)

- Free tier: 1 worker, 1 queue (ai). Acceptable for v1.0 with 500 servers.
- Phase 1.1: separate workers per queue, multiple replicas
- Worker CMD: `celery -A app.core.celery_app worker -Q ai,scanner,analytics -l info --concurrency=2`
- Beat CMD: `celery -A app.core.celery_app beat -l info`

### 9.3 Task patterns

```python
# Generic task with retry + logging
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(openai.RateLimitError, httpx.TimeoutException, openai.APIConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
)
async def enhance_single_tool(self, server_id: str, tool_name: str) -> dict:
    logger = get_logger(__name__)
    request_id = self.request.id
    logger.info("enhance_tool_start", server_id=server_id, tool_name=tool_name, request_id=request_id)
    
    try:
        # ... actual work ...
        return result
    except Exception as e:
        logger.error("enhance_tool_failed", server_id=server_id, tool_name=tool_name, error=str(e))
        raise
```

---

## 10. New Shared Modules

### 10.1 `app/core/celery_app.py`
Celery application factory. Imported by worker process.

### 10.2 `app/core/encryption.py`
Fernet-based encryption helpers.
```python
from cryptography.fernet import Fernet
from app.core.config import settings

def _get_fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())

def decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
```

### 10.3 `app/core/rate_limit.py`
Redis-backed token bucket. Plan-aware.
```python
async def check_rate_limit(scope: str, key: str, limit: int, window_seconds: int) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    # Lua script for atomic check-and-increment
    ...
```

### 10.4 `app/core/request_id.py`
ASGI middleware that injects `request_id` (UUID v4) into a `contextvars.ContextVar` and `X-Request-ID` response header.

### 10.5 `app/core/sensitive.py`
Structlog processor that strips sensitive fields:
```python
SENSITIVE_KEYS = {'authorization', 'api_key', 'password', 'secret', 'token', 'cookie'}

def strip_sensitive(logger, method_name, event_dict):
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in SENSITIVE_KEYS):
            event_dict[key] = '[REDACTED]'
    return event_dict
```

---

## 11. New Service Modules

| File | Purpose | Feature |
|---|---|---|
| `app/services/openapi_fetcher.py` | Fetch + validate OpenAPI from URL | F1 |
| `app/services/spec_analyzer.py` | Parse spec, extract tools | F1 |
| `app/services/tool_generator.py` | Convert OpenAPI ops → MCP tool defs | F1 |
| `app/services/credential_service.py` | Encrypt/decrypt credentials | F1/F4 |
| `app/services/ai_description_engine.py` | AI description enhancement | F2 |
| `app/services/ai_description/prompts.py` | LLM prompt templates (provider-agnostic) | F2 |
| `app/services/ai_description/quality_scorer.py` | 4-dimension quality scoring | F2 |
| `app/services/ai_description/tasks.py` | Celery tasks | F2 |
| `app/services/server_builder.py` | Convert tools_config to live server | F4 |
| `app/services/gateway/dispatcher.py` | Route tool calls to target APIs | F4 |
| `app/services/gateway/response_handler.py` | Truncate, base64, strip HTML | F4 |
| `app/services/security_scanner/rules.py` | Security rules | F5 |
| `app/services/security_scanner/scanner.py` | Run scans | F5 |
| `app/services/security_scanner/tasks.py` | Celery tasks | F5 |
| `app/services/analytics/recorder.py` | Record tool calls | F6 |
| `app/services/analytics/aggregator.py` | Aggregate to rollups | F6 |
| `app/services/analytics/tasks.py` | Celery tasks | F6 |
| `app/services/team_service.py` | Team management | F7 |
| `app/services/api_key_service.py` | API key CRUD | F7 |
| `app/services/billing/stripe_client.py` | Stripe wrapper | F7 |
| `app/services/billing/webhook_handler.py` | Stripe webhook | F7 |
| `app/services/auth/password.py` | Argon2id, HIBP, lockout | F7 (Wave 0) |
| `app/services/auth/oauth_github.py` | GitHub OAuth | F7 |
| `app/services/auth/token_rotation.py` | Refresh token tracking | F7 (Wave 0) |

That's **22 new service modules**. Each ships with its own test file.

---

## 12. New API Routes

Add to `app/api/v1/endpoints/`:

| File | Routes | Feature |
|---|---|---|
| `specs.py` | /specs/fetch, /specs/upload, /specs/{id}/tools | F1 |
| `tools.py` | /servers/{id}/tools, /tools/{name}, /tools/enhance | F1, F2 |
| `credentials.py` | /servers/{id}/credentials/* | F1, F4 |
| `build.py` | /servers/{id}/build-status (SSE), /build, /accept | F1, F2 |
| `security.py` | /servers/{id}/security/* | F5 |
| `analytics.py` | /servers/{id}/analytics/* | F6 |
| `team.py` | /team, /team/invite, /team/members/*, /team/audit-log | F7 |
| `api_keys.py` | /api-keys/* | F7 |
| `billing.py` | /billing/plans, /billing/subscribe, /billing/portal, /billing/webhook | F7 |
| `auth.py` (modify) | Add /auth/forgot-password, /auth/reset-password, /auth/verify-email, /auth/github, /auth/github/callback | F7 |

That's **9 new route files + 1 modified**.

---

## 13. Database Indexes (for performance)

Already exist: `idx_servers_slug`, `idx_servers_user_id`, primary keys on all tables.

Add in migrations:
- `idx_tool_calls_server_id_called_at` (F6)
- `idx_tool_calls_tool_name_called_at` (F6)
- `idx_tool_calls_status_called_at` WHERE status != 'success' (F6)
- `idx_scan_results_server_scanned` (F5)
- `idx_audit_team_created` (F7)
- `idx_audit_user_created` (F7)
- `idx_audit_action` (F7)
- `idx_subscriptions_stripe_customer` (F7)

---

## 14. Backups & Disaster Recovery

### 14.1 Neon
- Free tier: 7-day PITR (point-in-time recovery)
- Paid tier: 30-day PITR
- **Decision:** free tier acceptable for v1.0

### 14.2 Render
- Free tier: no automatic backups beyond disk
- **Decision:** rely on Neon for state. Render is stateless.

### 14.3 R2 (specs storage)
- 11 nines of durability per Cloudflare
- No backup needed

### 14.4 Disaster recovery scenarios
- **DB corruption:** restore from Neon PITR (within last 7 days)
- **Render region down:** wait for Render to recover (free tier has no multi-region)
- **Anthropic API down:** AI Engine fails gracefully, original descriptions still work
- **Neon DB down:** app shows 503, Render shows "starting" until DB back

---

## 15. Compliance Notes

### 15.1 GDPR
- User data export: endpoint `GET /api/v1/auth/me/data-export` returns all user data (F7)
- User data deletion: endpoint `DELETE /api/v1/auth/me` (F7) — soft delete for 30 days, hard delete after
- Cookie consent: out of scope for v1.0 (we use only necessary cookies)

### 15.2 CCPA
- Same as GDPR — covered by F7 endpoints

### 15.3 SOC 2
- Out of scope for v1.0. Phase 2+.

### 15.4 HIPAA
- Out of scope. Documented in Terms of Service: "MCPForge is not for processing PHI."

---

## 16. New Files Summary

For a complete Wave 0 + Wave 1 implementation:
- **8 new Alembic migrations**
- **22 new service modules** (across features)
- **9 new endpoint files** + 1 modified
- **1 docker-compose.yml** at root
- **1 Dockerfile.dev** in apps/api
- **5 new shared core modules** (celery, encryption, rate_limit, request_id, sensitive)
- **4 new models** (tool_calls, security_scan_results, security_acknowledgments, teams, team_memberships, team_invitations, audit_logs, api_keys, subscriptions, invoices, revoked_refresh_tokens [if DB-based])
- **7 new model files** in `app/models/`

Total new files (Wave 0 + Wave 1): ~60 files. Total LoC: ~15,000-20,000 lines.

Wave 2 adds: ~15 more files (playground backend, analytics), ~4,000 LoC.
Wave 3 adds: ~25 more files (teams, billing, Stripe), ~7,000 LoC.

**Total v1.0:** ~100 new files, ~25,000-30,000 LoC.

---

*See individual feature plans (`features/02-FEATURE-OPENAPI-INGESTION.md` through `08-FEATURE-AUTH-TEAMS-MANAGEMENT.md`) for the detailed per-feature build sequence.*
