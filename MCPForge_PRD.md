# MCPForge — Product Requirements Document

**Version:** 1.0  
**Status:** Production-Ready Specification  
**Author:** Partha Saradhi Munakala  
**Last Updated:** June 2026  
**Classification:** Internal — Engineering + Product

---

## Table of Contents

1. Executive Summary
2. Problem Statement
3. Market Analysis
4. Competitive Analysis
5. Target Users & Personas
6. Product Vision & Positioning
7. Feature Specifications — v1.0
8. Detailed User Flows
9. Technical Architecture
10. Database Schema
11. REST API Design
12. Tech Stack & Rationale
13. Security Architecture
14. Infrastructure & Deployment
15. Success Metrics & KPIs
16. Launch Strategy
17. Monetization & Pricing
18. Product Roadmap

---

---

## 1. Executive Summary

MCPForge is a full-lifecycle web platform for building, testing, and deploying production-ready Model Context Protocol (MCP) servers. It targets API developers and AI engineers who want their APIs accessible to AI tools — Claude Desktop, Cursor, Windsurf, GitHub Copilot — without installing CLI tools, writing protocol code, or managing local environments.

**The core insight driving this product:** Existing OpenAPI-to-MCP tools (of which there are 10+) produce technically functional servers with *terrible* tool descriptions. A peer-reviewed study of 10,831 MCP servers found that 73% have description quality problems, and well-described tools are selected by LLMs 260% more often than poorly described ones. MCPForge is the only platform that uses AI to optimize tool descriptions for LLM usability — not just protocol compliance.

**What MCPForge does that nothing else does:**
- Converts any OpenAPI spec (URL or upload) into an MCP server in under 60 seconds
- Runs an AI Description Engine that rewrites every tool description to maximize LLM selection probability
- Provides a browser-native MCP Playground — no CLI, no local setup
- Deploys a live hosted MCP endpoint (addable to Claude Desktop / Cursor in one copy-paste)
- Monitors server usage with per-tool analytics

**Target v1.0 metrics:** 2,000 registered users, 500 active deployed servers, 50,000 total tool calls served within 60 days of launch.

---

---

## 2. Problem Statement

### 2.1 The Three Failure Modes in the MCP Ecosystem

**Problem 1 — Generated servers are technically functional but LLM-unusable**

Every existing CLI tool that converts OpenAPI to MCP does a mechanical transformation: `operationId` becomes the tool name, the OpenAPI `description` field becomes the tool description. This produces servers that *technically comply* with the MCP spec but don't work well in practice.

A February 2026 peer-reviewed study (arxiv 2602.18914) analyzed 10,831 MCP servers across the ecosystem and found:
- **73% suffer from repeated tool names** — confusing LLMs about which tool to call
- **3,449 servers exhibit wrong parameter meanings** — descriptions that don't match actual behavior
- **3,093 lack return value descriptions** — LLMs can't reason about what they'll get back

The direct business impact: well-described servers are selected **260% more often** in competitive scenarios. A developer deploying a mechanically generated server is leaving 72% of potential usage on the table.

**Problem 2 — Testing MCP servers requires painful local setup**

The official testing path: install Claude Desktop, configure `claude_desktop_config.json`, restart the app, open it, and hope your server connected. The official MCP Inspector has had serious security vulnerabilities (CVE-2025-49596, CVSS 9.4). Third-party browser playgrounds exist but are either limited to HTTP servers or have no real API execution.

There is no hosted, browser-native MCP playground that works with any authentication scheme and lets you test real API calls without any local setup.

**Problem 3 — Deployment is a fragmented multi-step process**

After generating code, a developer must: deploy it somewhere, configure environment variables, set up a public URL, handle CORS, manage auth secrets, then submit to 5-10 different MCP registries manually (one developer built a separate CLI tool just to submit to 10+ directories). There is no platform that goes from spec → deployed + publicly accessible endpoint in under 60 seconds.

### 2.2 The Status Quo Workarounds and Why They Fail

| Workaround | What it does | Why it fails |
|---|---|---|
| Use an OpenAPI CLI tool | Generates code locally | Requires Node/Python, no AI enhancement, no hosting |
| Use MCP.Link | Hosted URL from spec | No customization, no auth config, no analytics, basic quality |
| Use Speakeasy/Gram | Enterprise hosted | $$$, SDK-focused, not for indie devs |
| Use Claude Desktop manually | Test locally | Requires restart, no browser experience, security risks |
| Self-host on Cloudflare Workers | Production deployment | Requires Cloudflare knowledge, no AI enhancement |

---

---

## 3. Market Analysis

### 3.1 MCP Ecosystem Growth (Verified Data)

The MCP protocol launched in November 2024. Growth since:

| Metric | Nov 2024 | May 2025 | Dec 2025 | Today (Jun 2026) |
|---|---|---|---|---|
| Total MCP servers | ~100 | 4,000+ | 11,415 | 31,818+ |
| Monthly downloads | <100K | ~500K | ~2M | ~8M (est.) |
| GitHub commits | — | — | 85K tracked in 2025 | Growing |
| Reddit community monthly visitors | — | — | 7.3M in 2025 | — |

MCP has been adopted by every major AI platform: Claude (Anthropic), ChatGPT (OpenAI, March 2025), GitHub Copilot, Cursor, Windsurf, VS Code extensions, and is natively supported by Cloudflare, Vercel, and Netlify.

Gartner projects that by 2026, **75% of API gateway vendors** and **50% of iPaaS vendors** will have MCP features. This means the population of "companies with an API that should be MCP-accessible" is essentially every company with a developer API.

### 3.2 Total Addressable Market

**Primary TAM:** The ~31M developer accounts on GitHub who work with APIs and want AI tools to use their APIs. Conservative conversion to paying users: 0.5% = 155,000 potential subscribers.

**Secondary TAM:** Enterprise teams building internal MCP tooling. Sentry's MCP monitoring server hit 30M requests/month within weeks of launch — indicating the scale of enterprise MCP usage.

**Why now:** The MCP ecosystem is in the "early majority" phase of its S-curve. The early adopters (developers who built the first 4,000 servers in 6 months) are done. The mainstream wave — companies with existing APIs who want to be AI-accessible — is arriving now. This is the optimal window to establish a platform position.

### 3.3 Business Model Validation

- CodeRabbit ($12/seat/month) raised $16M for AI code review
- LangSmith ($39/seat/month) raised large rounds for AI observability
- Smithery (MCP registry) offers 85% revenue share to server creators — implying meaningful monetizable traffic
- Composio (MCP integrations) has 250+ integrations and strong paid adoption

The market clearly pays for AI developer tooling that saves engineering time.

---

---

## 4. Competitive Analysis

### 4.1 Direct Competitors

**MCP.Link** (mcp-link.vercel.app)
- What it does: Paste an OpenAPI spec URL → get an MCP-compatible hosted endpoint instantly
- Strengths: Zero setup, completely hosted, open-source
- Weaknesses: No customization, no AI description enhancement, no authentication configuration, no analytics, no playground, no tool selection (exposes ALL endpoints), no security scanning, basic quality
- **Our advantage:** AI enhancement, tool selection, playground, analytics, auth config

**Speakeasy + Gram** (speakeasy.com)
- What it does: Enterprise SDK generation that includes MCP server generation; Gram is hosted MCP from OpenAPI
- Strengths: Excellent code quality, TypeScript type safety, enterprise support
- Weaknesses: Priced for enterprise SDK teams, requires Speakeasy ecosystem adoption, complex onboarding, not developer-friendly for indie builders
- **Our advantage:** Simpler, cheaper, AI enhancement, better playground

**Smithery** (smithery.ai)
- What it does: MCP server registry + hosting marketplace
- Strengths: Largest catalog (7,000+ servers), hosting infrastructure, OAuth management, 85% revenue share
- Weaknesses: Not a builder — you bring your already-built server; no AI enhancement; no OpenAPI conversion
- **Our advantage:** We build the server FOR you

**Tyk API-to-AI**
- What it does: Converts Tyk-managed APIs to MCP servers with governance + rate limiting
- Strengths: Enterprise governance, existing Tyk ecosystem
- Weaknesses: Requires Tyk API Gateway, enterprise pricing, complex
- **Our advantage:** Works with any API, no gateway required

**CLI Tools** (openapi-mcp-generator, mcpgen, ai-create, FastMCP, openapi-mcp)
- What they do: Command-line generation of MCP server code
- Strengths: Free, flexible, open-source, many language options
- Weaknesses: No UI, no hosting, no AI enhancement, no playground, requires local environment
- **Our advantage:** Everything a CLI can't do

### 4.2 Competitive Positioning Matrix

| Feature | MCPForge | MCP.Link | Speakeasy/Gram | CLI Tools | Smithery |
|---|---|---|---|---|---|
| Web UI (no CLI) | ✅ | ✅ | ✅ | ❌ | ✅ |
| OpenAPI → MCP | ✅ | ✅ | ✅ | ✅ | ❌ |
| AI description enhancement | ✅ | ❌ | ❌ | ❌ | ❌ |
| Tool selector (choose endpoints) | ✅ | ❌ | Partial | Partial | ❌ |
| Browser MCP playground | ✅ | ❌ | ❌ | ❌ | ❌ |
| One-click hosted deployment | ✅ | ✅ | ✅ | ❌ | ✅ |
| Authentication configuration | ✅ | Partial | ✅ | ✅ | ✅ |
| Security scanner | ✅ | ❌ | ❌ | ❌ | Partial |
| Usage analytics | ✅ | ❌ | ❌ | ❌ | Basic |
| Registry submission | ✅ | ❌ | ❌ | ❌ | Native |
| Free tier | ✅ | ✅ | Limited | ✅ | ✅ |
| Target user | Devs & teams | Devs | Enterprise SDK | Devs | All |

### 4.3 Our Defensible Moat

The AI Description Engine is our primary moat. It requires:
1. A curated quality framework based on the arxiv research (functionality, accuracy, completeness, context dimensions)
2. Prompt engineering that understands MCP tool calling semantics
3. Training data from the ecosystem to fine-tune what "good" looks like

This takes time to build and improves with usage data. As we accumulate before/after quality comparisons and tool selection data, our AI gets better — creating a flywheel that competitors can't easily replicate.

---

---

## 5. Target Users & Personas

### Persona 1 — Alex, API Developer at a SaaS Startup
**Role:** Backend engineer at a 15-person startup with a well-documented REST API  
**Goal:** "I want AI tools like Claude and Cursor to be able to use our API directly, so our users and our team can query our data in plain English"  
**Pain:** "I tried the CLI tools, generated the server in 5 minutes, added it to Claude Desktop, and when I ask it to 'get recent orders', it picks the wrong tool 40% of the time"  
**Willingness to pay:** $9-29/month if it just works  
**Key requirement:** Description quality — wants tools that LLMs actually select correctly

### Persona 2 — Priya, Indie Developer / AI Builder
**Role:** Building an AI-powered productivity tool that needs to call external APIs  
**Goal:** "I need 3-4 external APIs (Notion, Linear, Stripe) accessible to my AI agent, I want to use existing MCP servers where possible and create custom ones where they don't exist"  
**Pain:** "Testing MCP servers is a nightmare. I have to restart Claude Desktop every time I change a tool description. I need a way to iterate quickly."  
**Willingness to pay:** Free if possible, $9/month if playground saves her hours  
**Key requirement:** Browser playground for fast iteration

### Persona 3 — David, Tech Lead at a Mid-Market Company
**Role:** Engineering lead at a 200-person company building internal AI tooling  
**Goal:** "We want our internal APIs (HR system, ERP, project tracking) accessible to our company's AI assistant, but we can't put our credentials on Smithery's public infrastructure"  
**Pain:** "Security and privacy. Every hosted tool requires trusting a third party with our API keys"  
**Willingness to pay:** $29-99/month for a team plan with access control  
**Key requirement:** Credential encryption, access control, audit logs

---

---

## 6. Product Vision & Positioning

**Vision:** Every API in the world is one click away from being AI-accessible.

**Mission:** Make building and deploying production-quality MCP servers so simple that a developer with an OpenAPI spec can go from zero to a fully monitored, AI-optimized, deployed MCP server in under 3 minutes.

**Positioning Statement:** For API developers and AI engineers who want their APIs accessible to AI tools, MCPForge is the only MCP server platform that uses AI to optimize tool descriptions for maximum LLM usability — not just technical protocol compliance. Unlike CLI generators that produce mechanically correct but LLM-unfriendly servers, or enterprise platforms priced for SDK teams, MCPForge gives indie developers and small teams a professional-grade deployment platform with a browser playground, usage analytics, and AI-enhanced descriptions that make their MCP servers actually get used.

---

---

## 7. Feature Specifications — v1.0

### Feature 1 — Server Builder: OpenAPI Ingestion

**Description:** The entry point for all server creation. Accepts an OpenAPI spec via URL or file upload, parses it, and presents the user with a structured tool workspace.

**Acceptance Criteria:**

1. User can enter a public URL pointing to an OpenAPI 3.0+ JSON or YAML spec. System fetches and validates it within 5 seconds.
2. User can upload a `.json` or `.yaml` file up to 5MB. System parses it client-side and sends to backend.
3. System validates the spec against the OpenAPI 3.0 schema. Invalid specs show inline error messages identifying the specific problem (not a generic "invalid spec" message).
4. On successful parse, the system displays a **Tool Workspace** — a list of all detected API endpoints organized by tag group.
5. Each endpoint shows: HTTP method (color-coded), path, operation ID, original description (truncated to 100 chars), parameter count, and a toggle checkbox.
6. User can select/deselect individual endpoints. Deselected endpoints are excluded from the generated MCP server. Default: all GET endpoints selected, all DELETE endpoints deselected.
7. System displays a summary badge: "N tools selected • M excluded".
8. If the spec has no `operationId` on some endpoints, system auto-generates one from `{method}_{path_segments}` and shows a yellow warning badge with an explanation.
9. User names the server (pre-filled from spec `info.title`), adds a description, and selects an auth scheme (None / API Key / Bearer Token / Basic Auth / OAuth2).
10. For API Key and Bearer Token auth: user provides a name for the env var and a test value (stored encrypted, never shown in plaintext again). A "test connection" button fires a dry-run request to confirm credentials work before saving.
11. "Build Server" button initiates the processing pipeline (async). User sees a real-time progress stream via SSE: `Parsing spec → Selecting tools → Running AI Enhancement → Validating security → Server ready`.

**Edge Cases Handled:**
- Spec behind Basic Auth: user provides credentials for spec fetch, stored only in session
- Malformed YAML with tabs: parser detects and surfaces specific line number
- Spec with 200+ endpoints: system warns "Large spec detected — selecting all endpoints may produce an unfocused server. Consider selecting 10-30 key tools."
- Circular `$ref` definitions: dereferenced safely, not rejected

---

### Feature 2 — AI Description Engine

**Description:** The core product differentiator. After tool selection, the AI Description Engine analyzes every selected tool and rewrites its name, description, parameter descriptions, and return value description to maximize LLM usability. This is based on the four quality dimensions identified in the arxiv 2602.18914 research.

**Quality Dimensions (from research):**
- **Functionality** — Does the description accurately convey what the tool does? (+11.6% selection impact)
- **Accuracy** — Are parameter names and types correctly described? (+8.8% selection impact)  
- **Completeness** — Are all parameters described, including optionals? (critical for complex queries)
- **Context** — Does the description help an LLM decide *when* to use this tool vs alternatives?

**Acceptance Criteria:**

1. For each selected tool, the engine makes one Claude API call with a structured prompt that includes:
   - The original OpenAPI spec for that endpoint
   - The full request/response schema
   - Example request/response if available in the spec
   - The quality framework with specific scoring rubrics
   - Any sibling tools (for disambiguation)

2. The engine produces a structured output for each tool:
   ```json
   {
     "tool_name": "search_products",
     "tool_description": "Search the product catalog by keyword, category, price range, or availability. Use this when users want to find products that match specific criteria. Returns paginated results with product details.",
     "parameters": [
       {
         "name": "query",
         "description": "Natural language search term or product name. Supports partial matches. Example: 'wireless headphones under $50'",
         "required": true,
         "type": "string"
       }
     ],
     "return_description": "Returns an array of matching products, each with id, name, price, category, and in_stock status. Returns empty array if no matches found.",
     "quality_score": 94,
     "improvements_made": ["Added disambiguation context", "Rewrote 3 parameter descriptions", "Added return value description"]
   }
   ```

3. The UI presents the AI-enhanced version side-by-side with the original in a **Description Review Panel**:
   - Left column: Original (from OpenAPI spec)
   - Right column: AI Enhanced (editable)
   - Quality score badge (0-100) with breakdown by dimension
   - "Changes made" summary in orange badges
   - User can click any field to edit the AI's output
   - User can click "Revert to original" on any individual field

4. A bulk "Accept All AI Suggestions" button applies all enhancements without review (for users who trust the AI).

5. Quality score thresholds:
   - 90-100: Green "Excellent" badge
   - 70-89: Yellow "Good" badge
   - 50-69: Orange "Fair" badge — warning shown: "This tool may not be selected reliably by LLMs"
   - <50: Red "Poor" badge — blocking warning: "We recommend improving this description before deploying"

6. Processing time: < 3 seconds per tool (parallel API calls). A server with 15 tools should complete AI enhancement in under 10 seconds total.

7. Cost tracking: System calculates estimated token cost for the AI enhancement pass and displays it to the user (transparency). At current Claude Sonnet pricing, a 15-tool server costs approximately $0.02-0.05 to enhance.

8. Users on the free tier get 3 AI enhancements per month. Pro users get unlimited.

---

### Feature 3 — Browser MCP Playground

**Description:** A hosted, browser-native MCP client that lets users test their MCP server by calling its tools directly in the browser — with real API execution, no local setup.

**This is the hardest feature to build and the biggest UX differentiator.**

**How it works technically:**
The playground communicates with a Playground Proxy service that:
1. Accepts WebSocket connections from the browser
2. Speaks the MCP protocol to the user's deployed server (or pre-deployment test server)
3. Returns structured results to the browser in real time

**Acceptance Criteria:**

1. Playground accessible from two contexts:
   - **Pre-deployment:** Test the server before deploying (uses a temporary in-memory server instance)
   - **Post-deployment:** Test the live hosted server at any time from the server dashboard

2. The playground UI consists of four panels:
   - **Tool Browser (left):** List of all tools with their AI-enhanced names and quality scores. Click to select.
   - **Input Form (center-top):** Auto-generated form for the selected tool's parameters. Text inputs, dropdowns, and toggles based on schema types. Required fields marked with *.
   - **Response (center-bottom):** JSON response with syntax highlighting. Shows raw JSON and formatted view toggle.
   - **Call Log (right):** Full request/response history with timestamps. Exportable as JSON.

3. When the user clicks "Call Tool":
   - System shows a loading spinner
   - Makes real HTTP call to the actual API (with the user's stored credentials)
   - Displays raw MCP protocol JSON (what the LLM would see) AND a human-readable formatted view
   - Shows: execution time (ms), status code, token count of response

4. Error handling in the playground:
   - Auth failures: "Authentication failed — check your API key in Server Settings"
   - Network errors: "Could not reach your API at {baseUrl} — verify it's publicly accessible"
   - Schema validation errors: Highlight which parameter failed validation with the reason

5. Playground sessions are ephemeral — nothing is stored. No API calls appear in usage analytics.

6. "Share Test" button generates a shareable URL that pre-loads a specific tool with specific parameters (useful for debugging with teammates). Parameters that contain credentials are stripped before sharing.

---

### Feature 4 — Hosted MCP Gateway

**Description:** Every deployed server gets a unique, permanent URL that functions as an MCP endpoint. Users add this URL to their Claude Desktop config, Cursor settings, or any MCP client. MCPForge's gateway handles the MCP protocol, translates tool calls to HTTP requests, and returns MCP-formatted responses.

**Gateway URL format:** `https://mcpforge.io/mcp/v1/{server_slug}`

**Why a Gateway (not code download):**
- Users add ONE URL to their AI tool — it works everywhere
- We can push description updates without users reconfiguring
- We can monitor usage (analytics)
- Users don't need to know how to deploy a server

**Acceptance Criteria:**

1. After deployment, user sees a "Connect" panel with:
   - The gateway URL (with one-click copy)
   - Pre-filled `claude_desktop_config.json` snippet
   - Pre-filled Cursor `~/.cursor/mcp.json` snippet
   - A "Test Connection" button that sends a `tools/list` request and shows the response

2. The gateway supports two transport modes:
   - **SSE (Server-Sent Events):** `GET /mcp/v1/{slug}/sse` — for Claude Desktop and most MCP clients
   - **StreamableHTTP:** `POST /mcp/v1/{slug}/` — for newer clients and agent frameworks

3. Gateway request pipeline for each incoming MCP tool call:
   ```
   Incoming MCP request
   → Authenticate (verify gateway token / rate limit)
   → Parse JSON-RPC tool call
   → Look up tool → endpoint mapping from server config
   → Retrieve encrypted API credentials
   → Build HTTP request with proper auth headers
   → Execute HTTP request to target API
   → Parse response
   → Apply response schema validation
   → Format as MCP-compliant JSON-RPC response
   → Return to client
   ```

4. Response handling:
   - For responses over 100KB: automatically truncate and add a `_truncated: true` field with a note
   - For binary responses (images, files): return base64-encoded with MIME type annotation
   - For HTML responses (error pages): strip HTML, return plain text error message

5. Error responses follow MCP spec error codes:
   - `ToolNotFound` — tool name doesn't match any configured tool
   - `InvalidParams` — required parameter missing or wrong type
   - `UpstreamError` — the target API returned an error (includes status code and body)
   - `RateLimitExceeded` — user exceeded their plan's call limit

6. Gateway performance requirements:
   - P50 latency: < 100ms overhead (above the target API's own latency)
   - P95 latency: < 250ms overhead
   - Uptime: 99.9% SLA (for Pro tier)

7. Each server has an **Enable/Disable** toggle. Disabling stops all incoming calls immediately (within 5 seconds). Useful for incident response.

8. Server slug rules: lowercase alphanumeric + hyphens, 3-50 characters, unique per user. Changing the slug invalidates the old URL permanently.

---

### Feature 5 — Security Scanner

**Description:** Before deployment and on-demand post-deployment, the Security Scanner analyzes the server configuration for common MCP-specific vulnerabilities.

**Background:** A scan of 8,000+ public MCP servers found 36.7% have SSRF vulnerabilities, 43% have unsafe command execution paths, and 41% have zero authentication. This is the single biggest problem in the MCP ecosystem.

**Acceptance Criteria:**

1. Scanner runs automatically before every deployment. User sees results before confirming.

2. Scanner checks for:
   
   **SSRF (Server-Side Request Forgery):**
   - Does any tool accept a URL parameter that gets fetched server-side?
   - Does any endpoint's base URL contain dynamic path segments that could be manipulated?
   - Detection method: Analyze tool parameter names and descriptions for URL-like patterns
   
   **Authentication gaps:**
   - Is the server deployed with no authentication scheme?
   - Does any tool expose sensitive operations (DELETE, POST with PII fields) without auth?
   
   **Tool description injection:**
   - Do any tool descriptions contain executable-looking content, markdown links, or unusual characters that could affect LLM behavior?
   - Check for known prompt injection patterns in description text
   
   **Response data leakage:**
   - Do any tools return full authentication tokens, passwords, or private keys based on response schema?
   - Check field names in response schemas for `password`, `token`, `secret`, `key`, `private`
   
   **Overly broad tool exposure:**
   - Warn if a tool exposes a CRUD delete operation without a human-confirmation mechanism

3. Scanner results are color-coded:
   - 🔴 **CRITICAL** — Block deployment, must fix (SSRF detected, credential exposure)
   - 🟠 **HIGH** — Strongly recommended to fix, can override with acknowledgment
   - 🟡 **MEDIUM** — Warning shown, can proceed
   - 🔵 **INFO** — Best practice suggestions

4. Each finding includes: finding name, description, which tool triggered it, recommended fix, documentation link.

5. Users can add a `# mcpforge:ignore FINDING_ID` annotation in tool descriptions to acknowledge and suppress specific findings.

6. The scanner produces a **Security Report** downloadable as JSON — useful for teams that need to document their security posture.

---

### Feature 6 — Usage Analytics Dashboard

**Description:** Per-server analytics showing how AI clients are actually using the MCP server. This is critical for iterating on tool descriptions and understanding real-world usage.

**Acceptance Criteria:**

1. Analytics dashboard accessible per-server, showing:
   
   **Overview Panel (last 30 days default, adjustable to 7/30/90 days):**
   - Total tool calls
   - Unique sessions (unique client connections)
   - Error rate (%)
   - Average response time (ms)
   - Estimated token cost saved vs. no MCP (informational)
   
   **Tool Breakdown Table:**
   - Each tool: call count, success rate, avg latency, last called timestamp
   - Sorted by call count descending
   - Color-coded success rate: green (>95%), yellow (80-95%), red (<80%)
   
   **Error Log:**
   - Last 100 errors with: timestamp, tool called, error type, error message (sanitized, no credentials)
   - Filterable by tool and error type
   
   **Client breakdown:**
   - Which MCP clients are connecting: "Claude Desktop", "Cursor", "Unknown"
   - Detected from the `clientInfo` field in MCP initialization handshake
   
   **Time series chart:**
   - 24-hour and 7-day views of call volume
   - Overlay option to show error spikes

2. Analytics data stored for:
   - Free tier: 7 days
   - Pro tier: 90 days

3. All logged data is sanitized — parameter *values* are never stored (only parameter *names* appear in logs). This is non-negotiable for security/privacy.

4. Export: CSV export of tool call data for any time range.

5. "Description Performance" panel (unique feature):
   - If a user has edited AI-enhanced descriptions, system tracks whether the tool's call frequency changed after the edit
   - Shows: "After description update on [date], this tool's call rate increased 34%"

---

### Feature 7 — Authentication, Teams & Server Management

**Description:** Multi-user account management, team collaboration, and server configuration management.

**Acceptance Criteria:**

**Authentication:**
1. Sign up with email + password OR GitHub OAuth (most relevant for the developer audience)
2. Email verification required before accessing paid features
3. Password: minimum 12 characters, checked against HaveIBeenPwned API on creation
4. JWT access tokens (15-minute TTL) + refresh tokens (7-day TTL, rotated on use)
5. All auth tokens stored in httpOnly cookies — not localStorage

**API Keys (programmatic access):**
1. Users can generate named API keys for programmatic management (creating servers via API, fetching analytics)
2. API keys displayed once at creation, stored as SHA-256 hash
3. Keys can be scoped: `servers:read`, `servers:write`, `analytics:read`
4. Max 5 API keys per account

**Team Collaboration (Pro tier only):**
1. User can invite team members by email to their workspace
2. Roles: **Admin** (full access), **Editor** (can edit servers, cannot delete or change billing), **Viewer** (read-only + playground access)
3. Team invitations expire after 48 hours
4. Audit log: every server create/edit/delete, every deployment, every team member change — stored for 90 days

**Server Management:**
1. Server list view: all servers with status (Active / Paused / Error), last call time, call count this month
2. Server can be duplicated (copy all settings and descriptions, prompts for new name and slug)
3. Version history for server configurations: last 10 versions stored, one-click rollback
4. Delete server: confirmation dialog with server name re-entry, 24-hour grace period before permanent deletion (recoverable)

---

---

## 8. Detailed User Flows

### Flow A — Primary: New user builds and deploys their first MCP server

```
1. Land on mcpforge.io
   → Homepage shows the core value prop + "Build your first MCP server free"
   → No account required to try the builder (session-based, prompts to save)

2. Click "Start Building" → Builder page
   → Two options: "I have an OpenAPI spec" | "I don't have one — show me an example"
   → Clicking "example" pre-loads the Stripe API spec for demo purposes

3. User pastes OpenAPI spec URL → "Fetch & Analyze"
   → 2-3 second loading animation with status messages
   → Tool Workspace appears with all endpoints

4. User reviews endpoint list
   → Deselects DELETE endpoints and some obscure endpoints they don't need
   → Sees "12 tools selected"

5. Configures auth
   → Selects "Bearer Token"
   → Enters env var name: "API_KEY"
   → Enters test value (their actual API key)
   → Clicks "Test Connection" → "✅ Connected to api.example.com"

6. Names the server: "My Stripe Server"
   → Clicks "Build Server"

7. Sees real-time progress:
   "🔄 Parsing 12 tools..."
   "🤖 Running AI Description Engine (3/12)..."
   "🔒 Running Security Scanner..."
   "✅ Server ready for review"

8. Description Review Panel appears
   → User sees side-by-side original vs AI-enhanced descriptions
   → Quality score: overall 87/100
   → 2 tools marked "Fair" — user clicks into them and edits manually
   → Clicks "Accept All & Continue"

9. Security Scanner results
   → 1 MEDIUM warning: "Tool 'list_customers' returns email addresses. Ensure your use case complies with GDPR."
   → User clicks "Acknowledge & Continue"

10. Deployment confirmation
    → Shows: gateway URL, transport modes, monthly call limit (Free: 500 calls/month)
    → "Deploy Now" button

11. Server deployed
    → Dashboard shows gateway URL: https://mcpforge.io/mcp/v1/my-stripe-server
    → Copy-paste Claude Desktop config shown
    → User copies the config, opens Claude Desktop, pastes it, restarts
    → User tests: "What are my recent Stripe charges?" → works ✅

12. User bookmarks their MCPForge dashboard for analytics
```

**Total time from landing to working Claude Desktop integration: under 4 minutes.**

### Flow B — Developer tests and iterates on descriptions

```
1. Developer notices: "Claude keeps calling 'get_customer' when it should call 'search_customers'"
2. Opens MCPForge dashboard → Playground
3. Selects 'get_customer' tool → sees current description
4. Opens Description Editor → manually rewrites disambiguation clause
5. Clicks "Test in Playground":
   → Sends a realistic query: "find customers named John Smith"
   → Sees response comes back empty (wrong tool called)
6. Opens 'search_customers' tool → notes its description overlaps significantly
7. Edits both descriptions to add "USE THIS WHEN..." and "DO NOT USE FOR..." clauses
8. Runs playground test again → correct tool selected
9. Clicks "Push Description Update" → live change in < 5 seconds, no redeployment needed
```

### Flow C — Team lead shares server with team

```
1. David (Tech Lead) creates an MCP server for the company's internal HR API
2. Invites three team members as "Viewer" role
3. Each team member gets an email → clicks → joins workspace
4. Team members see the server in their dashboard (read-only)
5. Each copies the gateway URL to their own Cursor config
6. David can see in Analytics that 3 different client sessions are active
7. One team member finds an issue → comments in the analytics error log (Viewer role)
8. David reviews, edits the description, pushes update
```

---

---

## 9. Technical Architecture

### 9.1 System Overview

```
                    ┌─────────────────────────────────────────────────────┐
                    │                   BROWSER (Next.js)                   │
                    │  Builder UI │ Playground │ Analytics │ Dashboard      │
                    └─────────────────────┬───────────────────────────────┘
                                          │ HTTPS
                    ┌─────────────────────▼───────────────────────────────┐
                    │              NGINX (Reverse Proxy + SSL)              │
                    └──────┬──────────────┬──────────────┬────────────────┘
                           │              │              │
              ┌────────────▼──┐  ┌────────▼──────┐  ┌──▼────────────────┐
              │  Main API      │  │  MCP Gateway  │  │  Playground Proxy  │
              │  (FastAPI)     │  │  (FastAPI)    │  │  (FastAPI + WS)    │
              │  :8000         │  │  :8001        │  │  :8002             │
              └────────────┬──┘  └────────┬──────┘  └──────────────────┘
                           │              │
              ┌────────────▼──────────────▼──────┐
              │         PostgreSQL 16              │
              │  (Users, Servers, Analytics,       │
              │   Team data, Audit logs)           │
              └───────────────────────────────────┘
                           │
              ┌────────────▼──────────────┐
              │         Redis 7            │
              │  (Celery queues, Session   │
              │   cache, Rate limiting,    │
              │   Gateway config cache)    │
              └───────────────────────────┘
                           │
              ┌────────────▼──────────────┐
              │      Celery Workers        │
              │  (AI Enhancement jobs,     │
              │   Security Scanner,        │
              │   Analytics aggregation)   │
              └───────────────────────────┘
                           │
              ┌────────────▼──────────────┐
              │         AWS S3             │
              │  (OpenAPI spec storage,    │
              │   Audit log archives)      │
              └───────────────────────────┘
```

### 9.2 Service Breakdown

**Main API Service (FastAPI, port 8000)**
Handles all user-facing CRUD operations: auth, server management, description editing, analytics queries, team management. Synchronous endpoints with async background task dispatch.

**MCP Gateway Service (FastAPI, port 8001)**
The most critical service. Handles all incoming MCP protocol requests from AI clients. This service:
- Is stateless (reads from Redis/PostgreSQL for config)
- Must be horizontally scalable
- Implements both SSE and StreamableHTTP transports
- Maintains a connection pool to the target APIs
- Caches server configurations in Redis (5-minute TTL, invalidated on server update)

**Playground Proxy Service (FastAPI + WebSockets, port 8002)**
Handles browser WebSocket connections for the playground. Ephemeral — no persistence. Translates WebSocket messages from the browser into MCP protocol calls to temporary or live server instances.

**Celery Workers (3 worker types)**
1. `ai_worker` — Handles AI description enhancement jobs (Claude API calls). Separate from main workers to prevent rate limit issues from affecting other operations.
2. `scanner_worker` — Runs security scans. CPU-bound, separate pool.
3. `analytics_worker` — Aggregates raw event streams into analytics tables every 5 minutes.

### 9.3 MCP Gateway — Core Logic

The gateway is the most architecturally important component. It must handle the MCP protocol faithfully while adding our business logic.

```
Incoming SSE Request:
GET /mcp/v1/{server_slug}/sse
Headers: Authorization: Bearer {user_token} (optional)

Step 1: Slug resolution
  → Look up server in Redis cache by slug
  → If not in cache: SELECT from PostgreSQL + cache with 5min TTL
  → If server is disabled or deleted: return 404

Step 2: Rate limiting
  → Check per-server monthly call count in Redis
  → If over plan limit: return MCP error (RateLimitExceeded)

Step 3: MCP Handshake
  → Respond to initialize request with server capabilities
  → Return tools/list from cached server config (AI-enhanced descriptions)

Step 4: Tool call handling
  → Receive tools/call request: {name: "search_products", arguments: {...}}
  → Validate arguments against tool schema
  → Retrieve encrypted credentials from PostgreSQL (decrypt AES-256)
  → Build HTTP request: method + URL + headers + body
  → Execute HTTP request (5-second timeout, retry once on 429)
  → Parse response
  → Log event to analytics stream (async, non-blocking)
  → Return formatted MCP response

Step 5: Connection cleanup
  → On disconnect: clean up SSE connection, flush pending analytics
```

### 9.4 AI Description Engine — Implementation

```python
async def enhance_tool_description(
    tool: OpenAPITool,
    sibling_tools: list[OpenAPITool],
    spec_context: dict
) -> EnhancedToolDescription:
    
    prompt = build_enhancement_prompt(
        tool=tool,
        siblings=sibling_tools,
        quality_framework=QUALITY_FRAMEWORK,  # From arxiv research
        examples=GOOD_DESCRIPTION_EXAMPLES    # Curated examples
    )
    
    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=ENHANCEMENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse structured JSON response
    enhanced = parse_enhanced_description(response.content[0].text)
    
    # Score quality on 4 dimensions
    quality_score = score_description_quality(enhanced)
    
    return EnhancedToolDescription(
        tool_name=enhanced.tool_name,
        tool_description=enhanced.tool_description,
        parameters=enhanced.parameters,
        return_description=enhanced.return_description,
        quality_score=quality_score,
        improvements_made=diff_improvements(tool, enhanced)
    )
```

The quality scoring function evaluates:
- **Functionality score (0-30):** Does the description say what the tool does and returns? Checked with a lightweight regex+heuristic model
- **Accuracy score (0-25):** Do parameter descriptions match their types and constraints?
- **Completeness score (0-25):** Are all parameters described, including optionals?
- **Context score (0-20):** Does the description include "when to use" and "when NOT to use" guidance?

---

---

## 10. Database Schema

### `users`
```sql
CREATE TABLE users (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email        VARCHAR(255) UNIQUE NOT NULL,
  github_id    VARCHAR(100) UNIQUE,
  password_hash VARCHAR(255),            -- Argon2id
  display_name VARCHAR(100),
  avatar_url   VARCHAR(500),
  plan         VARCHAR(20) DEFAULT 'free',  -- free | pro | team
  plan_expires_at TIMESTAMPTZ,
  ai_enhancement_credits INT DEFAULT 3,   -- Free tier limit
  email_verified BOOLEAN DEFAULT false,
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);
```

### `mcp_servers`
```sql
CREATE TABLE mcp_servers (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
  slug         VARCHAR(50) UNIQUE NOT NULL,
  name         VARCHAR(200) NOT NULL,
  description  TEXT,
  status       VARCHAR(20) DEFAULT 'building',  -- building | active | paused | error
  
  -- Source spec
  spec_url     VARCHAR(1000),
  spec_s3_key  VARCHAR(500),            -- If uploaded
  base_url     VARCHAR(500) NOT NULL,
  
  -- Auth config (no credential values here)
  auth_scheme  VARCHAR(20) DEFAULT 'none',  -- none | api_key | bearer | basic | oauth2
  auth_header_name VARCHAR(100),
  credential_id UUID REFERENCES credentials(id),
  
  -- Config
  tools_config JSONB NOT NULL,           -- Array of tool configs (AI-enhanced descriptions)
  transport_mode VARCHAR(20) DEFAULT 'sse',  -- sse | streamable_http | both
  
  -- Stats (cached)
  total_calls  BIGINT DEFAULT 0,
  monthly_calls INT DEFAULT 0,
  last_call_at TIMESTAMPTZ,
  
  -- Metadata
  version      INT DEFAULT 1,
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_servers_slug ON mcp_servers(slug);
CREATE INDEX idx_servers_user_id ON mcp_servers(user_id);
```

### `credentials`
```sql
CREATE TABLE credentials (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  server_id    UUID REFERENCES mcp_servers(id) ON DELETE CASCADE,
  user_id      UUID REFERENCES users(id),
  env_var_name VARCHAR(100) NOT NULL,
  encrypted_value BYTEA NOT NULL,       -- AES-256-GCM encrypted
  encryption_key_id VARCHAR(50),        -- Reference to key in AWS KMS
  created_at   TIMESTAMPTZ DEFAULT now(),
  rotated_at   TIMESTAMPTZ
);
```

### `server_versions`
```sql
CREATE TABLE server_versions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  server_id    UUID REFERENCES mcp_servers(id) ON DELETE CASCADE,
  version      INT NOT NULL,
  tools_config JSONB NOT NULL,          -- Full snapshot of tools config at this version
  changed_by   UUID REFERENCES users(id),
  change_note  TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

### `tool_calls` (partitioned by day for performance)
```sql
CREATE TABLE tool_calls (
  id           UUID DEFAULT gen_random_uuid(),
  server_id    UUID NOT NULL,
  tool_name    VARCHAR(200) NOT NULL,
  status       VARCHAR(20) NOT NULL,   -- success | error | timeout
  error_type   VARCHAR(100),
  error_msg    TEXT,
  latency_ms   INT,
  response_size_bytes INT,
  client_name  VARCHAR(100),           -- "Claude Desktop" | "Cursor" | etc.
  called_at    TIMESTAMPTZ DEFAULT now()
  -- NOTE: No parameter values ever stored
) PARTITION BY RANGE (called_at);
CREATE INDEX idx_tool_calls_server_id ON tool_calls(server_id, called_at);
```

### `teams`
```sql
CREATE TABLE teams (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       VARCHAR(200) NOT NULL,
  owner_id   UUID REFERENCES users(id),
  plan       VARCHAR(20) DEFAULT 'team',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE team_members (
  team_id    UUID REFERENCES teams(id) ON DELETE CASCADE,
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  role       VARCHAR(20) NOT NULL,  -- admin | editor | viewer
  joined_at  TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (team_id, user_id)
);
```

### `audit_logs`
```sql
CREATE TABLE audit_logs (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id),
  action     VARCHAR(100) NOT NULL,   -- server.create | server.delete | member.invite | etc.
  resource_type VARCHAR(50),
  resource_id UUID,
  metadata   JSONB,
  ip_address INET,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

---

## 11. REST API Design

### Auth Endpoints
```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/auth/refresh
GET  /api/v1/auth/github          → OAuth redirect
GET  /api/v1/auth/github/callback
POST /api/v1/auth/verify-email
```

### Server Endpoints
```
GET    /api/v1/servers                   → List user's servers (paginated)
POST   /api/v1/servers                   → Create server (triggers async pipeline)
GET    /api/v1/servers/{id}              → Get server details
PATCH  /api/v1/servers/{id}             → Update server config
DELETE /api/v1/servers/{id}             → Soft delete (24h grace period)
POST   /api/v1/servers/{id}/deploy       → Deploy (or redeploy)
POST   /api/v1/servers/{id}/pause        → Pause server
POST   /api/v1/servers/{id}/duplicate    → Duplicate server
GET    /api/v1/servers/{id}/versions     → Get version history
POST   /api/v1/servers/{id}/rollback     → Rollback to a version

# SSE stream for build progress
GET    /api/v1/servers/{id}/build-status → SSE stream during pipeline
```

### Tool Endpoints
```
GET    /api/v1/servers/{id}/tools           → List tools with descriptions
PATCH  /api/v1/servers/{id}/tools/{name}    → Update a tool's description
POST   /api/v1/servers/{id}/tools/enhance   → Re-run AI enhancement on all tools
POST   /api/v1/servers/{id}/tools/{name}/enhance → Re-run AI on single tool
```

### OpenAPI Spec Ingestion
```
POST   /api/v1/specs/fetch               → Fetch and validate a spec URL
POST   /api/v1/specs/upload              → Upload spec file
GET    /api/v1/specs/{id}/tools          → Parse and list tools from spec
```

### Analytics Endpoints
```
GET    /api/v1/servers/{id}/analytics                 → Overview metrics
GET    /api/v1/servers/{id}/analytics/tools           → Per-tool breakdown
GET    /api/v1/servers/{id}/analytics/errors          → Error log (paginated)
GET    /api/v1/servers/{id}/analytics/clients         → Client breakdown
GET    /api/v1/servers/{id}/analytics/export          → CSV export
```

### Team Endpoints
```
GET    /api/v1/team                       → Get team info
POST   /api/v1/team/invite                → Invite member (sends email)
PATCH  /api/v1/team/members/{user_id}    → Change member role
DELETE /api/v1/team/members/{user_id}    → Remove member
GET    /api/v1/team/audit-log             → Team audit log
```

### MCP Gateway Endpoints (separate service)
```
GET    /mcp/v1/{slug}/sse                 → SSE transport
POST   /mcp/v1/{slug}/                   → StreamableHTTP transport
GET    /mcp/v1/{slug}/health             → Health check (no auth required)
```

---

---

## 12. Tech Stack & Rationale

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | Next.js 15 (App Router) + TypeScript | You know it deeply, App Router with Server Components is ideal for mixed static/dynamic content |
| **UI Components** | shadcn/ui + Tailwind CSS v4 | Your existing skillset, production-quality components |
| **Code Editing** | Monaco Editor | For displaying tool descriptions and JSON, you've used it in DevPath |
| **State Management** | Zustand + TanStack Query | Minimal client state, server state via React Query |
| **Real-time** | Server-Sent Events (SSE) | For build progress and playground responses |
| **Main Backend** | FastAPI + Python 3.12 | Your strongest language, async, excellent OpenAPI integration |
| **MCP Gateway** | FastAPI (separate process) | Must be horizontally scalable independently of main API |
| **AI Enhancement** | Anthropic Claude claude-sonnet-4-20250514 | Best instruction-following for structured JSON output tasks |
| **ORM** | SQLAlchemy 2.0 (async) + Alembic | Your existing expertise, async support for FastAPI |
| **Database** | PostgreSQL 16 | JSONB for tool configs, partitioning for analytics |
| **Cache + Queue** | Redis 7 + Celery | Your existing expertise, ideal for async job management |
| **Object Storage** | AWS S3 | OpenAPI spec files, audit log archives |
| **Auth** | JWT (httpOnly cookies) + GitHub OAuth | Right tool for developer-facing SaaS |
| **Encryption** | AES-256-GCM (credentials) + AWS KMS | Industry standard for credential storage |
| **Containerization** | Docker + Docker Compose | You've deployed production systems with this |
| **CI/CD** | GitHub Actions | Your existing expertise |
| **Hosting** | AWS ECS (Fargate) | Auto-scaling, managed containers |
| **Reverse Proxy** | Nginx | Known quantity, handles SSL, rate limiting |
| **Error Tracking** | Sentry | Your existing skill, production monitoring |
| **Structured Logging** | Python logging + CloudWatch | Consistent with your work experience |

---

---

## 13. Security Architecture

### Credential Storage (Zero-Knowledge Design)
- User's API keys and bearer tokens are **never stored in plaintext**
- Encryption: AES-256-GCM with a per-server-unique initialization vector
- Encryption keys stored in **AWS KMS** (not in the database or codebase)
- Decryption happens only within the Gateway service at request time — never exposed to the Main API
- No credential values appear in logs, analytics, or error messages

### Transport Security
- All external traffic over TLS 1.3
- HSTS header enforced: `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- API responses include: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`

### Gateway Security
- Rate limiting: per-server and per-IP using Redis token bucket
- Input validation: All MCP protocol JSON validated against JSON Schema before processing
- SSRF prevention: Internal IPs blocklisted — gateway cannot call `10.x`, `172.16.x`, `192.168.x`, `169.254.x` (AWS metadata endpoint)
- Response size limit: 5MB max response from target APIs — prevents memory exhaustion

### Auth Security
- JWTs stored in httpOnly, SameSite=Strict cookies — XSS-resistant
- Refresh token rotation on every use
- Account lockout: 5 failed logins → 15-minute lockout
- Password check: HaveIBeenPwned API (k-anonymity model) on registration and password change

---

---

## 14. Infrastructure & Deployment

### Environment Structure
```
local        → Docker Compose (all services)
staging      → AWS ECS (single replicas, reduced resources)
production   → AWS ECS (auto-scaling, multi-AZ)
```

### AWS Production Architecture
```
Route 53 (DNS)
    → CloudFront (CDN for frontend static assets)
    → ALB (Application Load Balancer)
        → ECS Service: mcpforge-main-api (2-8 replicas, auto-scale on CPU)
        → ECS Service: mcpforge-gateway (3-20 replicas, auto-scale on connections)
        → ECS Service: mcpforge-playground (1-5 replicas)
    → ECS Service: mcpforge-celery-ai (1-3 replicas, queue depth trigger)
    → ECS Service: mcpforge-celery-analytics (1-2 replicas)

Aurora PostgreSQL (Multi-AZ, read replica for analytics queries)
ElastiCache Redis (Cluster mode, 3 shards)
S3 (specs storage, ALB access logs, backups)
KMS (credential encryption keys)
SES (transactional email)
CloudWatch (logs, metrics, alarms)
Sentry (error tracking)
```

### Docker Compose (Local Dev)
```yaml
services:
  postgres:    image: postgres:16-alpine
  redis:       image: redis:7-alpine
  nginx:       build: ./nginx
  main-api:    build: ./backend (FASTAPI_PORT=8000)
  gateway:     build: ./gateway (FASTAPI_PORT=8001)
  playground:  build: ./playground (FASTAPI_PORT=8002)
  celery-ai:   build: ./backend (celery worker, ai queue)
  celery-analytics: build: ./backend (celery worker, analytics queue)
  frontend:    build: ./frontend (Next.js dev server)
```

### GitHub Actions CI/CD
```
On PR:
  → Lint (ruff, mypy, eslint)
  → Tests (pytest, playwright)
  → Build Docker images (no push)
  → Security scan (trivy)

On merge to main:
  → All PR checks
  → Docker build + push to ECR
  → Deploy to staging (ECS rolling update)
  → Smoke tests against staging
  → Manual approval gate
  → Deploy to production
```

---

---

## 15. Success Metrics & KPIs

### Product Metrics (Primary)

| Metric | Week 1 | Month 1 | Month 3 |
|---|---|---|---|
| Registered users | 500 | 2,000 | 10,000 |
| MCP servers created | 150 | 600 | 3,000 |
| Active deployed servers | 75 | 300 | 1,500 |
| Total MCP tool calls served | 5,000 | 50,000 | 500,000 |
| AI enhancements run | 400 | 1,500 | 8,000 |
| Free → Pro conversions | — | 30 (1.5%) | 150 |

### Quality Metrics (Secondary)
- Average tool quality score of deployed servers: target > 80/100
- User-reported "tool not found" errors: target < 5% of calls
- Gateway P95 latency overhead: target < 250ms

### Infrastructure Metrics
- Gateway uptime: 99.9% (max 8.7 hours downtime/year)
- AI enhancement pipeline success rate: > 99%
- Celery job failure rate: < 0.5%

### Business Metrics
- Monthly Recurring Revenue (MRR): target $500 at month 1, $5,000 at month 3
- Churn: < 5% monthly
- LTV:CAC ratio: target > 3:1

---

---

## 16. Launch Strategy

### Pre-Launch (Weeks 1-2)
1. **Build the product.** Launch nothing until the core flow (spec → AI enhance → deploy → playground) works end-to-end.
2. **Recruit 20 beta users.** Target: developers in the MCP Discord, r/ClaudeAI, Cursor community. Give them Pro accounts for life in exchange for feedback sessions.
3. **Record the demo video.** 90 seconds: paste the Stripe OpenAPI URL, show the AI enhancement panel, show it working in Claude Desktop. This video is the entire marketing asset.

### Launch Day
1. **Hacker News "Show HN":** "MCPForge — build and deploy MCP servers with AI-optimized tool descriptions (deployed servers get selected 260% more often)" — post at 8AM Pacific on a Tuesday.
2. **Twitter/X thread:** 5-tweet thread with the demo video, the quality research finding, and a link. Tag 3-4 AI engineers with large followings.
3. **Reddit:** r/ClaudeAI, r/cursor, r/LocalLLaMA — show the AI enhancement comparison (before vs after descriptions). Visual proof > any description.
4. **Submit the platform to Smithery and Glama** as an MCP tool (yes, MCPForge itself should have an MCP server so users can manage their servers from Claude Desktop).

### Post-Launch (Weeks 2-4)
1. Write a technical blog post: "Why 73% of MCP servers fail and how we fixed it" — this becomes the top search result for "MCP server quality"
2. Cold email 50 companies that have public OpenAPI specs (Stripe, Linear, Notion, Typeform, etc.) — "Your API could be usable from Claude in 60 seconds."
3. Post MCPForge-generated servers for popular APIs as examples — Stripe MCP, Notion MCP, Linear MCP — each listed on Glama/Smithery with "generated by MCPForge" attribution

---

---

## 17. Monetization & Pricing

### Free Tier
- 2 deployed servers
- 3 AI description enhancements per month
- 500 MCP tool calls per month
- 7-day analytics retention
- Community support

### Pro — $12/month (billed monthly) / $9/month (billed annually)
- 10 deployed servers
- Unlimited AI description enhancements
- 10,000 MCP tool calls per month
- 90-day analytics retention
- Custom server slug: `mcpforge.io/mcp/v1/yourname-{slug}`
- Priority support

### Team — $29/seat/month (minimum 2 seats)
- Unlimited servers
- Unlimited AI enhancements
- 100,000 tool calls per month
- Team roles (Admin, Editor, Viewer)
- Audit logs (90-day retention)
- SLA: 99.9% uptime guarantee
- Private servers (not listed in any registry)
- Dedicated support channel

### Add-Ons (available on all tiers)
- Additional tool calls: $1 per 1,000 calls over plan limit (auto-scaled)
- Extended analytics: +$3/month for 1-year retention

**Pricing rationale:** Benchmarked against LangSmith ($39/seat) and CodeRabbit ($12/seat). Pro at $12 is an impulse-buy price for an individual developer. Team at $29/seat is competitive with any developer tool SaaS. The free tier is intentionally generous to drive organic viral spread (other developers see MCP servers with "built with MCPForge" attribution on Glama/Smithery).

---

---

## 18. Product Roadmap

### v1.0 — Launch (Target: 8 weeks)
- ✅ OpenAPI spec ingestion (URL + file upload)
- ✅ Tool selector
- ✅ AI Description Engine
- ✅ Browser MCP Playground
- ✅ Hosted Gateway (SSE transport)
- ✅ Security Scanner (basic checks)
- ✅ Usage Analytics (7-day)
- ✅ Auth (email + GitHub OAuth)
- ✅ Free + Pro pricing

### v1.1 — (Month 2-3)
- StreamableHTTP transport support
- Team collaboration (invites, roles, audit logs)
- Description version history
- Registry submission automation (Smithery, Glama)
- AI enhancement re-runs with diff comparison

### v1.2 — (Month 4-6)
- Visual Tool Builder — define tools from scratch without an OpenAPI spec
- Multi-spec composition — combine multiple API specs into one MCP server
- Webhook notifications — get alerted on error spikes
- OAuth2 upstream support (for APIs that require OAuth)
- MCP Resources support (in addition to Tools)

### v2.0 — (Month 6-12)
- Fine-tuned description model trained on MCPForge usage data (better enhancement quality)
- MCP server templates marketplace — community-shared server configs
- Enterprise self-host option (Docker Compose + license key)
- Analytics API (programmatic access to analytics data)
- CLI companion (for teams that prefer terminal workflows)

---

---

## Appendix A — MCP Protocol Reference

The gateway must implement these MCP protocol methods correctly:

| Method | Description |
|---|---|
| `initialize` | Client handshake — return capabilities and server info |
| `tools/list` | Return all tools with names, descriptions, input schemas |
| `tools/call` | Execute a tool with given arguments, return result |
| `ping` | Health check — return empty response |

Transport: SSE (Server-Sent Events) uses `text/event-stream` with JSON-RPC 2.0 messages. StreamableHTTP uses `POST` with `application/json` body and optional streaming response.

---

## Appendix B — AI Enhancement Prompt Template (Core)

```
You are an MCP tool description specialist. Your job is to rewrite tool descriptions 
to maximize the probability that an LLM will correctly select and use this tool.

A peer-reviewed study found that tool descriptions scoring high on 4 dimensions are 
selected 260% more often. The 4 dimensions are:
1. FUNCTIONALITY (30pts): What does the tool do and what does it return?
2. ACCURACY (25pts): Are all parameter types, constraints, and behaviors correct?
3. COMPLETENESS (25pts): Are ALL parameters described, including optional ones?
4. CONTEXT (20pts): When SHOULD and SHOULD NOT this tool be used?

Original tool name: {original_name}
Original description: {original_description}
HTTP method: {method}
Endpoint path: {path}
Full parameter schema: {schema_json}
Response schema: {response_schema_json}
Sibling tools (for disambiguation): {sibling_tool_names_and_descriptions}

Rewrite this tool to score 90+ on all 4 dimensions. Output ONLY valid JSON in this format:
{
  "tool_name": "...",  // snake_case, action-oriented, 2-4 words max
  "tool_description": "...",  // 2-4 sentences: what it does, what it returns, when to use it
  "parameters": [{"name": ..., "description": ...}],
  "return_description": "...",  // What the caller can expect back
  "changes_summary": [...]  // Brief list of what you changed
}
```

---

## Appendix C — Security Scan Rules (v1.0)

```python
SECURITY_RULES = [
    {
        "id": "SSRF_URL_PARAM",
        "severity": "CRITICAL",
        "check": "Any tool parameter named 'url', 'endpoint', 'uri', 'target', 'host' with type string",
        "message": "This tool accepts a URL parameter that could be exploited for SSRF if not validated server-side"
    },
    {
        "id": "NO_AUTH_DELETE",
        "severity": "HIGH",
        "check": "DELETE endpoint tool with auth_scheme == 'none'",
        "message": "Unauthenticated DELETE operations can result in unauthorized data deletion"
    },
    {
        "id": "CREDENTIAL_IN_RESPONSE",
        "severity": "HIGH",
        "check": "Response schema contains field names matching /password|secret|private_key|api_key/i",
        "message": "Response may include sensitive credentials — verify this is intentional"
    },
    {
        "id": "PROMPT_INJECTION_DESC",
        "severity": "MEDIUM",
        "check": "Tool description contains markdown links, HTML tags, or strings matching /ignore (previous|above)|disregard/i",
        "message": "Tool description may be vulnerable to prompt injection"
    },
    {
        "id": "NO_AUTH",
        "severity": "MEDIUM",
        "check": "auth_scheme == 'none' on a server with any POST/PUT/PATCH tools",
        "message": "Server has write-capable tools with no authentication configured"
    }
]
```

---

*This document reflects the complete specification for MCPForge v1.0. All features described herein are in-scope for the initial release. Features marked as v1.1+ are out of scope for the launch milestone.*

*Document Owner: Partha Saradhi Munakala | Review cycle: Before each sprint*
