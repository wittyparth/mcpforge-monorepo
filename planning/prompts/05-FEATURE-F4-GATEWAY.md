# 05 — Feature 4: MCP Gateway (Parallel Wave 1)

> **When to use:** After F1 lands. Can run in parallel with F2, F5, F7.
> **Produces:** A working MCP gateway that translates MCP protocol → HTTP, with auth, rate limits, SSRF guard.
> **Most architecturally important feature.** Take your time on the security-sensitive parts.

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order, no skipping):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
4. .planning/09-INFRA-MIGRATIONS.md
5. AGENTS.md
6. .planning/features/05-FEATURE-MCP-GATEWAY.md (your full
   spec — read in full, this is the most complex feature)
7. .planning/research/MCP-PROTOCOL.md (JSON-RPC, transports,
   session management, error codes)
8. .planning/research/MCP-REFERENCE-SERVERS.md (Stripe,
   Cloudflare, Sentry, Anthropic patterns)
9. .planning/research/CELERY-FASTAPI-SSE.md (SSE in FastAPI)
10. apps/api/app/gateway/mcp_server.py (current stub)
11. apps/api/app/gateway/transport_sse.py (current stub)
12. apps/api/app/gateway/transport_http.py (current stub)
13. apps/api/app/gateway/tool_executor.py (current echo stub)
14. apps/api/app/playground/ws.py (current echo stub)
15. apps/api/app/services/credential_service.py (F1's, you'll
    decrypt at request time)
16. The `tools_config` JSON shape from F1

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: F4 — Hosted MCP Gateway
Feature plan: .planning/features/05-FEATURE-MCP-GATEWAY.md
Build order: Parallel Wave 1 (with F2, F5, F7)
Prerequisites: F1 must be merged (uses mcp_servers.tools_config
              and credentials tables). Wave 0 auth (JWT required
              on gateway routes).

═══════════════════════════════════════════════════════════════════════
CRITICAL CONSTRAINTS
═══════════════════════════════════════════════════════════════════════

1. **All gateway routes require JWT auth.** Wave 0 added the
   dependency; F4 must USE it. No anonymous access.

2. **SSRF prevention is non-negotiable.** Block 10.x, 172.16.x,
   192.168.x, 127.x, 169.254.x (AWS metadata), 0.0.0.0. Resolve
   the base_url hostname and check IP is not in any blocked
   range. Fail with `SSRFBlocked` error (-32005).

3. **Credentials are decrypted ONLY at request time** in the
   gateway. Never logged, never cached, never returned in
   error responses. Plaintext is cleared from memory after
   the call (best-effort).

4. **Rate limit per server** (Redis token bucket):
   - Free: 60/hour, 500/month
   - Pro: 1000/hour, 10000/month
   - Team: 10000/hour, 100000/month

5. **Response size limit: 5MB max** from upstream. Truncate to
   100KB with `_truncated: true` flag. Base64-encode binary
   with MIME type. Strip HTML, return plain text error.

6. **No caching of target API responses** in v1.0. Always live.

7. **Use httpx.AsyncClient** with 5s timeout, retry once on
   429 after 1s.

8. **MCP session management:** generate UUID v4 on
   initialize, return in `MCP-Session-Id` header. No Redis
   storage of session contents in v1.0.

9. **Both transports implemented:**
   - SSE: `GET /mcp/v1/{slug}/sse` + `POST /mcp/v1/{slug}/message`
   - StreamableHTTP: `POST /mcp/v1/{slug}/`

10. **Standard MCP error codes:** ToolNotFound (-32001),
    UpstreamError (-32002), RateLimitExceeded (-32003),
    ServerDisabled (-32004), SSRFBlocked (-32005),
    CredentialError (-32006), Timeout (-32007).

═══════════════════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════════════════

D1. **app/gateway/ssrf_guard.py** — IP blocklist check (10 tests)
D2. **app/gateway/auth_header_builder.py** — auth header
    construction (6 tests)
D3. **app/gateway/response_handler.py** — response truncation,
    base64, HTML strip (8 tests)
D4. **app/gateway/rate_limiter.py** — Redis token bucket with
    Lua script (6 tests)
D5. **app/gateway/tool_dispatcher.py** — the big one: builds
    HTTP request, executes via httpx, handles response (10
    tests)
D6. **app/gateway/session.py** — session manager
D7. **app/gateway/transport_sse.py** — REWRITE: full MCP over
    SSE (8 tests)
D8. **app/gateway/transport_http.py** — REWRITE: real
    StreamableHTTP, not just delegating to SSE (8 tests)
D9. **app/gateway/mcp_server.py** — UPDATE: register all
    gateway routes
D10. **app/services/server_config_cache.py** — Redis-cached
    server config lookup, invalidated on PATCH (6 tests)
D11. **app/api/v1/endpoints/gateway_admin.py** — deploy/pause/
    resume/connect endpoints (5 tests)
D12. **app/schemas/gateway.py** — ConnectPanelResponse,
    TestConnectionResponse, PauseResponse, DeployRequest
D13. **app/schemas/mcp_protocol.py** — JSONRPCRequest,
    JSONRPCNotification, JSONRPCSuccessResponse,
    JSONRPCErrorResponse, MCPErrorCode constants
D14. **Cache invalidation:** when mcp_servers is PATCHed, call
    `ServerConfigCache.invalidate(slug)`. When credentials
    change, same.
D15. **Update gateway route registration** in app/main.py
D16. **Update mcp_servers_service.py** to call cache.invalidate
D17. **End-to-end tests** (tests/test_gateway_e2e.py): 8 tests
    covering full init→list→call flow with mocked HTTP
D18. **Frontend types:** ConnectPanelResponse,
    TestConnectionResponse, PauseResponse
D19. **Frontend hooks** in `apps/web/src/hooks/use-gateway.ts`:
    useConnectPanel, useTestConnection, usePauseServer,
    useResumeServer, useDeployServer
D20. **Frontend API client:** api.servers.getConnectPanel,
    testConnection, deploy, pause, resume
D21. **Frontend components** in `apps/web/src/components/server/`:
    connect-panel.tsx, gateway-url-display.tsx,
    claude-desktop-config.tsx, cursor-config.tsx,
    test-connection-button.tsx, pause-resume-toggle.tsx,
    deploy-button.tsx
D22. **Add a Settings tab** to server detail page
D23. **Tests:** ≥70 backend tests, ≥5 Vitest, 2 Playwright
    (06-deploy-and-connect, 07-pause-resume)
D24. **THE MOMENT OF TRUTH:** manual end-to-end test with
    real Claude Desktop. Document the steps.

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE
═══════════════════════════════════════════════════════════════════════

1. Schemas (mcp_protocol, gateway)
2. SSRF guard + tests
3. Auth header builder + tests
4. Response handler + tests
5. Rate limiter + tests
6. Server config cache + tests
7. Tool dispatcher (the big one) + tests
8. Session manager
9. SSE transport REWRITE
10. HTTP transport REWRITE
11. Gateway admin endpoints
12. Cache invalidation wiring
13. E2E tests
14. Backend verification
15. Frontend types + API + hooks
16. Frontend components
17. Settings tab in server detail
18. Vitest + Playwright
19. Full CI
20. Manual e2e with Claude Desktop

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[All from master template] Plus F4-specific:
[ ] sse-starlette added to pyproject.toml
[ ] All gateway routes require JWT (verify by curl without
    auth — should 401)
[ ] SSRF guard verified: curl targeting 169.254.169.254
    returns SSRFBlocked error
[ ] Rate limit verified: 61st call to a free server returns
    RateLimitExceeded
[ ] Response truncation verified: mock upstream returns 200KB
    body, gateway returns 100KB + _truncated:true
[ ] Binary response verified: mock upstream returns image/png,
    gateway returns base64 with mimeType
[ ] HTML response verified: mock upstream returns text/html,
    gateway returns plain text
[ ] Both transports work: SSE and StreamableHTTP
[ ] Session management: initialize returns MCP-Session-Id
    header, subsequent requests accept it
[ ] Cache invalidation: PATCH server, next call sees new config
[ ] No credentials in any log line (verify with grep + test)
[ ] All MCP error codes correctly returned
[ ] Frontend connect panel renders Claude Desktop and Cursor
    configs as copy-paste JSON
[ ] 70+ backend tests passing
[ ] Manual: end-to-end with real Claude Desktop — tool call
    from Claude Desktop through MCPForge gateway to a real
    API (e.g., httpbin.org or a test server) succeeds

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

[Standard format]

Plus F4-specific:
## Transports implemented:
- [ ] SSE (GET /mcp/v1/{slug}/sse + POST /message)
- [ ] StreamableHTTP (POST /mcp/v1/{slug}/)
## Manual e2e test result:
- Claude Desktop version: ...
- Test API used: ...
- Tool called: ...
- Result: success/failure + response time
```

---

## Reviewer's checklist

1. **SSRF guard** — `curl -X POST .../tools/call` with `base_url=http://169.254.169.254/latest/meta-data/` should return SSRFBlocked.
2. **Rate limit** — 61st call to free server in an hour returns RateLimitExceeded.
3. **No credentials in logs** — `grep -r "Bearer\|api_key" logs/ | grep -v REDACTED` returns nothing.
4. **Both transports** — test with a real MCP client (Claude Desktop, mcp-cli, or our F3 playground).
5. **Cache invalidation** — update a server's auth_scheme, next gateway call should use the new scheme.
6. **Session management** — second call without initialize still works (we're lenient).
7. **Performance** — P50 <100ms overhead measured locally; P95 <250ms.
