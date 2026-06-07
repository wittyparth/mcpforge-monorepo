# 03 — Feature 1: OpenAPI Ingestion (Sequential, ~5 days)

> **When to use:** AFTER Wave 0 + Skeleton is merged. Sequential — blocks F2/F4/F5.
> **Produces:** A working "Create Server from OpenAPI URL" flow: fetch, validate, parse, present Tool Workspace, save to DB.
> **Why this is sequential:** Its `tools_config` JSON schema is the contract F2 (AI), F4 (Gateway), and F5 (Security) all read. Lock this first.

---

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order, no skipping):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
4. .planning/09-INFRA-MIGRATIONS.md
5. AGENTS.md
6. .planning/features/02-FEATURE-OPENAPI-INGESTION.md (your full
   spec — read in full, this is the source of truth)
7. .planning/research/OPENAPI-INGESTION.md (openapi-spec-validator,
   prance, $ref resolution reference)
8. .planning/research/MCP-PROTOCOL.md (for the tool definition
   schema format)
9. apps/api/app/main.py (current app factory — you'll extend)
10. apps/api/app/api/v1/endpoints/servers.py (current server
    CRUD — you'll extend with new build endpoint)
11. apps/api/app/api/v1/router.py (to see how routes are mounted)
12. apps/api/app/schemas/mcp_server.py (current MCPServerCreate —
    you'll reference and extend)
13. apps/api/app/services/mcp_server_service.py (current service —
    you'll reference patterns)
14. apps/web/src/app/(dashboard)/servers/new/page.tsx (current
    create form — you'll replace with multi-step flow)
15. apps/web/src/lib/api.ts (current API client — you'll extend)
16. apps/web/src/hooks/use-servers.ts (current hooks — you'll
    extend)

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: F1 — OpenAPI Spec Ingestion
Feature plan: .planning/features/02-FEATURE-OPENAPI-INGESTION.md
Build order: 1 (this is the second agent to run, after Wave 0+
              Skeleton. F1 is sequential because it produces the
              contract that F2/F4/F5 read.)
Prerequisites: Wave 0+Skeleton must be merged. Migrations 0002-
              0009 must be applied. /openapi.json must list the
              new endpoints. shared-types/api-types.d.ts must be
              regenerated.

═══════════════════════════════════════════════════════════════════════
WHAT YOU'RE BUILDING
═══════════════════════════════════════════════════════════════════════

A user pastes an OpenAPI URL (or uploads a file), the system
fetches + validates + parses it, shows them a Tool Workspace
where they can pick which endpoints become MCP tools, and saves
the curated config to `mcp_servers.tools_config`. After this
feature, the user can see their server with the tools listed.
To make it actually callable, F2 (AI enhancement) and F4
(gateway) need to run.

This feature does NOT include the AI description engine or the
gateway execution — those are F2 and F4. This feature gets the
shape right and locks the contract.

═══════════════════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════════════════

D1. **Backend service layer:**
    - `apps/api/app/services/openapi_fetcher.py` — fetches
      OpenAPI from URL, validates it, stores in R2, dedups
      by hash.
    - `apps/api/app/services/spec_analyzer.py` — extracts MCP
      tool definitions, resolves $refs, handles circular refs.
    - `apps/api/app/services/tool_generator.py` — converts
      user-curated tool list into the canonical
      `mcp_servers.tools_config` JSON.
    - `apps/api/app/services/credential_service.py` — Fernet
      encryption for API credentials.
    - `apps/api/app/core/encryption.py` — already created in
      Wave 0; verify it works.
    - `apps/api/app/core/r2_client.py` — async R2 (S3-
      compatible) client via aioboto3.

D2. **Backend schemas:**
    - `apps/api/app/schemas/openapi_spec.py` — full set per
      the feature plan § 4.4.
    - `apps/api/app/schemas/credential.py`
    - `apps/api/app/schemas/tool.py`

D3. **Backend endpoints:**
    - `apps/api/app/api/v1/endpoints/specs.py` — replaces the
      501 stub from Wave 0.
    - `apps/api/app/api/v1/endpoints/tools.py` — replaces stub.
    - `apps/api/app/api/v1/endpoints/credentials.py` — replaces
      stub.
    - `apps/api/app/api/v1/endpoints/build.py` — replaces stub.
      Includes the SSE endpoint
      `GET /api/v1/servers/{id}/build-status` for build
      progress (just emits "parsing complete" for now; F2 will
      wire up AI events).

D4. **Backend repository:**
    - `apps/api/app/repositories/spec_repo.py`
    - `apps/api/app/repositories/credential_repo.py`

D5. **Backend tests:** ≥40 tests per the feature plan § 4.8.
    Use `respx` for httpx, `moto` for R2, real DB via
    conftest fixtures.

D6. **Frontend types and API client:**
    - Update `apps/web/src/types/api.ts` to add ToolDefinition,
      SpecUploadResponse, SpecValidationError,
      ToolSelectionRequest, ToolResponse, CredentialResponse.
    - Update `apps/web/src/lib/validators.ts` to add
      specUrlSchema, toolSelectionSchema.
    - Update `apps/web/src/lib/api.ts` to add `api.specs.*`,
      `api.servers.enhance*` (just type signatures; F2 wires
      behavior), `api.servers.tools.*`,
      `api.servers.credentials.*`, `api.servers.build`.

D7. **Frontend hooks:**
    - `apps/web/src/hooks/use-spec.ts` (useFetchSpec,
      useUploadSpec, useSpec, useSelectTools)
    - `apps/web/src/hooks/use-tools.ts` (useServerTools,
      useUpdateTool)
    - `apps/web/src/hooks/use-credentials.ts` (useAddCredential,
      useTestCredential, useCredentials, useDeleteCredential)
    - `apps/web/src/hooks/use-build-status.ts` (SSE consumer)

D8. **Frontend shared components:**
    - `apps/web/src/components/shared/http-method-badge.tsx`
      (color-coded GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS)
    - `apps/web/src/components/shared/copy-to-clipboard.tsx`
    - `apps/web/src/components/shared/empty-state.tsx`
    - `apps/web/src/components/shared/loading-spinner.tsx`
    - Add 4 new shadcn primitives via `pnpm dlx shadcn@latest
      add tabs scroll-area switch toggle-group` — verify these
      work with the existing Tailwind v4 + Radix setup.

D9. **Frontend builder components** in
    `apps/web/src/components/builder/`:
    - `spec-input.tsx` (tabs: URL vs Upload)
    - `spec-url-input.tsx`
    - `spec-upload-input.tsx` (drag-drop)
    - `spec-validation-errors.tsx`
    - `tool-workspace.tsx` (main container)
    - `tool-tag-group.tsx` (collapsible section per tag)
    - `tool-row.tsx` (checkbox + method badge + path +
      description + warnings)
    - `tool-warnings.tsx`
    - `tool-summary.tsx`
    - `large-spec-warning.tsx`
    - `server-config-form.tsx`
    - `auth-scheme-selector.tsx`
    - `credential-input.tsx`
    - `credential-test-result.tsx`
    - `build-progress-modal.tsx` (SSE consumer; just shows
      "parsing complete" for now)
    - `build-step-indicator.tsx`

D10. **Frontend route update:** Replace
     `apps/web/src/app/(dashboard)/servers/new/page.tsx` with
     a multi-step flow: spec input → tool workspace → server
     config → build progress. The page should call
     `useFetchSpec` → on success navigate to step 2 with the
     parsed tools → user toggles tools + enters config →
     `useSelectTools` → on success `useBuild` → SSE
     consumption → on success redirect to
     `/dashboard/servers/{slug}`.

D11. **Frontend server detail:** Replace
     `apps/web/src/app/(dashboard)/servers/[slug]/page.tsx`
     (currently a "Coming soon" placeholder) with a real
     tabbed layout. F1 only fills the "Tools" tab; other tabs
     are placeholders for F2/F3/F4/F6.

D12. **Tests:**
    - Vitest component tests for all new components (≥15
      tests)
    - Playwright E2E (≥3 specs):
      - `01-create-from-url.spec.ts`
      - `02-upload-spec.spec.ts`
      - `03-invalid-spec.spec.ts`

D13. **Regenerate shared types:** After backend changes are
     complete, regenerate `packages/shared-types/api-types.d.ts`.
     Run `pnpm type-check` in apps/web. The frontend should
     now have full type safety against the new endpoints.

═══════════════════════════════════════════════════════════════════════
HARD CONSTRAINTS (non-negotiable)
═══════════════════════════════════════════════════════════════════════

[All constraints from master template — REPEAT HERE]

Plus F1-specific:
- R2 (not S3): use `aioboto3` with `endpoint_url` from
  `R2_ACCOUNT_ID`
- SSRF prevention: validate URL is HTTPS and not internal IP
  before fetching
- YAML parsing: `yaml.safe_load`, NEVER `yaml.load`
- Tool name uniqueness: deduplicate by suffixing `_2`, `_3`
- Parameter name collision: prefix query params with
  `query_`, body params with `body_` if there's a name clash
  with path params
- Default selection: GET selected, DELETE deselected, others
  selected (with override)
- 200+ endpoint warning: show a confirmation modal before
  committing to "all selected"

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE (follow IN ORDER)
═══════════════════════════════════════════════════════════════════════

Phase A — Encryption + R2 (1 day):
  1. Verify `app/core/encryption.py` (from Wave 0) has
     `encrypt(plaintext: str) -> bytes` and
     `decrypt(ciphertext: bytes) -> str`. Add tests.
  2. Create `app/core/r2_client.py` (async via aioboto3).
  3. Add tests for R2Client (use moto).

Phase B — OpenAPI fetcher (1 day):
  4. Create `app/services/openapi_fetcher.py` per the plan.
  5. Add tests: 8 tests using respx + a sample spec fixture.
  6. Save sample OpenAPI fixtures in
     `apps/api/tests/fixtures/openapi/` (petstore, github-
     like, malformed, 2.0, etc.)

Phase C — Spec analyzer (1 day):
  7. Create `app/services/spec_analyzer.py`.
  8. Add tests: 12 tests covering all edge cases.
  9. Verify circular $ref handling.

Phase D — Tool generator + credentials (1 day):
  10. Create `app/services/tool_generator.py`.
  11. Create `app/services/credential_service.py`.
  12. Create `app/repositories/spec_repo.py` and
      `app/repositories/credential_repo.py`.
  13. Add tests: 6+6 = 12 tests.

Phase E — Schemas, routes, models (1 day):
  14. Create all schemas per plan § 4.4.
  15. Create endpoints (replace the 501 stubs from Wave 0).
  16. Update `app/api/v1/router.py` to include the new
      routers.
  17. Add endpoint tests: 10+ tests in
      `tests/test_specs_endpoints.py`.
  18. Run `alembic upgrade head` to ensure migration 0009
      (spec_sources) applies.

Phase F — Backend verification (1 day):
  19. Start backend locally: `uv run uvicorn app.main:app`.
  20. Test via curl:
      - POST /api/v1/specs/fetch with a public OpenAPI URL
      - GET /api/v1/specs/{id}
      - POST /api/v1/specs/{id}/select-tools
      - POST /api/v1/servers/{id}/credentials
      - POST /api/v1/servers/{id}/credentials/test
      - GET /api/v1/servers/{id}/tools
      - PATCH /api/v1/servers/{id}/tools/{name}
  21. Verify all return correct shapes.
  22. Verify `curl http://localhost:8000/openapi.json` lists
      the new endpoints.

Phase G — Frontend types + API client (0.5 day):
  23. Update `apps/web/src/types/api.ts`.
  24. Update `apps/web/src/lib/validators.ts`.
  25. Update `apps/web/src/lib/api.ts`.
  26. Run `pnpm type-check` — must pass.

Phase H — Frontend hooks (0.5 day):
  27. Create the 4 new hooks files.
  28. Run `pnpm type-check` — must pass.

Phase I — Frontend components (2 days):
  29. Add the 4 shadcn primitives via `pnpm dlx shadcn@latest add`.
  30. Create all 16 builder components.
  31. Create the 4 shared components.
  32. Write Vitest tests for each (≥15 tests).

Phase J — Frontend pages (0.5 day):
  33. Rewrite `app/(dashboard)/servers/new/page.tsx` as multi-
      step flow.
  34. Rewrite `app/(dashboard)/servers/[slug]/page.tsx` with
      tabs (Tools tab filled; other tabs are placeholders).

Phase K — E2E (0.5 day):
  35. Add `apps/web/playwright.config.ts` (extends existing).
  36. Add the 3 Playwright specs.
  37. Run `pnpm exec playwright test` — must pass.

Phase L — Final CI (0.5 day):
  38. Run full CI suite from repo root.
  39. All checks pass.

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[All from master template] Plus F1-specific:
[ ] apps/api/pyproject.toml has openapi-spec-validator, prance,
    cryptography, aioboto3, tenacity
[ ] apps/web/package.json has @monaco-editor/react,
    react-resizable-panels, @radix-ui/react-{tabs,scroll-area,
    switch,toggle-group} (some may be in F2, install what's
    needed for F1)
[ ] Migration 0009_add_spec_sources.py created and reversible
[ ] apps/api/app/models/spec.py created; SpecSource exported
[ ] apps/api/app/core/encryption.py works (verify with tests)
[ ] apps/api/app/core/r2_client.py works (verify with tests)
[ ] apps/api/app/services/openapi_fetcher.py: 8 tests passing
[ ] apps/api/app/services/spec_analyzer.py: 12 tests passing
[ ] apps/api/app/services/tool_generator.py: 6 tests passing
[ ] apps/api/app/services/credential_service.py: 6 tests
    passing
[ ] apps/api/app/api/v1/endpoints/specs.py: 10 tests passing
[ ] apps/api/app/api/v1/endpoints/tools.py: 3 tests passing
[ ] apps/api/app/api/v1/endpoints/credentials.py: 4 tests
    passing
[ ] apps/api/app/api/v1/endpoints/build.py: 5 tests passing
[ ] Frontend: 16 builder components + 4 shared components
[ ] Frontend: 4 hooks files
[ ] Frontend: 3 Playwright E2E specs
[ ] Frontend: ≥15 Vitest component tests
[ ] /openapi.json lists all new endpoints
[ ] packages/shared-types/api-types.d.ts regenerated
[ ] pnpm type-check passes
[ ] mypy --strict passes
[ ] ruff check passes
[ ] pnpm lint passes
[ ] No credentials in any log line
[ ] Manual: paste https://petstore3.swagger.io/api/v3/openapi.json
    → see ~19 tools grouped by tag → toggle DELETE off →
    configure auth (none for petstore) → click Build → see
    server detail with tools listed

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

[Standard report format from master template]

Plus F1-specific:
## tools_config schema (this is the contract F2/F4/F5 will code
against — verify it's stable):
```json
{
  "version": 1,
  "generated_at": "...",
  "generator": "spec_analyzer_v1",
  "tools": [
    {
      "name": "...",
      "description": "...",
      "method": "GET",
      "path": "...",
      "tags": [...],
      "inputSchema": { ... },
      "annotations": { "readOnlyHint": ..., ... },
      "request_body_schema": ...,
      "response_schemas": { ... },
      "security_requirements": [...]
    }
  ]
}
```
This shape MUST NOT CHANGE without coordinating with F2/F4/F5.
```

---

## Reviewer's checklist

Before unblocking the parallel F2/F4/F5 agents, verify:

1. **Tool workspace renders** for a real OpenAPI URL (test with petstore).
2. **tools_config JSON shape** is documented above and committed to `mcp_servers.tools_config`.
3. **All 3 endpoints (fetch, upload, select-tools)** work via curl.
4. **Credentials** can be added and tested without leaking.
5. **Shared types regenerated** and apps/web type-checks.
6. **All 50+ tests pass** for F1 specifically.
7. **No regressions** in Wave 0 tests.

If any of these fail, do NOT start the parallel Wave 1 agents. Send F1 agent back.
