# 08 — Feature 3: Browser MCP Playground (Parallel Wave 2)

> **When to use:** After F4 lands. Can run in parallel with F6.
> **Produces:** A browser-based MCP client that tests tools in real-time without Claude Desktop.

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
4. AGENTS.md
5. .planning/features/04-FEATURE-MCP-PLAYGROUND.md
6. .planning/research/MCP-PROTOCOL.md (WebSocket transport)
7. .planning/research/MCP-REFERENCE-SERVERS.md
8. .planning/research/CELERY-FASTAPI-SSE.md (WebSocket section)
9. apps/api/app/playground/ws.py (current echo stub)
10. apps/api/app/gateway/tool_dispatcher.py (F4's, you'll
    reuse for actual execution)
11. apps/api/app/gateway/response_handler.py (F4's, reuse)
12. The mcp_servers.tools_config from F1
13. apps/web/src/app/(dashboard)/servers/[slug]/ (server detail
    page from F1)

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: F3 — Browser MCP Playground
Feature plan: .planning/features/04-FEATURE-MCP-PLAYGROUND.md
Build order: Parallel Wave 2 (with F6)
Prerequisites: F4 must be merged (gateway protocol stable).

═══════════════════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════════════════

D1. **REWRITE apps/api/app/playground/ws.py:**
    - Full MCP-over-WebSocket handler
    - JWT auth via token query param
    - tools/list on connect
    - tools/call dispatches via F4's tool_dispatcher
    - Ephemeral in-memory sessions (no persistence)
    - 10+ tests

D2. **app/schemas/playground.py** — PlaygroundSessionInfo,
    ShareTestRequest
D3. **Pre-deployment mode:** if server status != "active",
    load draft tools_config and allow testing against the
    user's own server
D4. **Post-deployment mode:** tools come from the deployed
    mcp_servers.tools_config (with AI-enhanced descriptions)
D5. **Share Test functionality:**
    - POST /api/v1/servers/{slug}/playground/share with
      tool_name + parameters
    - Returns shareable URL (params stripped of credentials)
    - URL expires in 7 days
    - 4+ tests
D6. **Frontend deps:** react-resizable-panels (for 4-panel
    layout)
D7. **Frontend route:**
    `/dashboard/servers/[slug]/playground/page.tsx`
D8. **Frontend components** in
    `apps/web/src/components/playground/`:
    - playground-page.tsx (4-panel container using
      react-resizable-panels)
    - tool-browser.tsx (left panel)
    - tool-form.tsx (center-top: auto-generated form from
      inputSchema)
    - response-viewer.tsx (center-bottom: JSON with syntax
      highlighting)
    - call-log.tsx (right panel)
    - json-viewer.tsx (Monaco-based)
    - share-test-button.tsx
    - form-field-generators/ (string-field, number-field,
      boolean-field, select-field, array-field, object-field,
      json-field) — auto-form generation from JSON Schema
D9. **Frontend hook** in `apps/web/src/hooks/use-playground.ts`:
    - usePlayground(serverSlug) — WebSocket session, tool list,
      call tool, call log, response state
D10. **Tests:** ≥10 backend, ≥5 Vitest, 2 Playwright
    (08-playground.spec.ts, 09-playground-share.spec.ts)
D11. **Auto-form generation:** given a tool's inputSchema
    (JSON Schema), generate form fields. Support: string,
    number, integer, boolean, array, object, enum (via
    select), nested objects (recursive), complex types
    (fallback to JSON textarea)

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE
═══════════════════════════════════════════════════════════════════════

1. Schemas (playground.py)
2. REWRITE app/playground/ws.py
3. Share Test endpoint
4. Backend tests
5. Install react-resizable-panels
6. Frontend usePlayground hook
7. Auto-form generator (start with primitives, then add
   array/object)
8. Playground components
9. Playground route
10. Add "Open Playground" button to server detail page
11. Vitest + Playwright
12. Full CI
13. Manual: deploy a server, open playground, call a tool,
    see response

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[All from master template] Plus F3-specific:
[ ] apps/api/app/playground/ws.py REWRITTEN with full MCP
[ ] Pre-deployment mode works (test against draft server)
[ ] Post-deployment mode works (test against live gateway)
[ ] Share Test URL works (load in incognito, pre-fills form,
    no credentials in URL)
[ ] Auto-form handles all JSON Schema types
[ ] Required fields marked with *
[ ] Response shows: raw JSON, formatted view, timing, status
[ ] Call log persists during session (cleared on disconnect)
[ ] Error display: auth fail, network error, schema
    validation — all actionable
[ ] 4-panel layout resizable
[ ] 10+ backend tests, 5+ Vitest, 2 Playwright

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

[Standard format]
```

---

## Reviewer's checklist

1. **Pre-deployment mode** — for a server with status="review", open playground, call a tool, see response.
2. **Post-deployment mode** — for a server with status="active", same flow.
3. **Share Test** — generate a share URL, copy it, open in incognito, verify tool and parameters are pre-filled.
4. **Form auto-generation** — test with a tool that has nested objects, arrays, enums.
5. **WebSocket reconnection** — kill the connection, verify auto-reconnects.
6. **No analytics pollution** — verify tool_calls table has 0 new rows for playground calls.
