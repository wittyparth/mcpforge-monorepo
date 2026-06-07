# Implementation Prompts — Strategy & Index

> **This folder contains the prompts you paste into fresh AI agents to implement MCPForge.** Each file is a self-contained prompt. The agent reads it, follows the build sequence, produces a PR, reports back.
>
> **Why this folder exists:** A fresh agent has 0% context. These prompts ARE the context. They reference the `.planning/` folder (which is the design rationale) and give the agent everything it needs to produce production-grade code.

---

## The Strategy in One Paragraph

MCPForge is too large to build in one context window without quality degrading. We split the work into **3 sequential phases** with **parallel agents within each phase**. Each phase produces a stable artifact (skeleton, deployed features, integrated system) that unblocks the next phase. The skeleton is the secret weapon: once the schemas, models, and route stubs are locked, parallel agents can't drift.

---

## Dependency Graph (THE most important diagram)

```
                          ┌────────────────────────────────────┐
                          │  AGENT 1 (sequential, 1 week)       │
                          │  Wave 0 + The Skeleton              │
                          │  → 00-WAVE-0-AND-SKELETON.md         │
                          └────────────────┬───────────────────┘
                                           │
                                           ▼
                          ┌────────────────────────────────────┐
                          │  AGENT 2 (sequential, 4-5 days)    │
                          │  Feature 1: OpenAPI Ingestion      │
                          │  → 02-FEATURE-F1-OPENAPI.md         │
                          └────────────────┬───────────────────┘
                                           │
            ┌──────────────────────────────┼──────────────────────────────┐
            │                              │                              │
            ▼                              ▼                              ▼
   ┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
   │  AGENT 3 (parallel) │     │  AGENT 4 (parallel) │     │  AGENT 5 (parallel) │
   │  F2: AI Engine      │     │  F4: MCP Gateway    │     │  F7: Auth/Teams     │
   │  → 03-FEATURE-      │     │  → 05-FEATURE-      │     │  → 08-FEATURE-      │
   │    F2-AI-ENGINE.md  │     │    F4-GATEWAY.md    │     │    F7-AUTH-TEAMS.md │
   └────────────────────┘     └─────────┬──────────┘     └────────────────────┘
                                        │
                              ┌─────────┴──────────┐
                              │                    │
                              ▼                    ▼
                     ┌────────────────────┐  ┌────────────────────┐
                     │  AGENT 6 (parallel) │  │  AGENT 7 (parallel) │
                     │  F3: Playground     │  │  F6: Analytics      │
                     │  → 04-FEATURE-      │  │  → 07-FEATURE-      │
                     │    F3-PLAYGROUND.md │  │    F6-ANALYTICS.md  │
                     └────────────────────┘  └────────────────────┘
                                        │
                                        ▼
                          ┌────────────────────────────────────┐
                          │  AGENT 8 (sequential, 1 week)     │
                          │  F5: Security Scanner (late)        │
                          │  → 06-FEATURE-F5-SECURITY.md        │
                          │  Reason: gates deploy; run before   │
                          │  final integration                 │
                          └────────────────┬───────────────────┘
                                           │
                                           ▼
                          ┌────────────────────────────────────┐
                          │  AGENT 9 (sequential, 1 week)       │
                          │  Integration, polish, launch         │
                          │  → 09-INTEGRATION-AND-LAUNCH.md      │
                          └────────────────────────────────────┘
```

---

## Phase Order (paste prompts in this sequence)

| # | Prompt | Why this order | Sequential/parallel |
|---|---|---|---|
| 1 | `01-MASTER-TEMPLATE.md` | The reusable template (also embedded in every other prompt for self-containment) | — |
| 2 | `02-WAVE-0-AND-SKELETON.md` | Sets foundation; nothing else can start without it | Sequential |
| 3 | `04-FEATURE-F1-OPENAPI.md` | F1's tools_config schema is the contract F2/F4/F5 all depend on | Sequential |
| 4 | `03-FEATURE-F2-AI-ENGINE.md` + `05-FEATURE-F4-GATEWAY.md` + `06-FEATURE-F5-SECURITY.md` + `08-FEATURE-F7-AUTH-TEAMS.md` | Can run in parallel; F2/F4/F5 read F1's schema; F7 is independent | **4 parallel** |
| 5 | `04-FEATURE-F3-PLAYGROUND.md` + `07-FEATURE-F6-ANALYTICS.md` | Both depend on F4 (gateway) | **2 parallel** |
| 6 | `09-INTEGRATION-AND-LAUNCH.md` | Final integration, polish, deploy | Sequential |

(F5 — Security Scanner — can technically run in parallel with F2/F4/F7, but its findings affect whether the gateway can deploy. Run it in the integration phase so the security findings inform the final design.)

---

## How to Use These Prompts

1. **Read the prompt file in full** before pasting. It's 5-15 minutes of reading.
2. **Verify the prerequisites** are met (previous phase's PR is merged, dependencies are installed, etc.).
3. **Paste the prompt verbatim** into a fresh AI agent session. Do NOT paraphrase — the wording has been tuned.
4. **Monitor the agent** as it works. Read its progress. Catch deviations early.
5. **Review the agent's PR** against the "Definition of Done" section of the prompt.
6. **If the agent's output is wrong,** DO NOT just retry. Update the prompt with what's missing and re-run.
7. **Commit the agent's work** with a clear message. The plan + the prompt are the audit trail.

---

## What the Prompts Reference

Every prompt assumes the agent will read these `.planning/` files (in order):

1. `INDEX.md` — navigation
2. `CURRENT-STATE.md` — exact state of the codebase
3. `00-MASTER-PLAN.md` — architecture, principles, build order, conventions
4. `09-INFRA-MIGRATIONS.md` — DB migrations, env vars
5. The specific feature plan (`features/NN-FEATURE-*.md`)
6. The relevant `research/*.md` files

The agent reads these FIRST, before any code work. Skipping the reading is the #1 cause of quality problems.

---

## Failure Modes & Recovery

| Symptom | Likely cause | Fix |
|---|---|---|
| Agent uses `anthropic` SDK directly | Didn't read the constraint; didn't read `research/LLM-PROVIDERS.md` | Reject PR; update prompt to call out the constraint more loudly; re-run |
| Agent invents new file structure | Didn't read `CURRENT-STATE.md` | Reject PR; have agent re-read the existing file structure before any work |
| Agent leaves `pass` or `TODO` | Didn't read "no stubs" constraint | Reject PR; require re-submission with TODOs implemented |
| Agent's API endpoint shape doesn't match what the frontend expects | Skeleton wasn't built first, or agent didn't regenerate shared types | Reject PR; ensure Wave 0+Skeleton is complete and reviewed before this agent runs |
| Agent's tests don't actually test the right things | Agent didn't write tests for the edge cases in the plan's "Edge Cases" section | Reject PR; require tests for each edge case explicitly listed |
| Two parallel agents produce incompatible code | The shared types/schema isn't strict enough | Add stricter types in the skeleton; have both agents regenerate from the same source |
| Agent's cost is "200 OK" with no error path | Agent didn't read the error handling section of the plan | Reject PR; require all error paths tested |

---

## Cost Optimization

- Each prompt is bounded. An agent run produces roughly 5K-15K LoC of code, depending on the feature.
- Fresh agent context = high quality. Don't try to "save time" by continuing a previous agent session.
- The skeleton is the highest-leverage investment. Spend 1 week on it; save 3 weeks of agent rework.
- If a feature PR is wrong, the cost of fixing the prompt and re-running is much less than the cost of merging wrong code.

---

*See individual prompt files in this folder.*
