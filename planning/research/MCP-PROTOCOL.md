# MCP Protocol — Reference

> **For AI agents:** Reference documentation for the Model Context Protocol (MCP) — the wire protocol our gateway implements. Use this when building F4 (Gateway), F3 (Playground), or debugging MCP interactions.

---

## 1. Official Sources

- **Docs site:** https://modelcontextprotocol.io
- **Specification (latest):** https://modelcontextprotocol.io/specification/latest
- **TypeScript schema (source of truth):** https://github.com/modelcontextprotocol/specification/blob/main/schema/2025-11-25/schema.ts
- **JSON Schema:** https://github.com/modelcontextprotocol/specification/blob/main/schema/2025-11-25/schema.json
- **llms.txt (full index):** https://modelcontextprotocol.io/llms.txt

## 2. Official SDKs

The `modelcontextprotocol` GitHub org maintains **10 SDKs**:

| SDK | Language | Stars | Package |
|---|---|---|---|
| [python-sdk](https://github.com/modelcontextprotocol/python-sdk) | Python | 23.3k | `mcp` (PyPI) |
| [typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk) | TypeScript | 12.6k | `@modelcontextprotocol/sdk` |
| [java-sdk](https://github.com/modelcontextprotocol/java-sdk) | Java | — | — |
| [kotlin-sdk](https://github.com/modelcontextprotocol/kotlin-sdk) | Kotlin | — | — |
| [csharp-sdk](https://github.com/modelcontextprotocol/csharp-sdk) | C# | 4.3k | — |
| [go-sdk](https://github.com/modelcontextprotocol/go-sdk) | Go | — | — |
| [rust-sdk](https://github.com/modelcontextprotocol/rust-sdk) | Rust | 3.5k | — |
| [swift-sdk](https://github.com/modelcontextprotocol/swift-sdk) | Swift | — | — |
| [php-sdk](https://github.com/modelcontextprotocol/php-sdk) | PHP | — | — |
| [ruby-sdk](https://github.com/modelcontextprotocol/ruby-sdk) | Ruby | — | — |

**For MCPForge:** Use the **Python `mcp` SDK** for client-side logic and reference patterns. We don't need to use it as a server runtime — we implement the protocol directly in FastAPI for fine control over auth, rate limits, and credential handling.

## 3. JSON-RPC 2.0 Base

**All messages MUST follow JSON-RPC 2.0.**

### Request
```json
{
  "jsonrpc": "2.0",
  "id": "string-or-number",     // MUST NOT be null, MUST NOT be reused in session
  "method": "string",
  "params": {}                   // optional
}
```

### Response (success)
```json
{ "jsonrpc": "2.0", "id": "...", "result": {} }
```

### Response (error)
```json
{
  "jsonrpc": "2.0",
  "id": "...",
  "error": { "code": -32601, "message": "...", "data": {} }
}
```

### Notification (no response)
```json
{ "jsonrpc": "2.0", "method": "string", "params": {} }
```

## 4. Lifecycle Methods (REQUIRED)

| Method | Direction | Description |
|---|---|---|
| `initialize` | Client → Server | First message. Negotiates protocol version + capabilities |
| `notifications/initialized` | Client → Server | After `initialize` succeeds |
| `ping` | Bidirectional | Health check, respond with `{}` |

**initialize response example:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {
      "tools": { "listChanged": false }
    },
    "serverInfo": {
      "name": "mcpforge-gateway",
      "version": "1.0.0"
    }
  }
}
```

## 5. Server Feature Methods

| Method | Required When | Direction |
|---|---|---|
| `tools/list` | Server declares `tools` capability | Client → Server |
| `tools/call` | Server declares `tools` capability | Client → Server |
| `notifications/tools/list_changed` | `listChanged: true` | Server → Client |
| `resources/list` | Server declares `resources` capability | Client → Server |
| `resources/read` | Server declares `resources` capability | Client → Server |
| `resources/subscribe` | Optional | Client → Server |
| `prompts/list` | Server declares `prompts` capability | Client → Server |
| `prompts/get` | Server declares `prompts` capability | Client → Server |
| `logging/setLevel` | Optional | Client → Server |
| `completion/complete` | Optional | Client → Server |

**For MCPForge v1.0:** Implement `tools/list` and `tools/call` only. Defer resources/prompts to v1.2.

## 6. Tool Definition Schema

```typescript
{
  name: string;              // 1-128 chars, [A-Za-z0-9_\-.] only, case-sensitive, unique
  description: string;       // CRITICAL — see arxiv 2602.18914
  inputSchema: {             // JSON Schema 2020-12
    type: "object",
    properties: { ... },
    required: ["..."]
  };
  outputSchema?: { ... };    // optional, for structured outputs
  annotations?: {
    readOnlyHint?: boolean;     // tool doesn't modify state
    destructiveHint?: boolean;  // tool may delete or modify permanently
    idempotentHint?: boolean;  // same args = same result
    openWorldHint?: boolean;   // interacts with external entities
  };
  execution?: { taskSupport: "forbidden" | "optional" | "required" };
  icons?: Array<{ src, mimeType, sizes, theme }>;
}
```

**Annotations are critical for ChatGPT UI safety:** Without `readOnlyHint: true`, ChatGPT shows "DESTRUCTIVE" warning for every tool. Without `destructiveHint: true` on a DELETE method, ChatGPT skips confirmation prompts. These affect user experience, not security.

**Description is untrusted** by the spec, but in MCPForge the description comes from our AI pipeline, so we trust it.

## 7. tools/call Request

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "search_products",
    "arguments": {
      "query": "red shoes",
      "limit": 20
    }
  }
}
```

## 8. tools/call Response (success)

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Found 3 products:\n1. Red shoes ($29.99)\n2. ..."
      }
    ],
    "isError": false
  }
}
```

**Content types:**
- `text` — plain text
- `image` — `{ type: "image", data: "<base64>", mimeType: "image/png" }`
- `audio` — `{ type: "audio", data: "<base64>", mimeType: "audio/mpeg" }`
- `resource` — `{ type: "resource", resource: { uri, mimeType, text/blob } }`

**For MCPForge:** Use `text` for all responses (we serialize binary as base64 text with MIME annotation).

## 9. tools/call Response (error)

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      { "type": "text", "text": "Error: invalid query parameter 'limit' (must be positive integer)" }
    ],
    "isError": true
  }
}
```

**Important:** Tool execution errors use `isError: true` (not JSON-RPC error format), so the LLM can self-correct.

## 10. Standard JSON-RPC Error Codes

| Code | Name | When to use |
|---|---|---|
| `-32700` | Parse Error | Invalid JSON received |
| `-32600` | Invalid Request | JSON valid but not Request/Notification |
| `-32601` | Method Not Found | Unknown method |
| `-32602` | Invalid Params | Invalid method parameters |
| `-32603` | Internal Error | Internal server error |
| `-32000` to `-32099` | Server Error | Implementation-defined |

**For MCPForge, custom error codes:**
- `-32001` ToolNotFound
- `-32002` UpstreamError
- `-32003` RateLimitExceeded
- `-32004` ServerDisabled
- `-32005` SSRFBlocked
- `-32006` CredentialError
- `-32007` Timeout

## 11. Transport: Streamable HTTP (recommended)

**Single endpoint supporting both POST and GET.**

### POST
- Send JSON-RPC request
- If request: server returns `text/event-stream` (SSE) OR `application/json` (sync)
- If notification: server returns `202 Accepted` (no body)
- Response includes `MCP-Session-Id` header (UUID)

### GET
- Open SSE stream to receive server-initiated messages
- Use `Last-Event-ID` header for resumability

### SSE wire format
```
event: message
id: unique-event-id
data: {"jsonrpc":"2.0","method":"...","params":{...}}

```
- Each field on its own line
- Empty line separates events
- `data:` is the JSON payload
- `event:` is the message type (optional, default = `message`)
- `id:` enables resumability

## 12. Transport: SSE (legacy, from v2024-11-05)

- Separate SSE endpoint + POST endpoint
- Kept for backwards compat with ChatGPT Workspace Agents
- MCPForge supports both (SSE at `/mcp/v1/{slug}/sse`, HTTP at `/mcp/v1/{slug}/`)

## 13. Transport: stdio (local CLI)

- Client launches server as subprocess
- Server reads JSON-RPC from stdin, writes to stdout
- Messages delimited by newlines
- Server logs go to stderr
- Used by Claude Desktop for local MCP servers

**For MCPForge:** Not used. We're a hosted gateway.

## 14. Session Management

- Server generates `MCP-Session-Id` (UUID v4) on `initialize`
- Returned in `MCP-Session-Id` response header
- Client includes it in subsequent requests
- Sessions can be reused across requests (Claude Desktop does this)
- Server can invalidate session (e.g., on credential change)

**For MCPForge v1.0:** Session state is minimal (just the ID). No Redis storage of session contents. If server is restarted, sessions are lost; clients reconnect.

## 15. clientInfo (for analytics)

During `initialize`, clients identify themselves:
```json
{
  "clientInfo": {
    "name": "Claude Desktop",
    "version": "0.1.0"
  }
}
```

**Known values:**
- `claude-ai` → claude.ai web
- `claude-desktop` → Claude Desktop app
- `cursor` → Cursor IDE
- `github-copilot` → VS Code Copilot

**For MCPForge:** Extract `clientInfo.name` and store as `tool_calls.client_name` for F6 analytics.

## 16. FastAPI + MCP Integration Patterns

### Using FastMCP (Python SDK reference)
```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("My MCP Server", json_response=True)
streamable_app = mcp.streamable_http_app()
sse_app = mcp.sse_app()
```

**MCPForge doesn't use FastMCP** — we implement the protocol directly. But reading FastMCP source is useful for reference patterns.

### SSE in FastAPI with sse-starlette
```python
from sse_starlette.sse import EventSourceResponse
from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/stream")
async def stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            yield {"event": "message", "data": "hello"}
            await asyncio.sleep(1)
    
    return EventSourceResponse(
        event_generator(),
        ping=15,  # heartbeat every 15s
        headers={"X-Accel-Buffering": "no"}  # nginx compat
    )
```

### Gotchas
1. **`/mcp` path suffix required** for some clients (ChatGPT)
2. **Auth middleware exclusion:** exclude `/mcp` from API key checks
3. **DNS rebinding protection:** FastMCP enables by default
4. **Lifespan context required:** without `async with mcp.session_manager.run()` you get `RuntimeError`
5. **Nginx proxying:** need `proxy_buffering off; proxy_read_timeout 120s;`
6. **Cold starts on serverless:** pre-warm via health check pings
7. **`readOnlyHint` for tools:** without it, ChatGPT shows "DESTRUCTIVE" warnings

## 17. Production Patterns from Leading Implementations

### Stripe MCP
- Two tool groups: Account + Knowledge retrieval
- Naming: `verb_noun` (`create_customer`, `list_invoices`)
- Restricted API keys as fallback
- "Short tool descriptions, narrow argument types, hard cap on tool calls per turn beat any amount of prompt engineering"

### Cloudflare MCP
- **Code Mode:** 2 tools (`search` + `execute`) for 2,500+ endpoints → 99.9% token reduction
- OAuth 2.1 + PKCE
- Dynamic V8 isolate for safe code execution

### Anthropic's production guide
- **Tool descriptions are more important than tool implementation** — "The LLM decides whether to call your tool based on the description"
- Write descriptions as usage guides, not API docs: "Write the description as if you're explaining to a smart colleague when they should use this function"
- Optimal length: 2-4 sentences per tool
- Anti-pattern: version suffixes in tool names (`FetchResources_v2`) — agents can't determine which to invoke

### Production deployment lessons
1. **Tool descriptions > tool code** — agents select by name/description only
2. **Descriptions are prompts** — they go into LLM context; treat as code
3. **Rate limit by tool, not globally** — different costs
4. **Return structured errors** — `{"code": "NOT_FOUND", "retryable": false}` beats stack traces
5. **Cache `tools/list`** — some clients cache aggressively; restart client after schema changes
6. **OAuth 2.1 + DCR** is the emerging standard
7. **StreamableHTTP over SSE** for new deployments
8. **Log `tool_name, duration_ms, ok/error`** on every request

## 18. Security Notes (CVE-2025-49596)

**MCP Inspector had a critical RCE (CVSS 9.4):**
- Missing auth between Inspector client and proxy
- Proxy listened on `0.0.0.0:6277` (all interfaces)
- CORS allowed `*`
- "0.0.0.0-day" browser bug: `0.0.0.0` treated as localhost
- Malicious site JS could dispatch to `http://0.0.0.0:6277` → RCE

**Fix (v0.14.1):**
- Session tokens auto-generated and required
- `Allowed-Origin` checks
- Server binds to `127.0.0.1` by default

**Other CVEs:**
- CVE-2025-6514 (CVSS 9.6): mcp-remote OS command injection
- CVE-2025-53109 (CVSS 7.3): Filesystem MCP symlink bypass
- CVE-2025-53110 (CVSS 7.3): Filesystem MCP path traversal
- CVE-2025-54136 (CVSS 8.8): Cursor MCPoison
- CVE-2025-54994 (CVSS 9.3): create-mcp-server-stdio command injection

**For MCPForge:**
- Security-first by default
- Never listen on `0.0.0.0` (production uses Render, not local)
- Session tokens mandatory for all gateway routes
- Build security scanning into platform (F5)
- SSRF guard in gateway
