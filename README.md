# MCPForge

> Convert any OpenAPI spec to an AI-optimized MCP server in under 60 seconds.

MCPForge is a web platform that lets API developers turn their OpenAPI specs into production-ready Model Context Protocol (MCP) servers — without writing protocol code, installing CLI tools, or managing local environments. The platform's AI Description Engine rewrites tool descriptions to maximize LLM selection probability (260% lift vs mechanically generated descriptions).

**For full product spec, see [`../MCPForge_PRD.md`](../MCPForge_PRD.md).**

## Architecture

This is a **Turborepo monorepo** with:

- **`apps/api`** — FastAPI backend (main API + MCP gateway + WebSocket playground, combined for cost efficiency)
- **`apps/web`** — Next.js 15 frontend (App Router, shadcn/ui, Tailwind v4)
- **`packages/`** — Shared TypeScript, ESLint, Python tooling configs, and generated types

See [`AGENTS.md`](./AGENTS.md) for the full engineering context, build commands, conventions, and project state.

## Stack

| Layer    | Tech                                            | Where                |
| -------- | ----------------------------------------------- | -------------------- |
| Frontend | Next.js 15 (App Router) + TypeScript            | Vercel               |
| UI       | shadcn/ui + Tailwind v4                         | `apps/web`           |
| Backend  | FastAPI + Python 3.12 + async                   | Render (free tier)   |
| ORM      | SQLAlchemy 2.0 async + asyncpg                  | `apps/api`           |
| DB       | PostgreSQL 16 (Neon free tier)                  | Neon                 |
| Cache    | Redis (Upstash free tier)                       | Upstash              |
| MCP      | Python `mcp` SDK (planned)                      | `apps/api`           |
| AI       | Anthropic Claude (Phase 3)                      | `apps/api`           |
| Auth     | JWT (httpOnly cookies) + GitHub OAuth (Phase 1) | `apps/api`           |
| CI       | GitHub Actions                                  | `.github/workflows/` |
| Monorepo | Turborepo + pnpm workspaces                     | root                 |

## Status

**Phase 1 — Foundation (in progress)**

- [x] Monorepo skeleton with Turborepo + pnpm
- [x] Shared TypeScript, ESLint, Python configs
- [x] AGENTS.md / CLAUDE.md for AI-assisted dev
- [ ] `apps/api` FastAPI scaffold (in progress)
- [ ] `apps/web` Next.js scaffold (in progress)
- [ ] Auth flow (register, login, refresh)
- [ ] MCP server CRUD + minimal MCP gateway
- [ ] Deploy to Render + Vercel + Neon
- [ ] End-to-end smoke test

**Phase 2 — MCP Builder core** (next)
**Phase 3 — AI Description Engine**
**Phase 4 — Playground + Analytics**
**Phase 5 — Security Scanner + Polish**

## Quick start (after Phase 1 ships)

```bash
# Install everything
pnpm install

# Set up env files
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
# Edit the env files with your secrets

# Run database migrations
cd apps/api && alembic upgrade head && cd ..

# Start dev servers (backend on :8000, frontend on :3000)
pnpm dev
```

## License

UNLICENSED — internal project.

---

Built by Partha Saradhi Munakala · [PRD](../MCPForge_PRD.md) · [Engineering context](./AGENTS.md)
