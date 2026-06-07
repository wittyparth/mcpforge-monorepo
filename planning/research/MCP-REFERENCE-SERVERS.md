# MCP Reference Server Implementations — Reference

> **For AI agents:** Reference patterns from the leading production MCP servers (Stripe, Cloudflare, Sentry, Anthropic). Use when building F4 (Gateway) and F3 (Playground).

---

## 1. Stripe MCP Server

- **Hosted:** `https://mcp.stripe.com`
- **Source:** https://github.com/stripe/ai/tree/main/tools/modelcontextprotocol
- **Language:** TypeScript
- **Transport:** stdio (npx-based) + remote
- **Auth:** Restricted API keys
- **Docs:** https://docs.stripe.com/mcp

### 1.1 Architecture
- Uses `@modelcontextprotocol/sdk` to register tools
- Tools map 1:1 to Stripe API endpoints
- API key passed via `--api-key` CLI arg
- Minimal description text — just operation summaries
- Docker support for containerized deployment

### 1.2 Tool naming
- Convention: `verb_noun` (`create_customer`, `list_invoices`, `search_stripe_resources`)
- Two tool groups: Account management + Knowledge retrieval (`search_stripe_documentation`)

### 1.3 Key lesson (per CallSphere analysis)
> "Short tool descriptions, narrow argument types, and a hard cap on tool calls per turn beat any amount of prompt engineering"

### 1.4 Pattern MCPForge adopts
- `verb_noun` naming (matches AI Engine's preference)
- Knowledge retrieval tool separate from action tools
- Restricted API keys for auth

## 2. Cloudflare MCP Server

- **Hosted:** `mcp.cloudflare.com`
- **Source:** https://github.com/cloudflare/mcp
- **Language:** TypeScript (Cloudflare Workers)
- **Transport:** StreamableHTTP
- **Auth:** OAuth 2.1 with PKCE

### 2.1 Revolutionary pattern: Code Mode
- Only **2 tools** (`search()` + `execute()`) for 2,500+ API endpoints
- Reduces token usage by **99.9%**
- Agents write JavaScript to query the OpenAPI spec, then execute discovered endpoints
- Worker Loader API for isolated code execution
- `globalOutbound` for network restriction

### 2.2 Example
```typescript
// Agent code in Worker sandbox:
const products = await search({ endpoint: 'products' });
const stripe = await execute({ endpoint: 'products', method: 'list' });
return stripe.data;
```

### 2.3 Trade-off
- Fewer tokens (good)
- Agents need coding ability (LLM must be capable of writing JS)
- Not a 1:1 tool mapping (slightly different mental model)

### 2.4 OAuth implementation
- `@cloudflare/workers-oauth-provider` library
- Handles PKCE flow automatically
- Downscopes token to selected permissions

### 2.5 Pattern MCPForge considers
- For servers with 200+ tools, offer a "compact mode" toggle
- Use Workers OAuth library patterns if we move to Cloudflare
- See `features/04-FEATURE-MCP-PLAYGROUND.md` for the "large spec warning" that hints at this

## 3. Sentry MCP Server

- **Hosted:** `mcp.sentry.dev`
- **Source:** https://github.com/getsentry/sentry-mcp (706 ★)
- **Language:** TypeScript
- **Transport:** Remote MCP (Cloudflare-based) + stdio fallback
- **Auth:** OAuth 2.1

### 3.1 Architecture
- Built on Cloudflare Workers + Durable Objects
- 16 tools focused on developer debugging workflows
- Some tools use OpenAI/Anthropic for NL→query translation
- "Code Mode" integration: alert → agent investigation → draft PR

### 3.2 Tools (16)
- `whoami` — current user info
- `search_events` — find error events
- `search_issues` — find issues
- `search_tags` — find tag values
- `get_issue_details` — issue details
- `analyze_issue_with_seer` — AI root cause analysis
- `get_issue_summary` — AI summary
- (9 more)

### 3.3 Key architectural decisions (per Sentry blog)

1. **Remote over local:** "STDIO works for advanced users, but cloning the repo, setting up configurations... is a lot of sharp edges"
2. **OAuth over API tokens:** "Making people create API tokens and pass them around is not great"
3. **Cloudflare for scale:** "Because of Sentry's scale, we needed significant user load handling"
4. **SDK instrumentation:** Added MCP support to Sentry's JavaScript SDKs for protocol visibility

### 3.4 Pattern MCPForge adopts
- Remote-first (hosted URL beats local install)
- OAuth preferred over API keys
- Cloudflare as the production runtime
- Instrument with observability

## 4. Anthropic's MCP Servers (Official Examples)

- **Source:** https://github.com/modelcontextprotocol/servers
- **Language:** TypeScript + Python
- **Tools:** 14 reference implementations

### 4.1 Key tools from official examples
- `everything`: Test/demo server with all MCP features
- `fetch`: Web page fetching
- `filesystem`: Local file access
- `git`: Git operations
- `github`: GitHub API
- `gitlab`: GitLab API
- `google-drive`: Drive access
- `postgres`: Database access
- `redis`: Redis access
- `slack`: Slack integration
- `memory`: Knowledge graph
- `brave-search`: Web search

### 4.2 Anthropic's MCP server design guide (key quotes)

> "The tool description is more important than the tool implementation. The LLM decides whether to call your tool based on the description."

> "Write the description as if you're explaining to a smart colleague when they should use this function."

> "Two to four sentences per tool strikes the right balance"

**Anti-pattern:** Version suffixes in tool names (e.g., `FetchResources_v2`) — "the agent cannot reliably determine which version to invoke"

### 4.3 Pattern MCPForge adopts
- All tool descriptions optimized for LLM usability (this is the whole product)
- 2-4 sentence descriptions
- No version suffixes
- Detailed parameter descriptions

## 5. Composio

- **URL:** https://composio.dev
- **Docs:** https://docs.composio.dev
- **Scale:** 1,000+ pre-built connectors

### 5.1 Architecture
- 7 meta-tools architecture
- Search, execute, connection management, sandbox workers
- Action-level RBAC
- SOC 2 Type II + ISO 27001

### 5.2 Pattern
```typescript
// Agent calls meta-tool:
await composio.execute({
  action: 'GITHUB_CREATE_ISSUE',
  params: { repo: '...', title: '...', body: '...' }
});
```

### 5.3 Trade-off
- Single API surface (cleaner)
- More indirection (agent must call execute with action name)

### 5.4 What MCPForge learns
- Action-level RBAC is enterprise-friendly (Phase 1.2+)
- 1,000+ connectors is a different business (Phase 2+)
- Meta-tool approach is a "compact mode" alternative

## 6. Cloudflare Durable Objects Pattern

For stateful MCP servers:

```typescript
import { McpAgent } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp";

export class MyMCP extends McpAgent<Env> {
  server = new McpServer({ name: "...", version: "1.0.0" });
  
  async init() {
    this.server.tool("add", { a: z.number(), b: z.number() }, async ({ a, b }) => ({
      content: [{ type: "text", text: String(a + b) }],
    }));
  }
}
```

**15 lines of code** for a stateful MCP server on Workers.

**MCPForge decision:** Not using this in v1.0 (we're on Render, not Workers). But the pattern is the model for our gateway: clear tool registration, schema-driven, framework-agnostic.

## 7. Smithery Patterns

- **URL:** https://smithery.ai
- **Tech:** Cloudflare Workers, TypeScript SDK generated by Stainless
- **Auth:** OAuth 2.1 + PKCE, API Keys, Service Tokens
- **Transport:** Streamable HTTP

### 7.1 Key patterns
- Namespace-based routing: one endpoint per namespace, tool names prefixed with connection ID
- Bring your own hosting — Smithery proxies to upstream servers
- OAuth managed on behalf of developers
- Per-server typed SDKs (generated from OpenAPI)

### 7.2 Pattern MCPForge considers
- Namespace routing for multi-tenant isolation
- Managed OAuth in v1.2

## 8. Vercel MCP

- **URL:** `https://mcp.vercel.com`
- **SDK:** `mcp-handler` npm package
- **Transport:** Streamable HTTP (recommended), SSE (backwards compat)
- **Compute:** Vercel Functions with Fluid compute

### 8.1 Pattern
```typescript
import { createMcpHandler } from "mcp-handler";
import { z } from "zod";

const handler = createMcpHandler((server) => {
  server.tool(
    "list_teams",
    "List all teams in the workspace",
    {},
    async () => { /* ... */ }
  );
});

export { handler as GET, handler as POST };
```

### 8.2 Fluid compute
- Optimized for MCP's irregular usage patterns
- "One customer saved 90% using Fluid vs traditional serverless"
- Long idle times, quick bursts (matches MCP usage)

### 8.3 Pattern MCPForge considers
- Fluid compute is a good target for Phase 1.1 (if we move off Render)

## 9. Common Patterns Across All Production Servers

| Pattern | Stripe | Cloudflare | Sentry | Anthropic | Vercel | Smithery |
|---|---|---|---|---|---|---|
| **Transport** | stdio + remote | StreamableHTTP | stdio + remote | stdio | StreamableHTTP | StreamableHTTP |
| **Auth** | API key | OAuth 2.1 | OAuth 2.1 | n/a | OAuth 2.1 | OAuth 2.1 |
| **Language** | TypeScript | TypeScript | TypeScript | TS+Py | TypeScript | TypeScript |
| **Naming** | `verb_noun` | Mixed | Mixed | Mixed | Mixed | Prefixed |
| **Descriptions** | Minimal | Generated | Explicit | Explicit | Explicit | Auto |
| **Runtime** | Node | Workers | Workers | Local | Vercel | Workers |
| **Hosting** | Stripe | Cloudflare | Cloudflare | User's machine | Vercel | Smithery |

**Shared lessons:**
1. All production servers use TypeScript SDK (Python SDK is less common)
2. OAuth 2.1 with PKCE is the auth standard
3. StreamableHTTP is the future; SSE is legacy
4. Cloudflare Workers is the most popular runtime
5. Tool descriptions matter enormously (this is our moat)

## 10. Patterns MCPForge Will Adopt

1. **Remote-first** (like Sentry) — hosted URL beats local install
2. **OAuth 2.1** in v1.2 for upstream APIs (F7) — matches the standard
3. **`verb_noun` naming** (like Stripe) — AI Engine's preference
4. **Use THIS WHEN pattern** (per Anthropic's guide) — engine of our quality
5. **2-4 sentence descriptions** (per Anthropic) — not bloated
6. **Restricted API keys for auth** (like Stripe) — for v1.0
7. **Production-grade observability** (like Sentry) — Sentry, structlog, request_id

## 11. Patterns MCPForge Will NOT Adopt

1. **Code Mode** (Cloudflare) — different audience; v1.2 consideration for compact mode
2. **Meta-tool approach** (Composio) — indirection; v1.0 is direct tool calls
3. **1,000+ pre-built connectors** (Composio) — different business
4. **Local stdio** (Stripe default) — we're hosted-only

## 12. References

- **Stripe MCP:** https://docs.stripe.com/mcp
- **Cloudflare MCP:** https://developers.cloudflare.com/agents/model-context-protocol/
- **Sentry MCP:** https://mcp.sentry.dev
- **Anthropic servers:** https://github.com/modelcontextprotocol/servers
- **Composio:** https://composio.dev
- **Smithery:** https://smithery.ai
- **Vercel MCP:** https://vercel.com/docs/mcp
- **CallSphere analysis of Stripe MCP:** https://callsphere.io/blog/stripe-mcp-analysis
- **Sentry MCP blog:** https://blog.sentry.io/yes-sentry-has-an-mcp-server-and-its-pretty-good/
- **Cloudflare Code Mode blog:** https://blog.cloudflare.com/code-mode-mcp/
