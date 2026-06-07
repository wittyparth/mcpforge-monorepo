# Feature 4 — Hosted MCP Gateway

> **PRD reference:** § 7 Feature 4 (lines 366-424)
> **Build order:** Wave 1, Step 2 (F1 builds tools_config; F2 enhances it; this serves it)
> **Estimated effort:** 6-8 days for one engineer

---

## 0. TL;DR

Every deployed MCP server gets a permanent URL: `https://mcpforge.io/mcp/v1/{server_slug}`. The Gateway speaks the MCP protocol (JSON-RPC 2.0) over both SSE and StreamableHTTP transports, translates incoming `tools/call` requests into actual HTTP calls to the user's target API, and returns MCP-formatted responses. Credentials are decrypted at request time, never logged, never exposed. SSRF is blocked. Rate limits are enforced. Latency overhead budget: P50 <100ms, P95 <250ms.

This is the most architecturally important feature. The current `app/gateway/` is a stub that only echoes — this feature replaces it with a real implementation.

---

## 1. Goals & Non-Goals

### 1.1 In scope (v1.0)
- Implement both MCP transports: SSE (`GET /mcp/v1/{slug}/sse`) and StreamableHTTP (`POST /mcp/v1/{slug}/`)
- Full JSON-RPC 2.0: `initialize`, `tools/list`, `tools/call`, `ping`, `notifications/initialized`, `notifications/cancelled`
- Session management with `MCP-Session-Id` header
- Server config cache (Redis, 5-min TTL, invalidated on server update)
- Credential decryption (Fernet) at request time
- Auth header building based on `mcp_servers.auth_scheme`
- HTTP request execution via `httpx.AsyncClient` (5s timeout, retry once on 429)
- Response handling: truncation (>100KB), base64 binary, strip HTML errors
- SSRF prevention: block internal IP ranges in outbound requests
- Rate limiting: per-server, per-hour, per-month, plan-based
- Analytics event emission (to F6 pipeline; non-blocking)
- Standard MCP error codes: `ToolNotFound`, `InvalidParams`, `UpstreamError`, `RateLimitExceeded`
- Authentication required for all gateway routes (JWT in cookie or Authorization header)
- Enable/Disable toggle (5s propagation via Redis pub/sub)

### 1.2 Out of scope (defer to v1.1+)
- `resources/list` and `resources/read` (MCP resources) — PRD v1.2
- `prompts/list` and `prompts/get` (MCP prompts) — PRD v1.2
- `sampling/createMessage` (server → client) — out of scope; gateway is server only
- OAuth 2.1 upstream (for APIs requiring OAuth dance) — PRD v1.2
- Per-tool rate limits (limit per server for v1.0)
- Server-side caching of target API responses (always live in v1.0)
- Connection pooling across servers (each call opens new httpx connection; v1.1 uses persistent pool)

---

## 2. User Stories

- As a user with a deployed server, I can add the gateway URL to Claude Desktop and it works.
- As a user with a deployed server, I can add the gateway URL to Cursor and it works.
- As a user, I see a "Connect" panel with copy-paste configs for Claude Desktop and Cursor.
- As a user, I can click "Test Connection" and see the gateway respond with `tools/list`.
- As a user, my API calls go through the gateway, get translated to HTTP, return responses, all in <500ms for fast APIs.
- As a user, I can pause my server and it stops accepting calls within 5 seconds.
- As a user on free tier, I get rate limited at 500 calls/month.
- As a user, my credentials are never exposed in any error response, log, or analytics event.
- As a Claude Desktop user, I can call any of the server's selected tools.
- As a user, when my target API returns 5xx, the gateway returns a typed `UpstreamError`, not a 500.
- As a user, when my target API returns 4xx, the gateway returns the body to the LLM (for self-correction).
- As a user, when the response is >100KB, the gateway truncates and adds `_truncated: true`.
- As a user, when the response is binary (image, file), the gateway base64-encodes with MIME type.
- As a user, when the response is HTML, the gateway strips HTML and returns plain text error.
- As an admin, I can see gateway request metrics in logs (request_id, server_id, tool_name, latency_ms, status).

---

## 3. Architecture Diagram

```
┌────────────────┐  HTTPS     ┌──────────────────────────────────┐
│  Claude        │───────────►│  Edge (Render / Cloudflare)      │
│  Desktop       │            │  - TLS                            │
│  Cursor        │            │  - Rate limit (per-IP)            │
│  MCP Client    │            │  - WAF                            │
└────────────────┘            └──────────┬───────────────────────┘
                                         │
                                         ▼
┌────────────────────────────────────────────────────────────┐
│  MCP Gateway (FastAPI, in same process as Main API)        │
│                                                            │
│  POST /mcp/v1/{slug}/                                      │
│  ├─ 1. JWT auth (required)                                │
│  ├─ 2. Slug → server config (Redis cache, 5min TTL)       │
│  ├─ 3. Check server status (active/paused/disabled)       │
│  ├─ 4. Rate limit check (Redis token bucket)              │
│  ├─ 5. Parse JSON-RPC                                     │
│  ├─ 6. Route by method:                                   │
│  │   ├─ initialize → return capabilities + session_id      │
│  │   ├─ tools/list → return tools from tools_config       │
│  │   ├─ tools/call → dispatch (see below)                 │
│  │   ├─ ping → return {}                                  │
│  │   └─ notifications/* → no-op                           │
│  └─ 7. Return JSON-RPC response                           │
│                                                            │
│  For tools/call:                                          │
│  ├─ Look up tool in tools_config                          │
│  ├─ Validate arguments against inputSchema                 │
│  ├─ Decrypt credentials (Fernet)                          │
│  ├─ Build auth headers                                    │
│  ├─ Build HTTP request: method + base_url + path + headers│
│  ├─ SSRF check: resolve base_url, ensure NOT internal IP  │
│  ├─ Execute via httpx.AsyncClient (5s timeout)            │
│  ├─ Retry once on 429                                     │
│  ├─ Handle response:                                      │
│  │   ├─ >100KB → truncate + flag _truncated: true        │
│  │   ├─ Binary → base64 encode + MIME type               │
│  │   ├─ HTML → strip tags, return plain text              │
│  │   └─ JSON → return as-is                              │
│  ├─ Async-fire analytics event to Celery                  │
│  ├─ Update mcp_servers.total_calls, monthly_calls         │
│  └─ Return MCP-formatted response                         │
└────────────────────────────┬───────────────────────────────┘
                             │
                             ▼
            ┌────────────────────────────────────┐
            │  Target API (user's API)           │
            │  e.g., api.stripe.com              │
            │  e.g., api.notion.com              │
            └────────────────────────────────────┘
```

### 3.1 Session management

- On `initialize`, server generates a session ID (UUID v4), returns in `MCP-Session-Id` header
- Sessions are NOT persistent (no Redis storage for v1.0; just header exchange)
- On `notifications/initialized`, session is "established" (just acknowledgement)
- On `notifications/cancelled` (with `requestId`), the in-flight request is cancelled via asyncio task
- Sessions can be reused across requests (Claude Desktop does this)

### 3.2 Rate limit implementation

Token bucket per server, per plan:

| Plan | Per-hour burst | Per-month sustained |
|---|---|---|
| Free | 60 | 500 |
| Pro | 1,000 | 10,000 |
| Team | 10,000 | 100,000 |

Redis Lua script for atomic check-and-increment:
```lua
-- KEYS[1] = "rl:{server_id}:hour", KEYS[2] = "rl:{server_id}:month"
-- ARGV[1] = hour_limit, ARGV[2] = month_limit
-- Returns: 1 if allowed, 0 if denied
local hour_count = tonumber(redis.call("GET", KEYS[1]) or "0")
local month_count = tonumber(redis.call("GET", KEYS[2]) or "0")
if hour_count >= tonumber(ARGV[1]) or month_count >= tonumber(ARGV[2]) then
    return 0
end
redis.call("INCR", KEYS[1])
redis.call("EXPIRE", KEYS[1], 3600)
redis.call("INCR", KEYS[2])
redis.call("EXPIRE", KEYS[2], 2592000)
return 1
```

Hourly counter resets via TTL. Monthly counter resets on 1st of month (cron job sets new key, or use TTL of 30 days for simplicity).

### 3.3 SSRF prevention

When making outbound request to user's `base_url`:
1. Resolve hostname → IP
2. Check IP is not in: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16` (AWS metadata), `0.0.0.0/8`
3. Check IP is not in IPv6 equivalent ranges
4. If internal, return `UpstreamError` with safe message (don't echo the URL)

When user adds URL params in tool call that look like URLs (`url`, `endpoint`, `target`, `host`):
- These should NOT be fetched by the gateway (they're just passed as query params to the user's API)
- But if the user's API then fetches the URL, that's the user's API's responsibility, not ours
- We don't proxy arbitrary URLs

### 3.4 Data flow for a single tool call

```
1. Claude Desktop sends:
   POST /mcp/v1/my-stripe/
   Headers: Cookie: access_token=...
           MCP-Session-Id: abc123 (optional)
   Body: {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_products","arguments":{"query":"red shoes"}}}

2. Gateway:
   - JWT auth ✓
   - Slug "my-stripe" → server config from cache
   - status="active" ✓
   - Rate limit: 1/60 hour, 1/500 month ✓
   - Parse JSON-RPC: method="tools/call", params.name="search_products"
   - Find tool in tools_config: yes
   - Validate arguments against inputSchema: query is required string ✓
   - Decrypt credential: SK_LIVE_*** (Fernet)
   - Build headers: {"Authorization": "Bearer SK_LIVE_***"}
   - Build request: GET https://api.example.com/v1/products/search?query=red+shoes
   - SSRF check: api.example.com → 93.184.216.34 (not internal) ✓
   - Execute via httpx: GET https://api.example.com/v1/products/search?query=red+shoes with 5s timeout
   - Response: 200 OK, [{"id":"prod_1","name":"Red Shoes",...}]
   - Check size: 1.2KB < 100KB ✓
   - Format as MCP JSON-RPC: {"result":{"content":[{"type":"text","text":"[{...}]"}],"isError":false}}
   - Async-fire analytics event (non-blocking)
   - Atomic UPDATE mcp_servers SET total_calls=total_calls+1, monthly_calls=monthly_calls+1
   - Return response
```

---

## 4. Backend Changes

### 4.1 New dependencies

```toml
"sse-starlette>=2.1.0",  # SSE in FastAPI
```

(No new model deps; uses existing infrastructure)

### 4.2 New files

```
apps/api/app/
├── gateway/
│   ├── __init__.py                   (exists, update)
│   ├── mcp_server.py                 (REWRITE: real MCP routes)
│   ├── transport_sse.py              (REWRITE: full MCP over SSE)
│   ├── transport_http.py             (REWRITE: full StreamableHTTP)
│   ├── session.py                    (NEW: session management)
│   ├── tool_dispatcher.py            (NEW: tool → HTTP request builder)
│   ├── response_handler.py           (NEW: truncate/base64/strip HTML)
│   ├── ssrf_guard.py                 (NEW: IP blocklist check)
│   ├── auth_header_builder.py        (NEW: build headers from auth_scheme)
│   └── rate_limiter.py               (NEW: Redis token bucket)
├── services/
│   ├── server_config_cache.py        (NEW: Redis-cached server config lookup)
│   └── gateway_service.py            (NEW: orchestrator)
├── api/v1/endpoints/
│   └── gateway_admin.py              (NEW: /servers/{id}/deploy, /pause, etc.)
└── schemas/
    ├── gateway.py                    (NEW: request/response models for gateway)
    └── mcp_protocol.py               (NEW: JSON-RPC types)

apps/api/tests/
├── test_transport_sse.py             (8 tests, NEW)
├── test_transport_http.py            (8 tests, NEW)
├── test_tool_dispatcher.py           (10 tests, NEW)
├── test_response_handler.py          (8 tests, NEW)
├── test_ssrf_guard.py                (10 tests, NEW)
├── test_auth_header_builder.py       (6 tests, NEW)
├── test_rate_limiter.py              (6 tests, NEW)
├── test_server_config_cache.py       (6 tests, NEW)
└── test_gateway_e2e.py               (8 tests, NEW — full request flow)
```

### 4.3 New Pydantic schemas

#### `app/schemas/mcp_protocol.py` (NEW)

```python
"""MCP JSON-RPC 2.0 message types."""

class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int  # not null per MCP spec
    method: str
    params: dict | None = None

class JSONRPCNotification(BaseModel):
    """No id, no response expected."""
    jsonrpc: Literal["2.0"]
    method: str
    params: dict | None = None

class JSONRPCSuccessResponse(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int
    result: dict | list | str | int | float | bool | None

class JSONRPCErrorResponse(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int | None  # null for parse errors
    error: JSONRPCError

class JSONRPCError(BaseModel):
    code: int  # -32700 to -32099
    message: str
    data: dict | None = None

# Standard error codes (MCP-compatible)
class MCPErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # MCP-specific (server-defined range -32000 to -32099)
    TOOL_NOT_FOUND = -32001
    UPSTREAM_ERROR = -32002
    RATE_LIMIT_EXCEEDED = -32003
    SERVER_DISABLED = -32004
    SSRF_BLOCKED = -32005
    CREDENTIAL_ERROR = -32006
    TIMEOUT = -32007
```

#### `app/schemas/gateway.py` (NEW)

```python
class ConnectPanelResponse(BaseModel):
    """Returned by /api/v1/servers/{id}/connect."""
    server_slug: str
    gateway_url: str
    transport_modes: list[Literal["sse", "streamable_http"]]
    claude_desktop_config: dict  # ready-to-paste JSON
    cursor_config: dict
    test_connection_endpoint: str  # GET to test

class TestConnectionResponse(BaseModel):
    success: bool
    response_time_ms: int
    tools_count: int | None
    error: str | None = None

class DeployRequest(BaseModel):
    skip_security_scan: bool = False  # admin override only

class PauseResponse(BaseModel):
    server_id: UUID
    status: Literal["paused", "active"]
    paused_at: datetime | None
    estimated_propagation_seconds: int = 5

class MCPGatewayInitResult(BaseModel):
    """Result of MCP initialize request."""
    protocolVersion: str = "2025-11-25"
    capabilities: dict = Field(default_factory=lambda: {"tools": {"listChanged": False}})
    serverInfo: dict = Field(default_factory=lambda: {
        "name": "mcpforge-gateway",
        "version": "1.0.0",
    })
    sessionId: str  # UUID
```

### 4.4 New endpoints

| Method | Path | Handler | Auth | Description |
|---|---|---|---|---|
| GET | `/mcp/v1/{slug}/health` | (existing) | No | Health check |
| GET | `/mcp/v1/{slug}/sse` | (rewrite) | JWT | SSE transport |
| POST | `/mcp/v1/{slug}/` | (rewrite) | JWT | StreamableHTTP transport |
| POST | `/mcp/v1/{slug}/message` | (keep) | JWT | Legacy SSE message endpoint |
| GET | `/api/v1/servers/{id}/connect` | (NEW) | JWT | Get connect panel info |
| POST | `/api/v1/servers/{id}/connect/test` | (NEW) | JWT | Test connection to gateway |
| POST | `/api/v1/servers/{id}/deploy` | (NEW) | JWT | Deploy (triggers F5 scan first) |
| POST | `/api/v1/servers/{id}/pause` | (NEW) | JWT | Pause server |
| POST | `/api/v1/servers/{id}/resume` | (NEW) | JWT | Resume server |
| GET | `/api/v1/servers/{id}/status` | (NEW) | JWT | Current status |

### 4.5 New services — pseudocode

#### `app/gateway/rate_limiter.py` (NEW, ~100 lines)

```python
"""
Redis token bucket rate limiter. Plan-aware.
"""

import redis.asyncio as redis
from app.core.config import settings
from app.core.redis import get_redis

RATE_LIMITS = {
    "free": {"hour": 60, "month": 500},
    "pro": {"hour": 1000, "month": 10000},
    "team": {"hour": 10000, "month": 100000},
}

LUA_SCRIPT = """
local hour_key = KEYS[1]
local month_key = KEYS[2]
local hour_limit = tonumber(ARGV[1])
local month_limit = tonumber(ARGV[2])

local hour_count = tonumber(redis.call("GET", hour_key) or "0")
local month_count = tonumber(redis.call("GET", month_key) or "0")

if hour_count >= hour_limit then
    return {0, "hour", hour_count, hour_limit}
end
if month_count >= month_limit then
    return {0, "month", month_count, month_limit}
end

redis.call("INCR", hour_key)
redis.call("EXPIRE", hour_key, 3600)
redis.call("INCR", month_key)
redis.call("EXPIRE", month_key, 2592000)
return {1, "ok", hour_count + 1, month_count + 1}
"""

class GatewayRateLimiter:
    async def check(self, server_id: UUID, plan: str) -> RateLimitResult:
        limits = RATE_LIMITS.get(plan, RATE_LIMITS["free"])
        r = await get_redis()
        result = await r.eval(
            LUA_SCRIPT,
            2,
            f"rl:{server_id}:hour",
            f"rl:{server_id}:month",
            limits["hour"],
            limits["month"],
        )
        allowed = result[0] == 1
        return RateLimitResult(
            allowed=allowed,
            denial_reason=result[1].decode() if isinstance(result[1], bytes) else result[1],
            current=result[2],
            limit=result[3],
        )

class RateLimitResult:
    allowed: bool
    denial_reason: str  # 'hour' | 'month' | 'ok'
    current: int
    limit: int
```

#### `app/gateway/ssrf_guard.py` (NEW, ~60 lines)

```python
"""
SSRF prevention: block outbound requests to internal IPs.
"""

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

class SSRFGuard:
    async def assert_safe(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SSRFBlockedError(f"Scheme {parsed.scheme} not allowed")
        
        hostname = parsed.hostname
        if not hostname:
            raise SSRFBlockedError("No hostname in URL")
        
        # Resolve all IPs (handles DNS rebinding basics)
        try:
            infos = await asyncio.get_event_loop().getaddrinfo(hostname, parsed.port or 443)
        except socket.gaierror:
            raise SSRFBlockedError(f"Cannot resolve hostname: {hostname}")
        
        for info in infos:
            ip_str = info[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            
            for blocked in BLOCKED_RANGES:
                if ip in blocked:
                    raise SSRFBlockedError(f"IP {ip_str} is in blocked range")
```

#### `app/gateway/auth_header_builder.py` (NEW, ~50 lines)

```python
"""
Builds authentication headers based on mcp_servers.auth_scheme and the credential value.
"""

class AuthHeaderBuilder:
    def build(self, auth_scheme: str, credential_value: str, auth_header_name: str | None) -> dict[str, str]:
        if auth_scheme == "none" or not credential_value:
            return {}
        elif auth_scheme == "api_key":
            return {auth_header_name or "X-API-Key": credential_value}
        elif auth_scheme == "bearer":
            return {"Authorization": f"Bearer {credential_value}"}
        elif auth_scheme == "basic":
            encoded = base64.b64encode(credential_value.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        elif auth_scheme == "oauth2":
            return {"Authorization": f"Bearer {credential_value}"}
        return {}
```

#### `app/gateway/response_handler.py` (NEW, ~100 lines)

```python
"""
Handles upstream API responses: truncation, base64, HTML stripping.
"""

MAX_RESPONSE_SIZE = 100 * 1024  # 100KB

class ResponseHandler:
    def handle(self, response: httpx.Response) -> ToolCallResult:
        content_type = response.headers.get("content-type", "").lower()
        
        # 1. Check status
        if response.status_code >= 500:
            raise UpstreamError(
                message=f"Upstream API returned {response.status_code}",
                status_code=response.status_code,
                body=sanitize_body(response.text)[:500],  # cap
            )
        
        # 2. Check size
        body_bytes = response.content
        truncated = False
        if len(body_bytes) > MAX_RESPONSE_SIZE:
            body_bytes = body_bytes[:MAX_RESPONSE_SIZE]
            truncated = True
        
        # 3. Route by content-type
        if "json" in content_type:
            try:
                data = json.loads(body_bytes)
                return ToolCallResult(
                    type="json",
                    content=data,
                    truncated=truncated,
                    response_size_bytes=len(body_bytes),
                    status_code=response.status_code,
                )
            except json.JSONDecodeError:
                # Fall through to text
                pass
        
        if any(t in content_type for t in ["image/", "application/pdf", "application/octet-stream"]):
            # Binary: base64 encode
            return ToolCallResult(
                type="binary",
                content=base64.b64encode(body_bytes).decode(),
                mime_type=content_type,
                truncated=truncated,
                response_size_bytes=len(body_bytes),
                status_code=response.status_code,
            )
        
        if "html" in content_type:
            # Strip HTML, return plain text
            text = strip_html(body_bytes.decode("utf-8", errors="replace"))
            return ToolCallResult(
                type="text",
                content=text,
                truncated=truncated,
                response_size_bytes=len(body_bytes),
                status_code=response.status_code,
            )
        
        # Default: text
        return ToolCallResult(
            type="text",
            content=body_bytes.decode("utf-8", errors="replace"),
            truncated=truncated,
            response_size_bytes=len(body_bytes),
            status_code=response.status_code,
        )
```

#### `app/gateway/tool_dispatcher.py` (NEW, ~200 lines)

```python
"""
Dispatches an MCP tools/call request to the target API.
Builds the HTTP request from the tool's config, executes it, returns MCP-formatted result.
"""

import httpx
import jinja2
from app.gateway.ssrf_guard import SSRFGuard
from app.gateway.auth_header_builder import AuthHeaderBuilder
from app.gateway.response_handler import ResponseHandler
from app.services.credential_service import CredentialService
from app.services.gateway_service import GatewayService

class ToolDispatcher:
    def __init__(self):
        self.ssrf_guard = SSRFGuard()
        self.auth_builder = AuthHeaderBuilder()
        self.response_handler = ResponseHandler()
        self.http_client = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))
    
    async def dispatch(
        self,
        server_config: dict,
        tool: dict,
        arguments: dict,
        request_id: str,
    ) -> dict:
        """Returns MCP-formatted result dict (not the JSON-RPC envelope)."""
        
        # 1. Validate arguments against inputSchema (basic validation; full JSON Schema validation deferred to v1.1)
        self._validate_basic_arguments(tool["inputSchema"], arguments)
        
        # 2. Decrypt credential
        credential_service = CredentialService(...)
        # Note: this is the only place plaintext credentials exist in memory
        credential_value = await credential_service.get_decrypted_for_request(server_config["server_id"])
        
        try:
            # 3. Build auth headers
            auth_headers = self.auth_builder.build(
                server_config["auth_scheme"],
                credential_value,
                server_config.get("auth_header_name"),
            )
            
            # 4. Build request: method, URL, headers, body
            request = self._build_request(
                server_config=server_config,
                tool=tool,
                arguments=arguments,
                auth_headers=auth_headers,
            )
            
            # 5. SSRF check
            await self.ssrf_guard.assert_safe(str(request.url))
            
            # 6. Execute (with 1 retry on 429)
            response = await self._execute_with_retry(request, request_id=request_id)
            
            # 7. Handle response
            result = self.response_handler.handle(response)
            
            # 8. Format as MCP content
            if result.type == "json":
                content_text = json.dumps(result.content, indent=2)
            elif result.type == "binary":
                content_text = f"[Binary data: {result.mime_type}, {result.response_size_bytes} bytes, base64-encoded below]\n{result.content}"
            else:
                content_text = result.content
            
            if result.truncated:
                content_text = f"[Response truncated to {result.response_size_bytes} bytes]\n{content_text}"
            
            mcp_result = {
                "content": [
                    {
                        "type": "text",
                        "text": content_text,
                    }
                ],
                "isError": result.status_code >= 400,
            }
            
            if result.status_code >= 400:
                mcp_result["content"].append({
                    "type": "text",
                    "text": f"Upstream returned HTTP {result.status_code}",
                })
            
            return mcp_result
        finally:
            # Clear credential from memory (best effort)
            credential_value = None  # noqa
    
    def _build_request(self, server_config, tool, arguments, auth_headers) -> httpx.Request:
        # 1. Substitute path parameters: /users/{id} → /users/123
        path = tool["path"]
        for param in tool.get("parameters", []):
            if param.get("in") == "path" and param["name"] in arguments:
                path = path.replace(f"{{{param['name']}}}", str(arguments[param["name"]]))
        
        # 2. Build query parameters
        query_params = {}
        for param in tool.get("parameters", []):
            if param.get("in") == "query" and param["name"] in arguments:
                query_params[param["name"]] = arguments[param["name"]]
        
        # 3. Build body (for POST/PUT/PATCH)
        body = None
        if tool["method"] in ("POST", "PUT", "PATCH"):
            # Collect all non-path, non-query, non-header params as body
            body_params = {
                k: v for k, v in arguments.items()
                if k not in {p["name"] for p in tool.get("parameters", []) if p.get("in") in ("path", "query", "header")}
            }
            # Or, if any param was prefixed with "body_", strip the prefix
            body = {}
            for k, v in list(body_params.items()):
                if k.startswith("body_"):
                    body[k[5:]] = v
                else:
                    body[k] = v
            if body:
                body = json.dumps(body)
        
        # 4. Build headers
        headers = {
            "User-Agent": "MCPForge-Gateway/1.0",
            "Accept": "application/json",
        }
        headers.update(auth_headers)
        if body:
            headers["Content-Type"] = "application/json"
        
        # 5. Build URL
        base_url = server_config["base_url"].rstrip("/")
        url = f"{base_url}{path}"
        
        # 6. Build request
        return httpx.Request(
            method=tool["method"],
            url=url,
            params=query_params,
            headers=headers,
            content=body,
        )
    
    async def _execute_with_retry(self, request: httpx.Request, request_id: str) -> httpx.Response:
        try:
            response = await self.http_client.send(request)
        except httpx.TimeoutException:
            raise UpstreamError("Request timed out after 5 seconds")
        except httpx.RequestError as e:
            raise UpstreamError(f"Network error: {type(e).__name__}")
        
        if response.status_code == 429:
            # Retry once after 1s
            logger.info("rate_limited_retrying", request_id=request_id)
            await asyncio.sleep(1.0)
            try:
                response = await self.http_client.send(request)
            except (httpx.TimeoutException, httpx.RequestError):
                pass  # return the original 429
        
        return response
    
    def _validate_basic_arguments(self, input_schema: dict, arguments: dict) -> None:
        required = input_schema.get("required", [])
        for req in required:
            if req not in arguments:
                raise InvalidParamsError(f"Required parameter missing: {req}")
        # Type checking is basic for v1.0; full JSON Schema validation in v1.1
```

#### `app/gateway/transport_sse.py` (REWRITE, ~200 lines)

```python
"""
MCP over Server-Sent Events.
SSE endpoint: GET /mcp/v1/{slug}/sse
Message endpoint: POST /mcp/v1/{slug}/message
"""

import json
import uuid
from sse_starlette.sse import EventSourceResponse
from app.gateway.tool_dispatcher import ToolDispatcher
from app.gateway.session import SessionManager
from app.services.server_config_cache import ServerConfigCache
from app.gateway.rate_limiter import GatewayRateLimiter
from app.gateway.errors import (
    tool_not_found_error, invalid_params_error, upstream_error,
    rate_limit_error, method_not_found_error, internal_error,
)

class SSESession:
    def __init__(self, session_id: str, server_id: str, user_id: str, slug: str):
        self.session_id = session_id
        self.server_id = server_id
        self.user_id = user_id
        self.slug = slug
        self.initialized = False
        self.created_at = datetime.utcnow()

session_manager = SessionManager()

async def handle_sse_connection(
    request: Request,
    slug: str,
    current_user: User = Depends(get_current_user_required),
):
    """SSE endpoint: client opens connection, we stream events."""
    
    # 1. Get server config
    server_config = await ServerConfigCache.get(slug)
    if not server_config:
        raise HTTPException(404, "Server not found")
    
    if server_config["user_id"] != current_user.id:
        # Free tier: only the owner can connect
        # Pro tier: team members can connect (handled in F7)
        if current_user.plan == "free" and server_config["user_id"] != current_user.id:
            raise HTTPException(403, "Not authorized for this server")
    
    if server_config["status"] != "active":
        raise HTTPException(404, f"Server is {server_config['status']}, not active")
    
    # 2. Generate session ID
    session_id = str(uuid.uuid4())
    session = SSESession(session_id, str(server_config["server_id"]), str(current_user.id), slug)
    await session_manager.add(session)
    
    # 3. Stream
    async def event_generator():
        try:
            # Send session ready event
            yield {
                "event": "endpoint",
                "data": json.dumps({"sessionId": session_id}),
            }
            
            # Heartbeat every 15s
            while True:
                if await request.is_disconnected():
                    break
                yield {"event": "ping", "data": ""}
                await asyncio.sleep(15)
        finally:
            await session_manager.remove(session_id)
    
    return EventSourceResponse(
        event_generator(),
        ping=15,
        headers={
            "X-Accel-Buffering": "no",  # nginx compat
            "MCP-Session-Id": session_id,
        },
    )

async def handle_sse_message(
    request: Request,
    slug: str,
    session_id: str = Header(..., alias="MCP-Session-Id"),
    current_user: User = Depends(get_current_user_required),
):
    """Message endpoint: client POSTs JSON-RPC, we send response back via SSE."""
    
    # 1. Get server config
    server_config = await ServerConfigCache.get(slug)
    if not server_config:
        raise HTTPException(404, "Server not found")
    
    # 2. Get session
    session = await session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    if session.user_id != str(current_user.id):
        raise HTTPException(403, "Session not owned by you")
    
    # 3. Parse JSON-RPC
    body = await request.json()
    request_obj = JSONRPCRequest(**body)
    
    # 4. Route
    response = await route_mcp_request(server_config, session, request_obj)
    
    return response  # JSON response (sent back to client; SSE event_id can be added for resumability)

async def route_mcp_request(server_config, session, request: JSONRPCRequest) -> dict:
    method = request.method
    params = request.params or {}
    
    if method == "initialize":
        session.initialized = True
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mcpforge-gateway", "version": "1.0.0"},
            },
        }
    
    if method == "notifications/initialized":
        return None  # no response for notifications
    
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request.id, "result": {}}
    
    if method == "tools/list":
        tools = server_config["tools_config"].get("tools", [])
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "tools": [
                    {
                        "name": t.get("ai_enhanced_name") or t["name"],
                        "description": t.get("ai_enhanced_description") or t.get("description", ""),
                        "inputSchema": t.get("inputSchema", {"type": "object", "properties": {}}),
                        "annotations": t.get("annotations", {}),
                    }
                    for t in tools
                ],
            },
        }
    
    if method == "tools/call":
        # Rate limit
        rate_limit = await GatewayRateLimiter().check(UUID(server_config["server_id"]), server_config["plan"])
        if not rate_limit.allowed:
            return rate_limit_error(request.id, rate_limit)
        
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Find tool
        tools = server_config["tools_config"].get("tools", [])
        tool = next((t for t in tools if t["name"] == tool_name or t.get("ai_enhanced_name") == tool_name), None)
        if not tool:
            return tool_not_found_error(request.id, tool_name)
        
        # Dispatch
        try:
            dispatcher = ToolDispatcher()
            result = await dispatcher.dispatch(
                server_config=server_config,
                tool=tool,
                arguments=arguments,
                request_id=str(request.id),
            )
            
            # Update call counts (async, non-blocking)
            asyncio.create_task(update_call_counts(UUID(server_config["server_id"])))
            
            # Emit analytics event
            asyncio.create_task(emit_analytics_event(
                server_id=UUID(server_config["server_id"]),
                tool_name=tool_name,
                status="success" if not result.get("isError") else "error",
                latency_ms=...,  # measure
            ))
            
            return {"jsonrpc": "2.0", "id": request.id, "result": result}
        except UpstreamError as e:
            return upstream_error(request.id, e)
        except InvalidParamsError as e:
            return invalid_params_error(request.id, e)
        except SSRFBlockedError as e:
            return ssrf_error(request.id, e)
    
    if method == "notifications/cancelled":
        # Could implement request cancellation; for v1.0, just acknowledge
        return None
    
    return method_not_found_error(request.id, method)
```

#### `app/gateway/transport_http.py` (REWRITE, ~100 lines)

```python
"""
MCP over Streamable HTTP.
Single endpoint: POST /mcp/v1/{slug}/
- POST: send JSON-RPC
- GET: open SSE stream (for server-initiated events)
"""

async def handle_http_request(
    request: Request,
    slug: str,
    current_user: User = Depends(get_current_user_required),
):
    if request.method == "POST":
        body = await request.json()
        request_obj = JSONRPCRequest(**body)
        
        # Get server config
        server_config = await ServerConfigCache.get(slug)
        if not server_config:
            raise HTTPException(404, "Server not found")
        
        if server_config["status"] != "active":
            raise HTTPException(404, f"Server {server_config['status']}")
        
        # Get or create session
        session_id = request.headers.get("MCP-Session-Id")
        if not session_id:
            session_id = str(uuid.uuid4())
        
        session = await session_manager.get(session_id) or SSESession(session_id, ...)
        await session_manager.add(session)
        
        # Route
        response = await route_mcp_request(server_config, session, request_obj)
        
        if response is None:
            # Notification: return 202 Accepted
            return Response(status_code=202, headers={"MCP-Session-Id": session_id})
        
        return Response(
            content=json.dumps(response),
            media_type="application/json",
            headers={"MCP-Session-Id": session_id},
        )
    
    elif request.method == "GET":
        # Open SSE stream for server-initiated messages
        # For v1.0, we don't push from server; just heartbeat
        async def event_generator():
            while True:
                if await request.is_disconnected():
                    break
                yield {"event": "ping", "data": ""}
                await asyncio.sleep(15)
        return EventSourceResponse(event_generator(), ping=15)
```

#### `app/services/server_config_cache.py` (NEW, ~80 lines)

```python
"""
Caches server config in Redis for fast gateway lookups.
Invalidated on server PATCH.
"""

CACHE_TTL_SECONDS = 300  # 5 min

class ServerConfigCache:
    @staticmethod
    async def get(slug: str) -> dict | None:
        r = await get_redis()
        cached = await r.get(f"server_config:{slug}")
        if cached:
            return json.loads(cached)
        
        # Cache miss — load from DB
        async with async_session_factory() as session:
            repo = MCPServerRepository(session)
            server = await repo.get_by_slug(slug)
            if not server:
                return None
            
            config = {
                "server_id": str(server.id),
                "user_id": str(server.user_id),
                "slug": server.slug,
                "name": server.name,
                "base_url": server.base_url,
                "auth_scheme": server.auth_scheme,
                "auth_header_name": server.auth_header_name,
                "tools_config": server.tools_config,
                "status": server.status,
                "plan": server.owner.plan if server.owner else "free",
            }
            
            # Cache it
            await r.setex(f"server_config:{slug}", CACHE_TTL_SECONDS, json.dumps(config, default=str))
            return config
    
    @staticmethod
    async def invalidate(slug: str) -> None:
        r = await get_redis()
        await r.delete(f"server_config:{slug}")
```

### 4.6 Test plan

| File | Test count | Coverage |
|---|---|---|
| `test_transport_sse.py` | 8 | initialize returns correct capabilities, tools/list returns tools, tools/call success, tools/call tool not found, session validation, heartbeat, disconnect cleanup, rate limit |
| `test_transport_http.py` | 8 | POST initialize, POST tools/list, POST tools/call, notification 202, GET SSE stream, MCP-Session-Id header required, invalid session, wrong owner |
| `test_tool_dispatcher.py` | 10 | basic GET, POST with body, path params, query params, header auth, bearer auth, basic auth, 4xx upstream, 5xx upstream, timeout |
| `test_response_handler.py` | 8 | JSON response, truncated (>100KB), base64 binary, HTML stripping, text response, 4xx body, 5xx body, size limit |
| `test_ssrf_guard.py` | 10 | private IP (10.x), private IP (172.16.x), private IP (192.168.x), loopback, AWS metadata (169.254), 0.0.0.0, IPv6 loopback, IPv6 ULA, IPv6 link-local, public IP allowed |
| `test_auth_header_builder.py` | 6 | none, api_key with custom header, api_key with default header, bearer, basic (encoding correct), oauth2 |
| `test_rate_limiter.py` | 6 | first request allowed, hour limit hit, month limit hit, free plan limit, pro plan limit, atomic (concurrent requests don't exceed) |
| `test_server_config_cache.py` | 6 | cache miss loads from DB, cache hit returns cached, TTL expiry, invalidation, status changes reflected, deleted server returns None |
| `test_gateway_e2e.py` | 8 | full flow: init → list → call, full flow with SSE, full flow with HTTP, pause stops calls, resume allows calls, free tier limit reached, credential decrypt success, credential decrypt fails gracefully |

**Mocking strategy:**
- `httpx.MockTransport` for outbound HTTP calls
- `fakeredis` for Redis
- Real session manager and dispatcher (integration)
- For full e2e, use FastAPI TestClient with mocked auth

---

## 5. Frontend Changes

### 5.1 New pages / components

```
src/components/server/
├── connect-panel.tsx                (NEW: gateway URL, copy buttons, configs)
├── gateway-url-display.tsx          (NEW: with copy button)
├── claude-desktop-config.tsx        (NEW: pre-filled JSON)
├── cursor-config.tsx                (NEW: pre-filled JSON)
├── test-connection-button.tsx       (NEW: calls /connect/test)
├── pause-resume-toggle.tsx          (NEW: server status toggle)
└── deploy-button.tsx                (NEW: triggers F5 scan + deploy)
```

### 5.2 New hooks

```typescript
// src/hooks/use-gateway.ts (NEW)
export function useConnectPanel(serverId: string) {
  return useQuery({
    queryKey: ['connect-panel', serverId],
    queryFn: () => api.servers.getConnectPanel(serverId),
  });
}

export function useTestConnection(serverId: string) {
  return useMutation({
    mutationFn: () => api.servers.testConnection(serverId),
  });
}

export function usePauseServer(serverId: string) {
  return useMutation({
    mutationFn: () => api.servers.pause(serverId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['server', serverId] });
    },
  });
}

export function useResumeServer(serverId: string) {
  return useMutation({
    mutationFn: () => api.servers.resume(serverId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['server', serverId] });
    },
  });
}

export function useDeployServer(serverId: string) {
  return useMutation({
    mutationFn: () => api.servers.deploy(serverId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['server', serverId] });
    },
  });
}
```

### 5.3 New endpoints in `lib/api.ts`

```typescript
servers: {
  // ... existing from F1, F2 ...
  getConnectPanel: (serverId: string) => request<ConnectPanelResponse>(`/api/v1/servers/${serverId}/connect`),
  testConnection: (serverId: string) => request<TestConnectionResponse>(`/api/v1/servers/${serverId}/connect/test`, { method: 'POST' }),
  deploy: (serverId: string) => request<{ deployment_id: string; scan_id: string }>(`/api/v1/servers/${serverId}/deploy`, { method: 'POST' }),
  pause: (serverId: string) => request<PauseResponse>(`/api/v1/servers/${serverId}/pause`, { method: 'POST' }),
  resume: (serverId: string) => request<PauseResponse>(`/api/v1/servers/${serverId}/resume`, { method: 'POST' }),
},
```

### 5.4 Test plan

**Playwright E2E:**
- `06-deploy-and-connect.spec.ts`: create server → deploy → see connect panel → copy Claude config → see in clipboard
- `07-pause-resume.spec.ts`: pause server → test connection fails → resume → test connection succeeds

---

## 6. Database / Migration Plan

No new tables needed. Uses existing `mcp_servers`, `credentials`, `server_versions`.

The `mcp_servers.status` field is updated to `"active" | "paused"`. The existing default is `"building"`. The flow becomes:
- Created: `"draft"` (NEW status, set in F1)
- After build pipeline: `"review"`
- After deploy: `"active"`
- After pause: `"paused"`
- Error: `"error"`

This may require a small migration to update the default or add a constraint:
```python
# Optional migration
op.execute("UPDATE mcp_servers SET status = 'draft' WHERE status = 'building'")
# Add a CHECK constraint (Postgres-only)
op.create_check_constraint("ck_mcp_servers_status", "mcp_servers", "status IN ('draft', 'review', 'active', 'paused', 'error', 'building')")
```

---

## 7. Environment Variables

No new env vars. Uses existing Redis, JWT, etc.

---

## 8. Observability

### 8.1 Structured logs

```python
logger.info("gateway_request", server_slug=slug, method=method, request_id=request_id, user_id=str(user.id))
logger.info("gateway_response", server_slug=slug, method=method, status_code=response_code, latency_ms=duration, request_id=request_id)
logger.warning("gateway_rate_limited", server_id=server_id, plan=plan, denial_reason=reason, request_id=request_id)
logger.warning("gateway_upstream_error", server_id=server_id, tool=tool_name, status_code=upstream_status, duration_ms=duration, request_id=request_id)
logger.error("gateway_ssrf_blocked", server_id=server_id, url=url, ip=ip_str, request_id=request_id)
logger.error("gateway_credential_error", server_id=server_id, request_id=request_id)
```

### 8.2 Metrics (counted in DB, not Prometheus)

- `mcp_servers.total_calls`, `mcp_servers.monthly_calls` — atomic increment per call
- `tool_calls` table (created in F6) — per-call records (sampled, async)
- We can derive: P50/P95 latency, error rate, rate limit hit rate

### 8.3 Sentry

- Upstream 5xx errors NOT captured (user's API issue, not ours)
- SSRF blocks captured as breadcrumbs (potential attack signal)
- Internal gateway errors captured

---

## 9. Edge Cases & Failure Modes

| Edge case | Detection | Response |
|---|---|---|
| Server not found | Cache miss + DB miss | 404 |
| Server paused | Status check | 404 with status |
| Server in review/draft | Status check | 404 with status |
| Rate limit exceeded | Redis check | MCP `RateLimitExceeded` (-32003) with retry-after |
| Tool not found in tools_config | Lookup | MCP `ToolNotFound` (-32001) |
| Required argument missing | Basic validation | MCP `InvalidParams` (-32602) |
| Upstream returns 5xx | Status check | MCP `UpstreamError` (-32002) with status code + sanitized body |
| Upstream returns 4xx | Status check | MCP result with `isError: true` and body (LLM can self-correct) |
| Upstream times out (5s) | httpx timeout | MCP `UpstreamError` with timeout message |
| Upstream returns HTML | Content-type check | Strip HTML, return plain text error |
| Upstream returns >5MB | Response size check before buffering | 413 (gateway memory protection) |
| Upstream returns 100KB-5MB | Response size check | Truncate to 100KB, add `_truncated: true` |
| Upstream returns binary | Content-type check | Base64 encode + MIME type annotation |
| User IP in `Authorization` header to internal IP | SSRF guard | MCP `SSRFBlocked` (-32005) |
| Concurrent calls to same server exceed limit | Redis atomic | Some get `RateLimitExceeded` |
| Credential decryption fails | Fernet error | MCP `CredentialError` (-32006) with safe message |
| User changes server config while in flight | Cache invalidation | Next call gets new config; in-flight uses old |
| User deletes server while in flight | Cache may be stale | Tools/call returns ToolNotFound |
| Stolen JWT (XSS) | N/A — httpOnly cookies mitigate | (mitigated by Wave 0 hardening) |
| MCP client doesn't send `initialize` first | We don't require it (lenient) | First call works without session |
| MCP client sends `notifications/cancelled` | We log but don't cancel | (v1.0 limitation) |
| Gateway runs out of file descriptors | httpx will fail | 503 to all clients; metrics alert |
| Cloudflare/Render rate limits our IP | Logs | 503 to clients with retry-after |
| Httpx connection leak | try/finally in dispatcher | Cleaned up |

---

## 10. Definition of Done

- [ ] `sse-starlette` added to pyproject.toml
- [ ] `app/gateway/transport_sse.py` REWRITTEN with full MCP protocol
- [ ] `app/gateway/transport_http.py` REWRITTEN with full StreamableHTTP
- [ ] `app/gateway/mcp_server.py` updated to wire new handlers
- [ ] `app/gateway/session.py` implemented
- [ ] `app/gateway/tool_dispatcher.py` implemented (200 lines)
- [ ] `app/gateway/response_handler.py` implemented
- [ ] `app/gateway/ssrf_guard.py` implemented
- [ ] `app/gateway/auth_header_builder.py` implemented
- [ ] `app/gateway/rate_limiter.py` implemented
- [ ] `app/services/server_config_cache.py` implemented
- [ ] `app/schemas/mcp_protocol.py` implemented
- [ ] `app/schemas/gateway.py` implemented
- [ ] `app/api/v1/endpoints/gateway_admin.py` implemented (deploy/pause/resume/connect)
- [ ] All gateway routes require JWT auth
- [ ] `app/main.py` registers gateway routes
- [ ] Backend tests: 70+ tests for F4, all passing
- [ ] Frontend: `components/server/connect-panel.tsx` and related components
- [ ] Frontend: `hooks/use-gateway.ts`
- [ ] Playwright E2E: deploy + connect flow
- [ ] Manual test: end-to-end with Claude Desktop (register, build, deploy, add to Claude, call a tool)
- [ ] CI: all checks pass
- [ ] No credentials in any log line
- [ ] SSRF guard verified (curl to 169.254.169.254 returns SSRF error)

---

## 11. Build Sequence (for AI agents)

### Step 1: Foundation
- [ ] Add `sse-starlette>=2.1.0` to `apps/api/pyproject.toml`
- [ ] Run `uv sync`

### Step 2: Schemas
- [ ] Create `app/schemas/mcp_protocol.py` with JSON-RPC types
- [ ] Create `app/schemas/gateway.py` with connect panel, deploy, pause responses

### Step 3: SSRF guard
- [ ] Create `app/gateway/ssrf_guard.py` (60 lines)
- [ ] Create `tests/test_ssrf_guard.py` (10 tests)

### Step 4: Auth header builder
- [ ] Create `app/gateway/auth_header_builder.py` (50 lines)
- [ ] Create `tests/test_auth_header_builder.py` (6 tests)

### Step 5: Response handler
- [ ] Create `app/gateway/response_handler.py` (100 lines)
- [ ] Create `tests/test_response_handler.py` (8 tests)

### Step 6: Rate limiter
- [ ] Create `app/gateway/rate_limiter.py` (100 lines)
- [ ] Create `tests/test_rate_limiter.py` (6 tests using fakeredis)

### Step 7: Server config cache
- [ ] Create `app/services/server_config_cache.py` (80 lines)
- [ ] Create `tests/test_server_config_cache.py` (6 tests)

### Step 8: Tool dispatcher
- [ ] Create `app/gateway/tool_dispatcher.py` (200 lines)
- [ ] Create `tests/test_tool_dispatcher.py` (10 tests with httpx MockTransport)

### Step 9: SSE transport
- [ ] REWRITE `app/gateway/transport_sse.py` (200 lines)
- [ ] Create `app/gateway/session.py` (50 lines)
- [ ] Create `tests/test_transport_sse.py` (8 tests)

### Step 10: HTTP transport
- [ ] REWRITE `app/gateway/transport_http.py` (100 lines)
- [ ] Create `tests/test_transport_http.py` (8 tests)

### Step 11: Gateway admin endpoints
- [ ] Create `app/api/v1/endpoints/gateway_admin.py` (deploy, pause, resume, connect)
- [ ] Update `app/main.py` to include gateway_admin router
- [ ] Create `tests/test_gateway_admin.py` (5 tests)

### Step 12: Wire into main app
- [ ] Update `app/main.py`:
  - Register gateway routes
  - All gateway routes require JWT (via dependency)
- [ ] Update `app/api/deps.py` to add `get_current_user_required` (vs `get_optional_current_user`)

### Step 13: Cache invalidation
- [ ] Update `app/services/mcp_server_service.py` to invalidate cache on PATCH
- [ ] Update `app/services/credential_service.py` to invalidate cache on credential change (since auth scheme might change)

### Step 14: Status pause propagation
- [ ] On pause: write to DB + publish to Redis pub/sub channel `server_status:{slug}`
- [ ] Gateway listens to channel, updates in-memory state (or just always reads cache, which is invalidated)
- [ ] Decision: use cache invalidation only (simpler). 5-second TTL means worst case 5s propagation.

### Step 15: Full e2e tests
- [ ] Create `tests/test_gateway_e2e.py` (8 tests)
- [ ] Mock all external (httpx + Redis)
- [ ] Verify full JSON-RPC request/response

### Step 16: Frontend connect panel
- [ ] Add `src/components/server/connect-panel.tsx`
- [ ] Add `src/components/server/gateway-url-display.tsx`
- [ ] Add `src/components/server/claude-desktop-config.tsx`
- [ ] Add `src/components/server/cursor-config.tsx`
- [ ] Add `src/components/server/test-connection-button.tsx`
- [ ] Add `src/components/server/pause-resume-toggle.tsx`
- [ ] Add `src/components/server/deploy-button.tsx`

### Step 17: Frontend hooks
- [ ] Create `src/hooks/use-gateway.ts` (5 hooks)

### Step 18: Frontend API client
- [ ] Update `src/lib/api.ts` with new endpoints

### Step 19: Wire into server detail page
- [ ] Add "Settings" tab to `app/(dashboard)/servers/[slug]/page.tsx`
- [ ] Settings tab shows: connect panel, pause/resume, deploy

### Step 20: Playwright E2E
- [ ] `06-deploy-and-connect.spec.ts`
- [ ] `07-pause-resume.spec.ts`

### Step 21: Manual end-to-end test (THE MOMENT OF TRUTH)
- [ ] Run full stack locally
- [ ] Create a server with a public API (e.g., httpbin.org or a mock)
- [ ] Deploy it (after F5 scan)
- [ ] Copy the Claude Desktop config
- [ ] Add to claude_desktop_config.json
- [ ] Restart Claude Desktop
- [ ] Call a tool from Claude
- [ ] Verify it works
- [ ] Check logs: no credentials, no errors, request_id correlation working
- [ ] Check analytics: total_calls incremented
- [ ] Pause server
- [ ] Wait 10s
- [ ] Try to call from Claude Desktop — should fail with MCP error

**Total estimated time:** 6-8 days for one engineer.

---

## 12. Open Questions

- **Q1 (P0):** Should we cache tool call responses in Redis? (Decision: no for v1.0; live calls only. Caching adds invalidation complexity.)
- **Q2 (P1):** How long should sessions live? (Decision: 30 min idle. After 30 min no activity, session is removed. Claude Desktop reconnects automatically.)
- **Q3 (P1):** Should we support SSE keep-alive via the message channel? (Decision: yes — heartbeat every 15s via SSE endpoint. Long-lived connections stay open.)
- **Q4 (P2):** Should we implement `notifications/cancelled`? (Decision: log but don't cancel. v1.1.)
- **Q5 (P2):** Should we record the upstream HTTP request/response for debugging? (Decision: no — privacy. F6 analytics can sample if needed.)

---

*See `features/06-FEATURE-SECURITY-SCANNER.md` for the security scan that gates deployment. See `features/04-FEATURE-MCP-PLAYGROUND.md` for the browser-based testing of deployed servers.*
