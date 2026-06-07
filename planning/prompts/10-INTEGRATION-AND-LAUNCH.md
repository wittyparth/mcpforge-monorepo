# 10 — Integration & Launch (Sequential, ~1 week)

> **When to use:** LAST agent, after all 7 features merged. This is the final polish + deploy + launch prep.
> **Produces:** Working v1.0 in production, demo video, registry submissions, ready for HN launch.

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md (read § 9 Definition of Done
   in full — that's the success criteria for this agent)
4. .planning/01-COMPETITOR-ANALYSIS.md
5. .planning/09-INFRA-MIGRATIONS.md
6. All 7 feature plans (skim — you need to know what was built)
7. AGENTS.md

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: Integration & Launch (no PRD feature — this is the
final integration pass)
Build order: LAST
Prerequisites: All 7 features (F1-F7) merged to main

═══════════════════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════════════════

D1. **End-to-end smoke test of all 3 PRD user flows:**

    **Flow A — New user builds and deploys first MCP server:**
    1. Register
    2. Paste OpenAPI URL (use https://petstore3.swagger.io/
       api/v3/openapi.json — it's public, stable, 19 endpoints)
    3. Tool workspace appears
    4. Toggle off DELETE endpoints
    5. Configure auth (none for petstore)
    6. Build (AI enhancement runs)
    7. Review panel shows AI-enhanced descriptions
    8. Accept all
    9. Deploy (security scanner runs)
    10. Connect panel shows gateway URL + Claude config
    11. Open playground, call a tool, see response
    12. Add to Claude Desktop (manual test with real Claude)
    13. Tool call from Claude Desktop through MCPForge works

    **Flow B — Developer iterates on descriptions:**
    1. Open playground for the same server
    2. Edit a tool's description manually
    3. See the change in the gateway immediately
    4. Description performance panel shows the call rate
       delta (after enough time/calls)

    **Flow C — Team lead shares server with team:**
    1. Invite 2 team members
    2. Accept invitations
    3. Verify team members can see the server
    4. Verify they CAN'T delete (Viewer role)

D2. **Fix any integration bugs found.** Common categories:
    - Schema drift between backend and frontend types
    - Cache invalidation not firing on server updates
    - CORS misconfiguration
    - Cookie not being set due to SameSite issues
    - Tool name collision between AI-generated and original

D3. **Production deployment:**
    - Deploy to Render (backend)
    - Deploy to Vercel (frontend)
    - Set all env vars in Render dashboard
    - Run migrations on production DB
    - Test production health endpoint
    - Verify Sentry is capturing events

D4. **Performance verification:**
    - Measure P50/P95 gateway latency under load
    - Use `wrk` or similar to send 100 concurrent requests
    - Verify rate limits work
    - Check Upstash usage
    - Check Anthropic/DeepSeek usage

D5. **Cost verification:**
    - Test full Flow A with DeepSeek
    - Note the cost in `mcp_servers.ai_enhancement_cost_cents`
    - Cross-check with DeepSeek dashboard

D6. **Demo video** (90 seconds, screen-recorded):
    - 0-15s: Land on landing page, click "Start Building"
    - 15-45s: Paste Stripe OpenAPI URL, see tools, select 5
    - 45-60s: AI enhancement panel appears, show before/after
      quality scores
    - 60-75s: Deploy, see connect panel, copy Claude config
    - 75-90s: Open Claude Desktop, call a tool, show success
    - Upload to YouTube (unlisted) and Loom
    - Save in `docs/demo-video.md`

D7. **Production-grade documentation:**
    - Update README.md with: how to use, deployment, env vars
    - docs/operator-runbook.md: on-call playbook, common
      issues, runbooks
    - docs/api-reference.md: auto-generated from /openapi.json
    - docs/architecture.md: high-level diagram (mermaid)

D8. **Registry submissions:**
    - Submit to Smithery (https://smithery.ai): create
      "MCPForge Server Builder" listing
    - Submit to Glama (https://glama.ai): same
    - Post MCPForge-generated servers for popular APIs
      (Stripe, Notion, Linear) on these registries
    - Save submission links in docs/registry-submissions.md

D9. **Launch prep:**
    - Write HackerNews "Show HN" post draft (3 paragraphs)
    - Write Twitter/X thread draft (5 tweets)
    - Draft 20 beta user outreach emails
    - Save all in docs/launch-materials.md

D10. **Final Definition of Done check:**
    Walk through the § 9 "Definition of Done" in
    00-MASTER-PLAN.md. Verify every item. Create a
    docs/v1.0-launch-checklist.md with each item checked
    off.

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE
═══════════════════════════════════════════════════════════════════════

1. Run full test suite (all features): verify nothing
   regressed
2. End-to-end smoke test of all 3 flows
3. Fix integration bugs as found
4. Deploy to production (Render + Vercel)
5. Set all env vars in Render dashboard
6. Run migrations on prod DB
7. Test prod health endpoint
8. Verify Sentry is capturing
9. Measure performance
10. Record demo video
11. Write documentation
12. Submit to registries
13. Prepare launch materials
14. Final Definition of Done walkthrough
15. Hand off to user for HN post + beta outreach

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[This IS the final Definition of Done — per 00-MASTER-PLAN.md § 9]

Product:
[ ] All 3 PRD user flows (A, B, C) work end-to-end
[ ] Landing page, pricing page, dashboard all polished
[ ] Demo video recorded (90 seconds, uploaded)

Engineering:
[ ] All endpoints have tests (unit + integration)
[ ] All 3 user flows have Playwright E2E
[ ] Lint + type-check + tests pass in CI
[ ] pnpm build succeeds for all packages
[ ] docker compose up brings up full stack
[ ] Staging environment deployed and verified

Security:
[ ] All credentials encrypted (Fernet)
[ ] SSRF guard in gateway
[ ] Rate limits per server, per user, per IP
[ ] CSRF protection on cookie-auth
[ ] Sentry captures errors
[ ] No secrets in git history
[ ] Argon2id for password hashing
[ ] HIBP check on registration

Quality:
[ ] Average tool quality score on Stripe MCP server: >85/100
[ ] Gateway P95 latency overhead: <250ms
[ ] AI enhancement per tool: <3s
[ ] Build pipeline for 15 tools: <30s end-to-end

Business:
[ ] Free tier enforces limits (500 calls/mo, 2 servers)
[ ] Pro plan ($12/mo) functional
[ ] Team plan ($29/seat/mo) functional
[ ] Stripe webhooks working (tested in Stripe dashboard)
[ ] Pricing page accurate

Launch readiness:
[ ] HackerNews post drafted
[ ] Twitter thread drafted
[ ] 20 beta user outreach emails drafted
[ ] Smithery/Glama submission prepared
[ ] Demo video uploaded

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

```
## Status: COMPLETE | PARTIAL | BLOCKED
## Production URL: https://api.mcpforge.io
## Production frontend URL: https://mcpforge.io
## Demo video: [link]
## All 3 user flows tested: yes/no
## Definition of Done: <X>/<Y> items checked
## Open issues for post-launch:
- <list, or "none">
## Ready for HN launch: yes/no
## Hand-off notes:
- <any important context the user needs to know>
```
```

---

## After this agent finishes

You, the human, do the final 4 things (the agent can't do these):

1. **Review the demo video.** If it's not 90 seconds, reshoot.
2. **Read the HN post draft.** Edit it in your voice. The agent's draft is a starting point.
3. **Send the 20 beta outreach emails** to your network.
4. **Post the HN thread at 8AM Pacific on a Tuesday** (per PRD § 16).

Then you're live. 🚀
