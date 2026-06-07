# AGENTS.md — MCPForge Engineering Context

> This file is the source of truth for AI coding agents (Claude Code, Cursor, etc.) working on MCPForge. Read it first. Update it as the project evolves.

## What is MCPForge?

MCPForge is a web platform that converts any OpenAPI spec into a production-ready MCP (Model Context Protocol) server with AI-optimized tool descriptions. Users paste an OpenAPI URL, get a hosted MCP endpoint they can add to Claude Desktop / Cursor / Windsurf.

**Core differentiator:** AI Description Engine that rewrites tool descriptions for maximum LLM selection probability (260% lift vs mechanically generated descriptions per arxiv 2602.18914).

**Reference:** `MCPForge_PRD.md` in the parent directory. This is the canonical product spec.

## Architecture (MCPForge monorepo)

```
mcpforge-monorepo/
├── apps/
│   ├── api/          # FastAPI: main API + MCP gateway + WebSocket playground (combined)
│   └── web/          # Next.js 15: Builder UI, Playground, Analytics, Dashboard
├── packages/
│   ├── tsconfig/     # Shared TypeScript configs
│   ├── eslint-config/# Shared ESLint configs
│   ├── python-config/# Shared Python tooling (ruff, mypy, pytest)
│   ├── ui/           # Shared shadcn/ui components (built from apps/web)
│   └── shared-types/ # TS types generated from FastAPI OpenAPI schema
├── .github/workflows/# CI
├── turbo.json
├── pnpm-workspace.yaml
├── package.json
└── AGENTS.md (this file)
```

### Why this shape?

- **Turborepo + pnpm** for atomic cross-service changes and shared types
- **apps/api** consolidates what the PRD calls 3 services (main API, MCP gateway, playground proxy) into one FastAPI process — they're split later only when traffic justifies independent scaling
- **apps/web** on Vercel (Next.js 15 App Router, server components, edge-ready)
- **apps/api** on Render free tier (Docker, sleeps after 15 min inactivity)
- **Database** on Neon free PostgreSQL (scales to zero, 0.5GB free)
- **Cache** on Upstash free Redis (10K commands/day, replaceable with in-memory for now)

### Phase 1 scope (current)

**Build:** monorepo foundation + auth + minimal MCP server creation + dashboard shell
**Skip for now:** AI Description Engine, security scanner, advanced analytics, billing, teams, registry submission

## Build & run commands

```bash
# Install everything
pnpm install

# Start both apps in dev mode (parallel)
pnpm dev

# Start only one
pnpm dev:api
pnpm dev:web

# Build all
pnpm build

# Lint + type check
pnpm lint
pnpm type-check

# Test
pnpm test

# Format
pnpm format
```

### Backend-specific (apps/api)

```bash
cd apps/api

# Activate venv
source .venv/bin/activate

# Run migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Run backend without Docker (local)
uvicorn app.main:app --reload --port 8000

# Run with Docker
docker build -t mcpforge-api .
docker run -p 8000:8000 mcpforge-api

# Tests
pytest

# Local env vars (example — copy to .env for persistence)
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/mcpforge"
export JWT_SECRET="local-dev-secret-must-be-at-least-32-characters-long"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT=development
export CORS_ORIGINS='["http://localhost:3000"]'
```

### Frontend-specific (apps/web)

```bash
cd apps/web

# Dev server
pnpm dev

# Build
pnpm build

# Generate TS types from backend OpenAPI (run after backend is running)
pnpm gen:api-types  # calls packages/shared-types fetch + openapi-typescript
```

### Shared types (packages/shared-types)

```bash
cd packages/shared-types

# Fetch latest OpenAPI schema (backend must be running)
pnpm fetch

# Regenerate api-types.d.ts
pnpm generate

# Override API URL: API_URL=https://mcpforge-api.onrender.com pnpm fetch
```

## Conventions

### Code style

- **TypeScript:** Strict mode, no `any` ever, prefer `unknown` + type guards. Use `import type` for type-only imports.
- **Python:** Strict mypy, ruff for lint+format, Pydantic v2 for all schemas, async everywhere (no sync DB calls).
- **Naming:** snake_case for Python, camelCase for TS variables, PascalCase for TS components/classes.
- **Files:** kebab-case for filenames (`user-service.ts`, `mcp_server.py`).

### Backend patterns (FastAPI)

- **Settings:** Pydantic Settings in `app/core/config.py`, load from env. Never read `os.environ` directly.
- **DB sessions:** Inject via `Depends(get_db)`. Never use module-level sessions.
- **Auth:** JWT in httpOnly cookies. `get_current_user` dependency for protected routes.
- **Errors:** Raise `HTTPException` with structured detail. Custom exception handlers in `app/core/exceptions.py`.
- **Logging:** `structlog` configured in `app/core/logging.py`. JSON in prod, colored in dev. Request ID injected via middleware. Never `print()`.
  - **Gotcha:** `get_logger()` returns the raw `structlog.get_logger()` result — do NOT `assert isinstance(..., structlog.stdlib.BoundLogger)` because the proxy is resolved lazily on first call. Type the return as `Any`.
- **Services vs routes:** Routes = HTTP plumbing only. Business logic in `app/services/`. DB queries in `app/repositories/`.

### Frontend patterns (Next.js)

- **Server components by default.** Add `"use client"` only when needed (forms, hooks, browser APIs).
- **Data fetching:** TanStack Query for client state, RSC + `fetch` for server data.
- **Forms:** `react-hook-form` + Zod schemas (shared with backend where possible).
- **UI:** shadcn/ui components in `apps/web/components/ui/`. Shared ones promote to `packages/ui/`.
- **State:** Zustand for global client state, TanStack Query for server state. No Redux.
- **Styling:** Tailwind v4, no CSS modules. CSS variables for theming.

### MCP protocol

- Use `mcp` Python SDK (planned, not yet in deps).
- Gateway endpoint: `/mcp/v1/{slug}/sse` for SSE transport.
- HTTP endpoint: `/mcp/v1/{slug}/` for StreamableHTTP transport.
- All tool calls go through the gateway service — never direct API calls from frontend.

## Database schema (current, partial)

```sql
-- Phase 1 tables only
users            (id, email, password_hash, github_id, plan, email_verified, created_at, updated_at)
mcp_servers      (id, user_id, slug, name, base_url, auth_scheme, tools_config jsonb, status, created_at, updated_at)
credentials      (id, server_id, env_var_name, encrypted_value bytea, created_at)
server_versions  (id, server_id, version, tools_config jsonb, change_note, created_at)
-- tool_calls, teams, audit_logs added in later phases
```

## Environment variables

### apps/api/.env

```bash
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-me-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
CORS_ORIGINS=http://localhost:3000
ANTHROPIC_API_KEY=           # added in Phase 3
```

### apps/web/.env.local

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Deployment

Free tier stack: Vercel (web) + Render (api) + Neon (Postgres) + Upstash (Redis). All $0/mo at <100 users.

### 1. Database (Neon)

1. Sign up at https://neon.tech (free tier: 0.5GB, scales to zero)
2. Create project `mcpforge-prod` in `us-east-1`
3. Copy the **pooled** connection string → save as `DATABASE_URL`
4. Format: `postgresql+asyncpg://USER:PASS@HOST.neon.tech/DBNAME?sslmode=require`

### 2. Cache (Upstash)

1. Sign up at https://upstash.com (free tier: 10K cmd/day)
2. Create Redis database in `us-east-1`
3. Copy the **TLS** URL → save as `REDIS_URL`
4. Format: `rediss://default:PASS@HOST.upstash.io:6379`

### 3. Backend (Render)

1. Sign up at https://render.com with GitHub
2. Click **New** → **Blueprint** → select this repo
3. Render reads `render.yaml` at repo root and provisions:
   - `mcpforge-api` (Docker, free plan, oregon region)
   - Health check on `/health`
   - Auto-deploy on push to `main`
4. After first deploy fails (no env vars), open service → **Environment**:
   - `DATABASE_URL` = (from step 1)
   - `REDIS_URL` = (from step 2)
   - `JWT_SECRET` = (Render auto-generates; copy and save)
   - `CORS_ORIGINS` = `["https://YOUR-APP.vercel.app"]` (set after step 4)
   - `ENVIRONMENT` = `production`
   - `LOG_LEVEL` = `INFO`
5. **Manual deploy** to pick up env vars
6. Run migrations from Render Shell: `alembic upgrade head`
7. Verify: `curl https://mcpforge-api.onrender.com/health` → `{"status":"ok",...}`

### 4. Frontend (Vercel)

1. Sign up at https://vercel.com with GitHub
2. **Add New Project** → import this repo
3. Vercel reads `vercel.json` at repo root, auto-detects `apps/web`
4. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = `https://mcpforge-api.onrender.com`
   - `NEXT_PUBLIC_APP_URL` = `https://YOUR-APP.vercel.app`
5. Deploy. First build: ~2 min.
6. After deploy succeeds, copy the Vercel URL → go back to Render step 4 and update `CORS_ORIGINS` with the real URL (no trailing slash, exact match).

### 5. Wire backend to frontend

1. After step 4, update Render `CORS_ORIGINS` with the real Vercel URL
2. Re-deploy backend (auto on next push, or manual)
3. End-to-end test: visit Vercel URL → register → create server → call MCP endpoint

### Gotchas

- Render free tier **sleeps after 15 min** — first request takes ~30s. Either accept the cold start or upgrade to a paid plan.
- Neon free tier **scales to zero after 5 min** — first DB query takes ~2s. Same trade-off.
- Cookie `Secure` flag is enabled in production (`ENVIRONMENT=production`) — httpOnly cookies require HTTPS.
- Vercel monorepo detection: if it picks the wrong root, set **Root Directory** to `apps/web` in project settings.

## What to work on next

### Phase 1 — DONE (this branch)

- [x] Monorepo foundation (Turborepo + pnpm)
- [x] Backend: auth (register, login, refresh, logout, me), MCP server CRUD, minimal MCP gateway with `echo` tool
- [x] Frontend: landing, auth pages, dashboard, server list, server create, server detail, settings
- [x] Shared types auto-generated from OpenAPI (`@mcpforge/shared-types`, 1064 lines)
- [x] End-to-end test passes locally: register → cookie set → /me → create server → CORS verified
- [x] CI (lint, type-check, tests, build), deployment configs (render.yaml, vercel.json, Dockerfile)

### Phase 2 — OpenAPI spec ingestion (the actual product)

1. **OpenAPI fetcher** — `app/services/openapi_fetcher.py`: download from URL, parse with `openapi-spec-validator`, reject bad specs with helpful errors.
2. **Spec analyzer** — `app/services/spec_analyzer.py`: extract endpoints, parameters, request/response schemas. Map to MCP tool definitions.
3. **Tool generator** — `app/services/tool_generator.py`: convert each OpenAPI operation into one MCP tool with name, description, input schema.
4. **Frontend builder UI** — `apps/web/src/app/(dashboard)/servers/new/page.tsx`: paste OpenAPI URL, preview generated tools, confirm creation.
5. **Server build pipeline** — `apps/api/app/services/server_builder.py`: convert `mcp_servers.tools_config` JSONB into a live gateway config that serves real tool calls (not just `echo`).
6. **Versioning** — every spec update creates a `server_versions` row, dashboard shows diffs.
7. **Encrypted credentials** — `credentials` model exists, wire up Fernet encryption in `app/services/credential_service.py`, UI to add API keys per server.

## Anti-patterns to avoid

- ❌ `as any`, `@ts-ignore`, `@ts-expect-error` — fix the type properly
- ❌ Sync DB calls in async FastAPI routes — use `AsyncSession`
- ❌ Direct API calls to user APIs from frontend — must go through MCP gateway
- ❌ Storing API credentials in plaintext — always encrypt (Fernet for now, KMS later)
- ❌ Logging request/response bodies with credentials — sanitize before logging
- ❌ Hardcoding URLs or secrets in code — use settings/env
- ❌ `print()` in Python — use `logger`
- ❌ `console.log` in committed TS code — use proper logging
- ❌ `git commit` without explicit user request
- ❌ Modifying the user's existing files without permission

## Useful file paths

- PRD: `../MCPForge_PRD.md`
- This file: `./AGENTS.md`
- Monorepo root: `./`
- Backend: `./apps/api/`
- Frontend: `./apps/web/`
- Shared types: `./packages/shared-types/` (generated)
- CI: `./.github/workflows/`

## Update protocol

When you make architectural decisions or learn non-obvious things, update this file. Future agents (and the user) need the latest context. Keep it scannable — use bullet points and code blocks, not prose.
