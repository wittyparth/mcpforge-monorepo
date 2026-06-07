# Feature 3 — Browser MCP Playground

> **PRD reference:** § 7 Feature 3 (lines 325-363)
> **Build order:** Wave 2, Step 1
> **Estimated effort:** 5-7 days for one engineer

---

## 0. TL;DR

A browser-native MCP client that lets users test their MCP servers without Claude Desktop. Communicates with the Gateway over WebSocket, executes real tool calls, shows the MCP protocol JSON in real-time, and persists a session call log. This is the demo differentiator — clicking "Test in Playground" beats any amount of "add to Claude Desktop" instructions.

Pre-deployment: tests against a temporary in-memory server instance. Post-deployment: tests against the live hosted server.

---

## 1. Goals & Non-Goals

### 1.1 In scope
- WebSocket-based playground (real-time, bidirectional)
- Pre-deployment mode: temporary in-memory server instance
- Post-deployment mode: real gateway
- 4-panel UI: Tool Browser / Input Form / Response / Call Log
- Auto-generated forms from tool `inputSchema` (JSON Schema → form fields)
- JSON response viewer with syntax highlighting
- "Share Test" button (URL with pre-filled tool + parameters, credentials stripped)
- Execution timing + status code + response size
- Schema validation errors highlighted in form
- Error display with actionable messages (auth fail, network error, etc.)
- Ephemeral sessions — nothing persisted, no analytics

### 1.2 Out of scope
- Conversation-style chaining of multiple tool calls — v1.1
- Saving call history (everything is ephemeral) — by design
- Multi-user shared playgrounds — v1.1
- Custom tools defined in playground (not from spec) — v1.1

---

## 2. User Stories

- As a user, I can open the Playground from the server detail page.
- As a user, I see a 4-panel layout: Tool Browser / Input Form / Response / Call Log.
- As a user, I can select any tool from the Tool Browser.
- As a user, an input form auto-generates from the tool's inputSchema.
- As a user, required fields are marked with `*`.
- As a user, I can fill the form and click "Call Tool".
- As a user, the response shows: raw JSON (what LLM sees) + formatted view + execution time + status + response size.
- As a user, the Call Log shows history of all calls in this session.
- As a user, I can click "Share Test" to get a URL that pre-loads a specific tool with parameters.
- As a user, the shared URL has all credentials stripped (cannot leak secrets).
- As a user, I see specific error messages for auth failures, network errors, schema validation errors.

---

## 3. Architecture

### 3.1 Diagram

```
┌──────────────────────┐                    ┌──────────────────────────┐
│  Browser             │   WebSocket        │  Playground Proxy        │
│  (Next.js)           │◄──────────────────►│  (FastAPI, in same proc) │
│                      │   /ws/playground/  │                          │
│  Tool Browser        │   {slug}?token=... │  ┌────────────────────┐  │
│  Input Form          │                    │  │  PlaygroundSession │  │
│  Response Viewer     │   JSON-RPC         │  │  (ephemeral)        │  │
│  Call Log            │   over WebSocket   │  └─────────┬──────────┘  │
└──────────────────────┘                    │            │             │
                                            │            ▼             │
                                            │  ┌────────────────────┐  │
                                            │  │  ToolDispatcher    │  │
                                            │  │  (reuse F4)        │  │
                                            │  └─────────┬──────────┘  │
                                            │            │             │
                                            │            ▼             │
                                            │  ┌────────────────────┐  │
                                            │  │  Target API        │  │
                                            │  └────────────────────┘  │
                                            └──────────────────────────┘
```

### 3.2 Data flow

1. User clicks "Open Playground" on server detail page
2. Frontend opens `WebSocket(/ws/playground/{slug}?token={jwt})`
3. Backend creates a `PlaygroundSession` (in-memory, ephemeral)
4. Backend sends `tools/list` response (same as F4, but no caching)
5. User selects a tool → frontend generates form
6. User clicks "Call Tool" → frontend sends `tools/call` JSON-RPC
7. Backend's `PlaygroundProxy` validates, dispatches, returns response
8. Frontend updates Response panel + appends to Call Log
9. On disconnect: session is destroyed

**Pre-deployment mode:** if server is not "active", backend creates a temporary MCP server instance in-process (no Redis cache, no rate limit, no auth checks against the gateway). Uses the same ToolDispatcher.

---

## 4. Backend Changes

### 4.1 REWRITE `app/playground/ws.py` (full impl, ~250 lines)

```python
"""
WebSocket playground. Real-time MCP client/server in the browser.
"""

from fastapi import WebSocket, WebSocketDisconnect, Query, status
from app.gateway.tool_dispatcher import ToolDispatcher
from app.gateway.response_handler import ResponseHandler
from app.services.server_config_cache import ServerConfigCache
from app.core.security import decode_access_token
import json
import asyncio
import uuid

class PlaygroundSession:
    def __init__(self, session_id: str, server_slug: str, user_id: str, server_config: dict | None):
        self.session_id = session_id
        self.server_slug = server_slug
        self.user_id = user_id
        self.server_config = server_config  # None for pre-deployment
        self.created_at = datetime.utcnow()
        self.call_count = 0
        self.last_activity = datetime.utcnow()
        self.dispatcher = ToolDispatcher()

# In-memory session storage (lost on restart — that's the point)
_sessions: dict[str, PlaygroundSession] = {}

async def playground_websocket(
    websocket: WebSocket,
    slug: str,
    token: str = Query(...),
):
    # 1. Authenticate via JWT token
    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # 2. Accept connection
    await websocket.accept()
    
    # 3. Get server config (None for pre-deployment)
    server_config = await ServerConfigCache.get(slug)
    if not server_config:
        # Pre-deployment: load from DB but don't require active
        server_config = await _load_server_draft(slug, user_id)
    
    if not server_config:
        await websocket.send_json({"error": "Server not found or no access"})
        await websocket.close()
        return
    
    if str(server_config.get("user_id")) != user_id:
        await websocket.send_json({"error": "Not your server"})
        await websocket.close()
        return
    
    # 4. Create session
    session_id = str(uuid.uuid4())
    session = PlaygroundSession(session_id, slug, user_id, server_config)
    _sessions[session_id] = session
    
    try:
        # 5. Send tools/list as initial message
        await _send_tools_list(websocket, session)
        
        # 6. Listen for messages
        while True:
            message = await websocket.receive_json()
            await _handle_message(websocket, session, message)
    except WebSocketDisconnect:
        pass
    finally:
        # 7. Cleanup
        _sessions.pop(session_id, None)


async def _handle_message(websocket: WebSocket, session: PlaygroundSession, message: dict):
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})
    
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Find tool
        tools = session.server_config.get("tools_config", {}).get("tools", [])
        tool = next((t for t in tools if t["name"] == tool_name or t.get("ai_enhanced_name") == tool_name), None)
        if not tool:
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32001, "message": f"Tool not found: {tool_name}"},
            })
            return
        
        # Dispatch (reuse F4 dispatcher)
        start = time.time()
        try:
            result = await session.dispatcher.dispatch(
                server_config=session.server_config,
                tool=tool,
                arguments=arguments,
                request_id=str(request_id),
            )
            elapsed_ms = int((time.time() - start) * 1000)
            
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    **result,
                    "_meta": {
                        "latency_ms": elapsed_ms,
                        "tool_name": tool_name,
                    },
                },
            })
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32002,
                    "message": str(e),
                    "data": {"latency_ms": elapsed_ms, "tool_name": tool_name},
                },
            })
    
    elif method == "ping":
        await websocket.send_json({"jsonrpc": "2.0", "id": request_id, "result": {}})


async def _send_tools_list(websocket: WebSocket, session: PlaygroundSession):
    tools = session.server_config.get("tools_config", {}).get("tools", [])
    mcp_tools = [
        {
            "name": t.get("ai_enhanced_name") or t["name"],
            "description": t.get("ai_enhanced_description") or t.get("description", ""),
            "inputSchema": t.get("inputSchema", {"type": "object", "properties": {}}),
        }
        for t in tools
    ]
    await websocket.send_json({
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {"tools": mcp_tools},
    })


async def _load_server_draft(slug: str, user_id: str) -> dict | None:
    """For pre-deployment playground."""
    async with async_session_factory() as session:
        repo = MCPServerRepository(session)
        server = await repo.get_by_slug(slug)
        if not server or str(server.user_id) != user_id:
            return None
        return {
            "server_id": str(server.id),
            "user_id": str(server.user_id),
            "slug": server.slug,
            "name": server.name,
            "base_url": server.base_url,
            "auth_scheme": server.auth_scheme,
            "auth_header_name": server.auth_header_name,
            "tools_config": server.tools_config,
            "status": server.status,
        }
```

### 4.2 New Pydantic schemas

```python
# app/schemas/playground.py (NEW)
class PlaygroundSessionInfo(BaseModel):
    session_id: str
    server_slug: str
    server_name: str
    tools_count: int
    is_pre_deployment: bool
    created_at: datetime

class ShareTestRequest(BaseModel):
    tool_name: str
    parameters: dict
    server_slug: str

class ShareTestResponse(BaseModel):
    share_url: str  # /dashboard/servers/{slug}/playground?tool=...&params=...
    expires_at: datetime  # 7 days
```

### 4.3 Test plan (10+ tests)

- WebSocket connection with valid JWT
- WebSocket connection with invalid JWT (closes)
- Pre-deployment mode (server status != active)
- Post-deployment mode (server status == active)
- tools/list on connect
- tools/call happy path
- tools/call with invalid tool name
- tools/call with upstream 5xx
- ping
- Cleanup on disconnect

---

## 5. Frontend Changes

### 5.1 New components

```
src/components/playground/                  (NEW directory)
├── playground-page.tsx                     # Main 4-panel container (uses resizable-panels)
├── tool-browser.tsx                        # Left panel: list of tools
├── tool-form.tsx                           # Center-top: auto-generated form
├── response-viewer.tsx                     # Center-bottom: JSON response
├── call-log.tsx                            # Right panel: call history
├── json-viewer.tsx                         # Reusable: syntax-highlighted JSON
├── share-test-button.tsx                   # Generate shareable URL
└── form-field-generators/
    ├── string-field.tsx
    ├── number-field.tsx
    ├── boolean-field.tsx
    ├── select-field.tsx                    # For enum types
    ├── array-field.tsx
    ├── object-field.tsx                    # Recursive
    └── json-field.tsx                      # Free-form JSON for complex types
```

### 5.2 New hook

```typescript
// src/hooks/use-playground.ts (NEW)
export function usePlayground(serverSlug: string) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null);
  const [response, setResponse] = useState<CallResponse | null>(null);
  const [callLog, setCallLog] = useState<CallLogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  
  useEffect(() => {
    // Get JWT from cookie
    const token = getCookie('access_token');
    const ws = new WebSocket(`${WS_URL}/ws/playground/${serverSlug}?token=${token}`);
    wsRef.current = ws;
    
    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.method === 'tools/list') {
        setTools(message.params.tools);
      } else if (message.id) {
        // Response to a tools/call
        if (message.error) {
          setResponse({ error: message.error, latency: message.error.data?.latency_ms });
        } else {
          setResponse({ result: message.result });
        }
        setCallLog((prev) => [...prev, { ...message, timestamp: new Date() }]);
      }
    };
    
    return () => ws.close();
  }, [serverSlug]);
  
  const callTool = useCallback((toolName: string, arguments: Record<string, any>) => {
    wsRef.current?.send(JSON.stringify({
      jsonrpc: '2.0',
      id: crypto.randomUUID(),
      method: 'tools/call',
      params: { name: toolName, arguments },
    }));
  }, []);
  
  return { tools, selectedTool, setSelectedTool, response, callLog, isConnected, callTool };
}
```

### 5.3 New route

`/dashboard/servers/[slug]/playground/page.tsx` — uses `usePlayground` hook, renders 4 panels via `react-resizable-panels`.

### 5.4 Auto-generated form

The form generator reads `inputSchema` (JSON Schema) and creates appropriate fields:
- `type: "string"` → text input (or textarea if max length > 100)
- `type: "string", enum: [...]` → select dropdown
- `type: "integer"` / `"number"` → number input
- `type: "boolean"` → switch
- `type: "array"` → repeatable field group
- `type: "object"` → nested field group
- For complex/unknown types → JSON textarea

All fields:
- Mark required (red asterisk) based on `required` array
- Show description from schema
- Validate type on change (show inline error)
- Show example from schema if present

### 5.5 Test plan

**Playwright E2E:**
- `08-playground.spec.ts`: create server, deploy, open playground, call a tool, see response
- `09-playground-share.spec.ts`: call tool, click share, copy URL, open in incognito, see pre-filled form

---

## 6. Database / Migration Plan

No new tables. Uses ephemeral in-memory sessions.

---

## 7. Environment Variables

No new env vars.

---

## 8. Observability

```python
logger.info("playground_session_started", session_id=session_id, slug=slug, user_id=user_id, is_pre_deployment=server_config["status"] != "active")
logger.info("playground_tool_call", session_id=session_id, tool=tool_name, latency_ms=elapsed, status="success"|"error")
logger.info("playground_session_ended", session_id=session_id, duration_seconds=duration, call_count=session.call_count)
```

Note: NO analytics — playground calls are ephemeral, never tracked.

---

## 9. Edge Cases & Failure Modes

| Edge case | Response |
|---|---|
| WebSocket disconnects mid-call | Frontend shows "Reconnecting..."; auto-reconnects with backoff |
| Server has 0 tools | Show "No tools enabled" message in Tool Browser |
| Tool's inputSchema is invalid | Show "Invalid schema" warning; render basic form anyway |
| Tool call takes >30s | Backend timeout; frontend shows timeout error |
| User opens 5 playground tabs | Each gets its own session; no cross-talk |
| User disconnects during slow call | Backend cleans up session; in-flight call continues to completion or times out |
| Pre-deployment mode with no tools_config | Show "Build the server first" message |

---

## 10. Definition of Done

- [ ] `app/playground/ws.py` REWRITTEN with full MCP playground
- [ ] `app/schemas/playground.py` implemented
- [ ] Backend tests: 10+ tests
- [ ] Frontend: 4-panel playground page with resizable layout
- [ ] Frontend: form generator handles all JSON Schema types
- [ ] Frontend: WebSocket hook with reconnection
- [ ] Frontend: JSON viewer with syntax highlighting (Monaco or react-json-view)
- [ ] Playwright E2E passes
- [ ] Manual: deploy a real server, call a tool from playground, see response

---

## 11. Build Sequence (abbreviated)

1. Schemas (`app/schemas/playground.py`)
2. Rewrite `app/playground/ws.py`
3. Backend tests
4. Frontend: `usePlayground` hook
5. Frontend: playground components
6. Frontend: auto-form generator
7. Frontend: route at `/dashboard/servers/[slug]/playground`
8. Playwright tests
9. Manual e2e

---

*See `features/05-FEATURE-MCP-GATEWAY.md` for the gateway that the playground dispatches to.*
