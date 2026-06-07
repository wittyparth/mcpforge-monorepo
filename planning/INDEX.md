# MCPForge Planning Hub

> **Audience:** AI coding agents (and humans) picking up MCPForge v1.0 implementation.
> **Source of truth:** [`../MCPForge_PRD.md`](../MCPForge_PRD.md) — this is the WHAT.
> **This folder:** the HOW, broken into atomic, verifiable feature plans.

---

## Quick Start for AI Agents

1. **Read first** → [`CURRENT-STATE.md`](./CURRENT-STATE.md) — exact state of the codebase right now (what exists, what doesn't, where to add).
2. **Read second** → [`00-MASTER-PLAN.md`](./00-MASTER-PLAN.md) — architecture, principles, build order, definition of done.
3. **Read third** → [`01-COMPETITOR-ANALYSIS.md`](./01-COMPETITOR-ANALYSIS.md) — what we are building against, the moat.
4. **Then** pick a feature from the Build Order and read its plan:
   - [`02-FEATURE-OPENAPI-INGESTION.md`](./features/02-FEATURE-OPENAPI-INGESTION.md) — Feature 1
   - [`03-FEATURE-AI-DESCRIPTION-ENGINE.md`](./features/03-FEATURE-AI-DESCRIPTION-ENGINE.md) — Feature 2
   - [`04-FEATURE-MCP-PLAYGROUND.md`](./features/04-FEATURE-MCP-PLAYGROUND.md) — Feature 3
   - [`05-FEATURE-MCP-GATEWAY.md`](./features/05-FEATURE-MCP-GATEWAY.md) — Feature 4
   - [`06-FEATURE-SECURITY-SCANNER.md`](./features/06-FEATURE-SECURITY-SCANNER.md) — Feature 5
   - [`07-FEATURE-ANALYTICS-DASHBOARD.md`](./features/07-FEATURE-ANALYTICS-DASHBOARD.md) — Feature 6
   - [`08-FEATURE-AUTH-TEAMS-MANAGEMENT.md`](./features/08-FEATURE-AUTH-TEAMS-MANAGEMENT.md) — Feature 7
5. **Reference** → [`09-INFRA-MIGRATIONS.md`](./09-INFRA-MIGRATIONS.md) for DB migrations, env vars, deployment.
6. **Reference** → [`research/`](./research/) for the deep research that backs each plan (MCP protocol, Claude API, arxiv paper, competitors, prompt engineering).

---

## Folder Layout

```
.planning/
├── INDEX.md                    ← you are here
├── CURRENT-STATE.md            ← codebase audit (what exists today, what doesn't)
├── 00-MASTER-PLAN.md           ← architecture, principles, build order, DoD
├── 01-COMPETITOR-ANALYSIS.md   ← competitive moat, feature comparison
├── 09-INFRA-MIGRATIONS.md      ← DB migrations, env vars, infra plan
├── features/                   ← one MD per PRD feature (7 total)
│   ├── 02-FEATURE-OPENAPI-INGESTION.md
│   ├── 03-FEATURE-AI-DESCRIPTION-ENGINE.md
│   ├── 04-FEATURE-MCP-PLAYGROUND.md
│   ├── 05-FEATURE-MCP-GATEWAY.md
│   ├── 06-FEATURE-SECURITY-SCANNER.md
│   ├── 07-FEATURE-ANALYTICS-DASHBOARD.md
│   └── 08-FEATURE-AUTH-TEAMS-MANAGEMENT.md
├── research/                   ← raw research (read-only references for AI agents)
│   ├── MCP-PROTOCOL.md         ← MCP spec, transports, JSON-RPC, official SDK
│   ├── LLM-PROVIDERS.md        ← Multi-provider via OpenAI-compatible protocol (DeepSeek, OpenAI, Anthropic, OpenCode Go, etc.)
│   ├── OPENAPI-INGESTION.md    ← openapi-spec-validator, prance, $ref resolution
│   ├── MCP-REFERENCE-SERVERS.md← Stripe/Cloudflare/Anthropic patterns
│   ├── ARXIV-2602-18914.md     ← the MCP quality study
│   └── CELERY-FASTAPI-SSE.md   ← async job patterns, SSE, WebSocket
├── diagrams/                   ← ASCII + mermaid diagrams (referenced from plans)
└── schemas/                    ← JSON Schemas, Pydantic examples, ERD (mermaid)
```

---

## Status of Each Plan

| Doc | Status | Ready to implement? |
|---|---|---|
| `00-MASTER-PLAN.md` | ✅ Complete | Yes — read first |
| `01-COMPETITOR-ANALYSIS.md` | ✅ Complete | Yes — context for design choices |
| `CURRENT-STATE.md` | ✅ Complete | Yes — tells you where to put code |
| `09-INFRA-MIGRATIONS.md` | ✅ Complete | Yes — DB + env changes needed by features |
| `02-FEATURE-OPENAPI-INGESTION.md` | ✅ Complete | Yes — Feature 1 |
| `03-FEATURE-AI-DESCRIPTION-ENGINE.md` | ✅ Complete | Yes — Feature 2 |
| `04-FEATURE-MCP-PLAYGROUND.md` | ✅ Complete | Yes — Feature 3 |
| `05-FEATURE-MCP-GATEWAY.md` | ✅ Complete | Yes — Feature 4 |
| `06-FEATURE-SECURITY-SCANNER.md` | ✅ Complete | Yes — Feature 5 |
| `07-FEATURE-ANALYTICS-DASHBOARD.md` | ✅ Complete | Yes — Feature 6 |
| `08-FEATURE-AUTH-TEAMS-MANAGEMENT.md` | ✅ Complete | Yes — Feature 7 |
| `research/*` | ✅ Complete | Reference only |

---

## Convention for Feature Plans

Every feature plan follows this exact structure (so AI agents can pattern-match):

```
# Feature N — <Name>

## 0. TL;DR
   3-5 bullets max. What is this feature. Why it matters. How long.

## 1. Goals & Non-Goals
   In-scope (must-have for v1.0) vs Out-of-scope (v1.1+).

## 2. User Stories
   Bullet list of "As a <user>, I can <action>, so that <benefit>".

## 3. Architecture Diagram
   ASCII or mermaid. Components, data flow, integration points.

## 4. Backend Changes
   4.1 New files (with full path, purpose, exports, dependencies)
   4.2 Modified files (with diff-level description)
   4.3 New SQLAlchemy models (with field-level schema)
   4.4 New Pydantic schemas (with field-level schema)
   4.5 New endpoints (method, path, request, response, status, errors)
   4.6 New services / business logic (pseudocode, not code)
   4.7 Background jobs / Celery tasks
   4.8 Security & rate limiting
   4.9 Test plan (unit, integration, e2e)

## 5. Frontend Changes
   5.1 New pages (with route, purpose, components used)
   5.2 New components (with props, state, behavior)
   5.3 New hooks (with signature, what they call, what they cache)
   5.4 New types / Zod schemas
   5.5 New dependencies to install
   5.6 State management updates
   5.7 Test plan (component, e2e with Playwright)

## 6. Database / Migration Plan
   New tables, indexes, partitions. Alembic migration naming.

## 7. Environment Variables
   New env vars (backend + frontend), defaults, validation.

## 8. Observability
   Logs, metrics, traces, Sentry. What's emitted when.

## 9. Edge Cases & Failure Modes
   What can go wrong. How we detect it. How we recover.

## 10. Definition of Done
   Bullet list of acceptance criteria that must all be true.

## 11. Build Sequence (for AI agents)
   Numbered steps. Each step is atomic. Each step verifiable.

## 12. Open Questions
   Things that need human input before / during build.
```

---

## How to Use These Plans

**For an AI agent picking up the work:**

1. **Don't start with code.** Read `00-MASTER-PLAN.md` to understand the build order and global principles.
2. **Read the feature's plan entirely** before touching anything.
3. **Check `CURRENT-STATE.md`** to confirm the files / patterns you'd be adding/modifying still look the same (it was written at one point in time; reality may have drifted).
4. **Read the relevant `research/` doc** if the plan references one (e.g., for AI Engine, read `research/ANTHROPIC-CLAUDE-API.md`).
5. **Follow the Build Sequence in the feature plan** — each step is a verifiable unit of work.
6. **At each step:** run lint + type-check + tests for the changed module, then mark step done.
7. **When the whole feature is done:** verify all items in "Definition of Done", then mark the feature complete in the master plan.

**For a human reviewer:**

Each plan is designed to be readable in 15-20 minutes. Diagrams, tables, and short bullets over prose.

---

## Editing This Folder

- This folder is `.gitignore`'d (`.planning/`). Changes here are local — never committed.
- If you want to persist a planning change across machines, commit it explicitly with `git add -f .planning/...` (override the gitignore).
- When a feature is fully shipped and accepted, **do not delete its plan** — leave it as historical record. Add a `✅ SHIPPED on YYYY-MM-DD` stamp to the top.

---

## Ground Rules for Implementation (from `00-MASTER-PLAN.md`)

1. **No stubs.** Every endpoint, every model, every UI state has real production logic. No `TODO` or `pass` in shipped code.
2. **No breaking changes to existing Phase 1 contracts.** The auth flow, server CRUD, and shared types package must keep working. New features extend, not replace.
3. **Strict typing, strict lint, strict tests.** Ruff `B/SIM/UP/ARG/I/N/W/E/F` (current rule set), mypy strict, TS strict + `noUncheckedIndexedAccess`. Every new service has a corresponding `test_*.py` with ≥1 happy + 2 edge cases.
4. **Production-grade error handling.** Every external call (Anthropic, target APIs, OpenAPI fetches) is wrapped with timeout, retry, structured logging, and a typed exception that the route handler maps to a proper HTTP / MCP error.
5. **Cost transparency.** AI calls and outbound HTTP are instrumented. Users see estimated cost in the UI; backend logs actual cost.
6. **Privacy by default.** No parameter values stored in analytics. No credentials in logs. No credentials in error responses. Ever.
7. **Graceful degradation.** When AI fails, the build still produces a server (with original descriptions + warning). When target API is down, the gateway returns a typed `UpstreamError` not a 500. When the playground can't connect, it shows actionable guidance.

---

*Maintained as part of the MCPForge monorepo. See `../AGENTS.md` for the repo-wide engineering context.*
