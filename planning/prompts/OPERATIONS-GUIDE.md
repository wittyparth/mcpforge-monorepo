# Operations Guide — How to Use These Prompts

> **This is the playbook for actually running MCPForge implementation.** Read this end-to-end before spawning the first agent. The prompts are the contracts; this guide is the procedure.

---

## TL;DR

```
Week 1:    Spawn AGENT 1 (Wave 0 + Skeleton). Wait. Review. Merge.
Week 2-3:  Spawn AGENT 2 (F1 OpenAPI). Wait. Review. Merge.
Week 3-5:  Spawn AGENTS 3-6 in PARALLEL (F2, F4, F5, F7). Wait. Review. Merge each.
Week 5-6:  Spawn AGENTS 7-8 in PARALLEL (F3, F6). Wait. Review. Merge each.
Week 6-7:  Spawn AGENT 9 (Integration & Launch). Wait. Review. Ship.
```

Total: **9 agents across ~6-7 weeks calendar**, depending on how aggressively you parallelize.

---

## 1. The 3 Phases, 9 Agents

### Phase 1: Foundations (WEEK 1)
**Agent 1 — Wave 0 + Skeleton** (sequential, blocks everything)
- Prompt: `02-WAVE-0-AND-SKELETON.md`
- Output: Argon2id, HIBP, CSRF, Sentry, rate limits, 8 migrations, all schemas, all 50+ route stubs, regenerated shared types, docker-compose
- Reviewer gate: open `/openapi.json`, verify 50+ paths, verify shared types are 2000+ lines, verify all migrations apply

### Phase 2: Critical Path (WEEKS 2-3)
**Agent 2 — F1 OpenAPI Ingestion** (sequential, blocks Phase 3)
- Prompt: `03-FEATURE-F1-OPENAPI.md`
- Output: Working "Create Server from URL" flow, `mcp_servers.tools_config` schema locked
- Reviewer gate: paste a public OpenAPI URL, see tools, save, verify tools_config JSON shape is stable (F2/F4/F5 will read this)

### Phase 3: Parallel Wave 1 (WEEKS 3-5)
**Agents 3, 4, 5, 6 — F2, F4, F5, F7** (4 in PARALLEL)
- Prompts:
  - `04-FEATURE-F2-AI-ENGINE.md`
  - `05-FEATURE-F4-GATEWAY.md`
  - `06-FEATURE-F5-SECURITY.md`  (will be in integration phase per the original plan)
  - `07-FEATURE-F7-AUTH-TEAMS.md`
- Each agent gets a fresh context. Each codes against the locked F1 schema.
- Reviewer gate: each PR passes its own Definition of Done

**Important:** F2, F4, F7 are independent and can be fully parallel. F5 (Security Scanner) is also independent. The dependency graph between them is:
- F2 reads `mcp_servers.tools_config` (from F1) ✓
- F4 reads `mcp_servers.tools_config` (from F1) + `credentials` (from F1) + `ServerConfigCache` (new) ✓
- F5 reads `mcp_servers.tools_config` (from F1) + analyzes it ✓
- F7 mostly independent (touches auth, billing, teams) — no F1 dependency

So all 4 can be truly parallel. Each agent does NOT need to wait for the others.

### Phase 4: Parallel Wave 2 (WEEKS 5-6)
**Agents 7, 8 — F3, F6** (2 in PARALLEL, after F4 is merged)
- Prompts:
  - `08-FEATURE-F3-PLAYGROUND.md`
  - `09-FEATURE-F6-ANALYTICS.md`
- F3 (Playground) needs F4 (Gateway) to be done
- F6 (Analytics) needs F4 (Gateway) to be done (gateway emits events)
- Both can be parallel with each other

### Phase 5: Integration & Launch (WEEKS 6-7)
**Agent 9 — Integration** (sequential, after all 7 features merged)
- Prompt: `10-INTEGRATION-AND-LAUNCH.md`
- Output: All 7 features working together, end-to-end manual testing, demo video, registry submissions, deployed
- Reviewer gate: full system works; demo video recorded; ready for HN launch

---

## 2. How to Spawn an Agent

### 2.1 The "How" depends on your tool

Different AI tools have different ways to spawn fresh agents. The key is **fresh context** — never resume a previous session for a new task.

**If you have access to a fresh-context agent tool (preferred):**
1. Open a brand new session
2. Paste the entire prompt file contents (the `.md` between the ``` fences)
3. Let the agent work
4. When the agent reports back, review the output

**If you're using a CLI tool (Aider, Cursor Composer, etc.):**
1. Start a fresh project/session for each agent
2. Add the `.planning/` folder to the context (via "include these files" or by running in the repo)
3. Paste the prompt
4. The agent has access to the codebase

**If you're using Claude.ai or similar web UI:**
1. Start a new chat (don't continue an old one)
2. Paste the prompt
3. Attach the `.planning/` folder as a knowledge source if your tool supports it

**Critical rule:** NEVER resume a previous session for a new agent. The whole point is fresh context.

### 2.2 What to include with the prompt

The prompt file is self-contained (it tells the agent to read the `.planning/` files). Just paste it. The agent will read what it needs.

If your tool requires you to provide context manually, also attach:
- The full `.planning/` folder (or at least `INDEX.md`, `CURRENT-STATE.md`, `00-MASTER-PLAN.md`, `09-INFRA-MIGRATIONS.md`, the specific feature plan, and the relevant research docs)

---

## 3. What to Do While the Agent Runs

**Time estimates per agent:**
- Wave 0 + Skeleton: 1 week
- F1 OpenAPI: 4-5 days
- F2/F4/F5/F7 (parallel): 4-7 days each
- F3/F6 (parallel): 5-7 days each
- Integration: 1 week

**What you're doing during this time:**
1. **Monitor progress.** The agent should report its current step every few hours. If it goes silent for >4 hours, ping it.
2. **Check intermediate outputs.** When the agent says "migrations done", verify by running `alembic upgrade head` yourself. When it says "endpoint tests pass", run the test command.
3. **Don't micromanage.** The agent is doing real engineering. Trust the build sequence. Only intervene if the agent is clearly off-track.
4. **Do NOT spawn new agents while previous ones are running** (unless explicitly parallel — see § 4).

---

## 4. When to Spawn in Parallel

**Safe to spawn in parallel:**
- All 4 Phase 3 agents (F2, F4, F5, F7) ONCE F1 is merged
- The 2 Phase 4 agents (F3, F6) ONCE F4 is merged

**NEVER spawn in parallel:**
- Wave 0 and F1 (Wave 0 must land first)
- F1 and any of F2/F4/F5 (F1 must land first)
- F4 and F3/F6 (F4 must land first)

**Practical recommendation:** Use 4 separate fresh-context sessions for Phase 3. They can all be running at the same time. The agents are independent — each works on their own files, their own routes, their own frontend components. The only shared thing is `mcp_servers.tools_config` (locked by F1).

---

## 5. How to Review an Agent's PR

When the agent reports `## Status: COMPLETE`, do this checklist BEFORE merging.

### 5.1 Read the report
Look at:
- Files created (should match the plan)
- Tests passing (should be ≥the number specified)
- Definition of Done: <X>/<Y> items checked (should be Y/Y)
- Open issues (should be empty or "none")

If anything is "PARTIAL" or "BLOCKED", ask the agent to complete before reviewing further.

### 5.2 Run the verification commands yourself
```bash
# From repo root
cd /Users/parthu/Coding/MCP/mcpforge-monorepo
pnpm type-check
pnpm lint
cd apps/api && uv run pytest --cov=app
cd apps/web && pnpm test
cd apps/api && uv run mypy app
cd apps/api && uv run ruff check app
```

ALL must pass. If any fail, send the agent back.

### 5.3 Spot-check specific files
Don't read every line. Sample 3-5 files at random and check:
- No `pass`, `TODO`, `NotImplementedError` in production paths
- No `Any` in Python, no `any` in TypeScript
- No `print()`, no `os.environ` direct reads
- Structured logging with `logger = get_logger(__name__)`
- Error responses use `AppError` subclasses
- Tests cover edge cases listed in the plan's "Edge Cases" section

### 5.4 Integration check
After merging, in dev mode:
- Manually exercise the feature (paste a real OpenAPI URL, see tools)
- Run the previous features' smoke tests (no regression)

If integration breaks, the next agent will report it. Fix forward.

### 5.5 The "10-second smoke test"

If you have 10 seconds, the minimum-viable review is:
1. `pnpm type-check && pnpm lint` — passes?
2. `uv run pytest apps/api/tests/test_<that_feature>.py` — passes?
3. Open one production file from the PR — does it look like real engineering, or does it have stubs?

If all 3 yes, merge. The Definition of Done checklist in the prompt is your deeper review.

---

## 6. Cost & Time Budget

### 6.1 Token cost per agent (approximate)
- Wave 0 + Skeleton: ~50-100K tokens
- Each feature (F1-F7): ~30-80K tokens each
- Integration: ~30-50K tokens

Total: ~500K-1M tokens across all 9 agents.

If your tool bills per million tokens, expect $10-50 in API costs for the whole project. (The human review time is more expensive than the API costs.)

### 6.2 Wall clock time
- Wave 0 + Skeleton: 1 week (with full attention)
- F1: 4-5 days
- F2/F4/F5/F7 parallel: 4-7 days wall clock (longest of the 4)
- F3/F6 parallel: 5-7 days wall clock (longest of the 2)
- Integration: 1 week

If you do all phases back-to-back: **6-7 weeks** for v1.0.

If you spread it out (one feature per week): **8-10 weeks**.

### 6.3 When to NOT use parallel agents
- If you don't have a way to monitor 4 agents in parallel
- If you can't review 4 PRs in a reasonable time
- If your team is small (1-2 people) — review bandwidth is the bottleneck

Sequential is fine too. It just takes longer.

---

## 7. Failure Recovery

### 7.1 Agent's PR is broken

**Symptom:** CI fails; spot-check reveals stubs or wrong implementation.

**Response:**
1. Don't merge.
2. Reply to the agent (in its session) with the specific failure: "Your build step 14 doesn't actually call Claude; the response_text is just stubbed. Re-do step 14 and re-submit."
3. Agent re-runs the failing step and resubmits.
4. Re-review.

### 7.2 Agent went off-script

**Symptom:** Agent used `anthropic` SDK, or built a new top-level package, or skipped migrations.

**Response:**
1. Identify which constraint was violated (the prompt lists 12 hard constraints).
2. Send the agent a clear message: "You violated constraint #1 (use `openai` SDK, not `anthropic`). Re-do the LLM client using `openai` AsyncOpenAI with `base_url`. Do not change other files."
3. Agent fixes the violation. Re-review.

### 7.3 Agent is stuck for >24 hours

**Symptom:** Agent hasn't reported progress; you ask for status and get a confused response.

**Response:**
1. Kill the session.
2. Update the prompt with the missing detail (e.g., "Note: when implementing X, use approach Y because Z").
3. Spawn a new agent.
4. The new agent has fresh context — it will likely succeed where the old one floundered.

### 7.4 Two parallel agents produce incompatible code

**Symptom:** F2's tests fail because F4 changed the gateway response shape, OR F4's tests fail because F2 added a new model field.

**Response:**
1. This is the cost of parallelism. Expected occasionally.
2. Identify the interface (model field, response shape) that drifted.
3. Either:
   a. Update one of the agents' prompts to match the other's interface, OR
   b. Merge both PRs and let the integration agent reconcile
4. The "locked Skeleton" minimizes this. If it happens, the Skeleton wasn't detailed enough.

### 7.5 The Skeleton wasn't detailed enough

**Symptom:** Multiple agents ask "what should this look like?" for things the Skeleton should have specified.

**Response:**
1. Pause the parallel agents.
2. Update the Skeleton (add the missing schema, model field, or route signature).
3. Have the agents regenerate from the updated Skeleton.
4. Resume.

This is why the Skeleton phase is so important. Spend the time upfront.

---

## 8. After All Features Land

After Agent 9 (Integration) finishes:
- Run the full system in dev mode
- Record the 90-second demo video
- Submit to Smithery and Glama
- Write the technical blog post
- Prepare the HN launch

**You, the human, do these last 4 steps.** The agent can't make a video. The agent can't craft a HN post in your voice.

---

## 9. Quick Reference: Prompt Cheat Sheet

| Step | Prompt file | Agent | Wall time |
|---|---|---|---|
| 1 | `02-WAVE-0-AND-SKELETON.md` | Sequential | 1 week |
| 2 | `03-FEATURE-F1-OPENAPI.md` | Sequential | 4-5 days |
| 3a | `04-FEATURE-F2-AI-ENGINE.md` | Parallel w/ 3b, 3c, 3d | 5-7 days |
| 3b | `05-FEATURE-F4-GATEWAY.md` | Parallel w/ 3a, 3c, 3d | 6-8 days |
| 3c | `06-FEATURE-F5-SECURITY.md` | Parallel w/ 3a, 3b, 3d | 4-5 days |
| 3d | `07-FEATURE-F7-AUTH-TEAMS.md` | Parallel w/ 3a, 3b, 3c | 10-14 days |
| 4a | `08-FEATURE-F3-PLAYGROUND.md` | Parallel w/ 4b (after 3b) | 5-7 days |
| 4b | `09-FEATURE-F6-ANALYTICS.md` | Parallel w/ 4a (after 3b) | 5-6 days |
| 5 | `10-INTEGRATION-AND-LAUNCH.md` | Sequential | 1 week |

---

## 10. Common Mistakes (don't do these)

1. **Don't resume an old session** for a new agent. Fresh context every time.
2. **Don't skip the Skeleton.** It's the contract that unblocks parallel work.
3. **Don't skip the review** because the agent said "COMPLETE". Verify.
4. **Don't paste a paraphrased version** of the prompt. The wording has been tuned.
5. **Don't spawn 4 agents at once** if you can't monitor 4 in parallel. Sequential is fine.
6. **Don't merge a PR with TODOs.** Send it back.
7. **Don't run agents in production.** They should run in dev mode, on a branch, with their work in a PR.
8. **Don't commit secrets.** If the agent accidentally commits a `.env`, rotate the keys.

---

*This guide is part of the `.planning/` folder (gitignored). Update it as you learn what works.*
