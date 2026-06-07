# 04 — Feature 2: AI Description Engine (Parallel Wave 1)

> **When to use:** After F1 lands. Can run in parallel with F4, F5, F7.
> **Produces:** AI-enhanced tool descriptions, side-by-side review panel, quality scores.
> **Multi-provider:** Uses `openai` AsyncOpenAI with `base_url` override. Primary: DeepSeek V4 Flash.

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order, no skipping):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
4. .planning/09-INFRA-MIGRATIONS.md
5. AGENTS.md
6. .planning/features/03-FEATURE-AI-DESCRIPTION-ENGINE.md
   (your full spec — read in full)
7. .planning/research/LLM-PROVIDERS.md (multi-provider via
   OpenAI-compatible protocol — DEEP READ, this is critical)
8. .planning/research/ARXIV-2602-18914.md (the 4 quality
   dimensions)
9. .planning/research/CELERY-FASTAPI-SSE.md (for the Celery
   task + SSE pub/sub)
10. apps/api/app/services/ai_description_engine.py (does NOT
    exist yet — you will create)
11. apps/api/app/models/mcp_server.py (for the new fields
    added by migration 0002)
12. The `tools_config` JSON shape produced by F1 — see the
    F1 agent's report back, OR load any mcp_server row and
    inspect mcp_servers.tools_config in psql

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: F2 — AI Description Engine
Feature plan: .planning/features/03-FEATURE-AI-DESCRIPTION-ENGINE.md
Build order: Parallel Wave 1 (with F4, F5, F7)
Prerequisites: F1 must be merged. mcp_servers.tools_config schema
              is stable. Migration 0002 must be applied.

═══════════════════════════════════════════════════════════════════════
CRITICAL CONSTRAINTS (DO NOT VIOLATE)
═══════════════════════════════════════════════════════════════════════

1. **Use `openai` SDK, NOT `anthropic`.** AsyncOpenAI with
   `base_url` from env. Primary: DeepSeek V4 Flash. The
   `LLMClient` is in `app/core/llm_client.py` (renamed from
   the old `anthropic_client.py` — if it doesn't exist yet,
   create it; if it exists, USE IT, don't reimplement).

2. **Provider switching is via env vars only.** No code change.
   LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY.

3. **Use `response_format={"type": "json_object"}` for
   structured output.** Falls back to prompt engineering if
   provider doesn't support it (LLM_JSON_MODE=false).

4. **Quality scoring is heuristic, not LLM-based.** Regex
   patterns on the 4 dimensions from arxiv 2602.18914.

5. **Multi-provider pricing table is in `app/core/llm_client.py`
   `PROVIDER_PRICING`.** Add new models there.

6. **Cost tracking per server:** update
   `mcp_servers.ai_enhancement_cost_cents` after each call.

7. **Free tier quota:** decrement `users.ai_enhancement_credits`
   by 1 per enhancement (not per tool — per "build" call).
   Pro tier doesn't decrement.

═══════════════════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════════════════

D1. **app/core/llm_client.py** (if not already in Skeleton)
    - AsyncOpenAI with base_url from env
    - PROVIDER_PRICING dict
    - chat_completion method with structured JSON output
    - calculate_cost_cents method
    - Retry on 429/5xx via tenacity
    - Tests using mocked AsyncOpenAI (6+ tests)

D2. **app/core/celery_app.py** (NEW)
    - Celery 5.4+ with Redis broker
    - 5 queues: high_priority, default, ai, scanner, analytics
    - Beat schedule for partition creation + token cleanup
    - See research/CELERY-FASTAPI-SSE.md § 1 for full config

D3. **app/core/sse.py** (NEW or extended from Skeleton)
    - SSEManager with Redis pub/sub
    - subscribe / unsubscribe / publish methods
    - Tests using fakeredis (4+ tests)

D4. **app/services/ai_description_engine.py** (NEW)
    - AIDescriptionEngine class with enhance_tool method
    - Builds prompt with system + spec_context (cached) +
      tool spec + sibling tools + few-shot examples
    - Calls LLMClient.chat_completion with JSON mode
    - Parses response, scores quality, computes improvements
    - Calculates cost via LLMClient.calculate_cost_cents
    - Returns enhanced tool dict with metadata

D5. **app/services/ai_description/quality_scorer.py** (NEW)
    - QualityScorer with score(enhanced, original, all_tools)
    - 4-dimension heuristic scoring
    - Returns AIQualityScore with badge
    - 12+ tests covering each dimension

D6. **app/services/ai_description/prompts.py** (NEW)
    - SYSTEM_PROMPT (4-dimension quality framework)
    - USER_PROMPT_TEMPLATE (XML structure)
    - FEW_SHOT_EXAMPLES (3 examples)
    - 4+ tests

D7. **app/services/ai_description/tasks.py** (NEW)
    - enhance_all_descriptions Celery task
    - Parallel execution (semaphore 5)
    - Per-tool enhance + emit SSE event + write back to DB
    - Decrement user credits (free tier)
    - 6+ tests in eager mode

D8. **app/services/server_builder.py** (NEW)
    - Orchestrates the build pipeline (currently just runs
      AI; security scanner added in F5)

D9. **Schemas** in `apps/api/app/schemas/ai_description.py`:
    - AIQualityScore, AIImprovementItem, AIEnhancedTool
    - AIEnhancementRequest, AIEnhancementResponse
    - ToolAcceptRequest, BuildEvent

D10. **Endpoints** in `apps/api/app/api/v1/endpoints/build.py`:
    - POST /api/v1/servers/{id}/tools/enhance
    - POST /api/v1/servers/{id}/tools/enhance/{name}
    - POST /api/v1/servers/{id}/tools/accept
    - GET /api/v1/servers/{id}/build-status (SSE)
    - POST /api/v1/servers/{id}/build (initiate build)
    - Replaces the 501 stubs from Skeleton
    - 5+ tests

D11. **Wire into user model:**
    - `UserRepository.decrement_credits(user_id, amount)` method
    - Tests for credit decrement

D12. **Frontend types** in `apps/web/src/types/api.ts`:
    - AIQualityScore, AIImprovementItem, AIEnhancedTool,
      BuildEvent

D13. **Frontend hooks** in `apps/web/src/hooks/use-ai.ts`:
    - useEnhanceTools, useEnhanceSingleTool, useAcceptTools,
      useBuildStatusSSE

D14. **Frontend API client updates** in
    `apps/web/src/lib/api.ts`:
    - api.servers.enhanceTools, enhanceSingleTool, acceptTools

D15. **Frontend components** in
    `apps/web/src/components/builder/`:
    - quality-score-badge.tsx (color-coded)
    - quality-score-breakdown.tsx (4 dimensions)
    - inline-edit-field.tsx
    - description-monaco-editor.tsx
    - improvements-badges.tsx
    - revert-field-button.tsx
    - ai-cost-display.tsx
    - ai-credits-indicator.tsx
    - original-vs-enhanced.tsx
    - ai-review-tool-card.tsx
    - ai-review-panel.tsx (main container)

D16. **Update frontend tools page:**
    - `app/(dashboard)/servers/[slug]/tools/page.tsx` add
      "AI Review" tab (default) + "Manual Edit" tab (Monaco)

D17. **Tests:**
    - 35+ backend tests (across all new files)
    - ≥10 Vitest component tests for new components
    - 2 Playwright E2E specs (04-ai-review.spec.ts,
      05-ai-edit-single.spec.ts)

D18. **Tool edit history:**
    - Migration 0002 includes the tool_edit_history table
    - Whenever a tool's description/params is updated (via
      accept OR manual edit), insert a row
    - F6 Description Performance feature will read this

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE
═══════════════════════════════════════════════════════════════════════

1. Create app/core/llm_client.py (if not in Skeleton)
2. Create app/core/celery_app.py
3. Create app/core/sse.py
4. Create app/services/ai_description/prompts.py
5. Create app/services/ai_description/quality_scorer.py
6. Create app/services/ai_description_engine.py
7. Create app/services/ai_description/tasks.py
8. Create app/services/server_builder.py
9. Create app/schemas/ai_description.py
10. Create endpoints in app/api/v1/endpoints/build.py
11. Update UserRepository with decrement_credits
12. Add tests (35+)
13. Backend verification: pnpm type-check (no changes),
    uv run pytest, mypy, ruff all pass
14. Update frontend types + API client + hooks
15. Create frontend components
16. Update tools page with AI Review tab
17. Add Vitest + Playwright tests
18. Run full CI suite
19. Manual: run end-to-end with a real DeepSeek key

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[All from master template] Plus F2-specific:
[ ] app/core/llm_client.py uses openai SDK (NOT anthropic)
[ ] LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY env vars
    work — switch from deepseek to openai requires only env change
[ ] PROVIDER_PRICING table has entries for deepseek-v4-flash,
    gpt-4o, gpt-4o-mini, claude-sonnet-4-6, claude-haiku-4-5
[ ] Quality scoring is heuristic (regex/pattern), not LLM-based
[ ] Celery task uses semaphore(5) for parallel LLM calls
[ ] SSE events emit "ai_progress" and "tool_enhanced" with
    correct shape
[ ] Tool edit history rows inserted on every description change
[ ] Free tier credits decrement per "build" (not per tool)
[ ] mcp_servers.ai_enhancement_cost_cents updated after each call
[ ] 12-tool server with deepseek-v4-flash costs <$0.10
[ ] Average quality score on Stripe spec tools >80/100
[ ] No "anthropic" import anywhere in apps/api/app/

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

[Standard format]

Plus F2-specific:
## Provider config used (for the test run):
- LLM_PROVIDER: ...
- LLM_MODEL: ...
- 12-tool server cost (cents): ...
- Avg quality score: ...
- Tools scored Excellent (90+): <N>/12
- Tools scored Good (70-89): <N>/12
- Tools scored Fair (50-69): <N>/12
- Tools scored Poor (<50): <N>/12
```

---

## Reviewer's checklist

1. **`grep -r "anthropic" apps/api/app/`** — should return zero matches (only `anthropic` is in the test fixtures, not the code).
2. **`grep "openai" apps/api/pyproject.toml`** — should be present.
3. **Switch providers via env only** — test by setting `LLM_PROVIDER=openai LLM_MODEL=gpt-4o-mini` and re-running an enhancement; should work without code change.
4. **Cost tracking** — `SELECT ai_enhancement_cost_cents FROM mcp_servers WHERE id=...;` should show non-zero after a build.
5. **Quality scores** — verify the heuristic scorer works (mock the AI response, check the score).
6. **SSE works** — `curl -N` against `/build-status` and trigger a build; see events stream.
7. **Tool edit history** — accept some AI changes; verify rows in `tool_edit_history`.
