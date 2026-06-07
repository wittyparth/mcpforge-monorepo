# Feature 2 — AI Description Engine

> **PRD reference:** § 7 Feature 2 (lines 263-322)
> **Build order:** Wave 1, Step 3
> **Estimated effort:** 5-7 days for one engineer
> **This is the core product differentiator.** Zero competitors have this.

---

## 0. TL;DR

After a user selects tools from their OpenAPI spec (F1), the AI Description Engine rewrites every tool's name, description, parameters, and return description to maximize LLM tool selection probability. The engine is grounded in arxiv 2602.18914's 4-dimension quality framework (Functionality, Accuracy, Completeness, Context).

**The engine is provider-agnostic via the OpenAI-compatible protocol.** It works with any LLM endpoint that speaks the OpenAI Chat Completions API — DeepSeek (primary: `deepseek-v4-flash`), OpenAI, Anthropic (via their OpenAI-compatible proxy or third-party proxies), OpenCode Go, OpenRouter, or a self-hosted model. The provider, base URL, model name, and API key are all controlled via environment variables — switch providers without code changes.

The output is a side-by-side review panel where users can accept/reject/edit each AI suggestion. Quality scores (0-100, with color-coded badges) drive user trust. Free tier gets 3 AI enhancements per month; Pro gets unlimited.

**This feature is what we sell.** Everything else is plumbing.

---

## 1. Goals & Non-Goals

### 1.1 In scope (v1.0)
- AI enhancement of any tool in `mcp_servers.tools_config`
- Side-by-side diff UI (original vs AI enhanced)
- Quality score on 4 dimensions (0-100, color-coded)
- Edit / revert / bulk-accept flows
- Cost tracking (display estimated cost in UI, log actual cost in DB)
- Async via Celery with SSE progress events
- Prompt caching to keep costs at ~$0.02-0.05 per server
- Re-run on individual tool or all tools
- 4 quality badges: Excellent (90+) / Good (70-89) / Fair (50-69) / Poor (<50)
- "Accept All" button for users who trust the AI
- "Revert to original" per field
- Free tier quota: 3 enhancements per user per month (tracked in `users.ai_enhancement_credits`)
- Preserve original descriptions in `mcp_servers.original_tools_config` for revert

### 1.2 Out of scope (defer to v1.1+)
- Fine-tuned model trained on our usage data (v2.0)
- A/B testing of prompt variants (v1.1)
- User feedback loop ("was this description useful?") (v1.1)
- Cross-spec disambiguation (when server has 2 tools with similar names) — v1.1
- Multi-language descriptions (i18n) (v2.0)
- Pre-generation spec quality scoring (predict which tools will need heavy editing) (v1.2)
- Streaming AI responses (token-by-token) (v1.1)

---

## 2. User Stories

- As a user, I see a Description Review Panel after the build pipeline completes.
- As a user, I see each tool's original description and the AI-enhanced version side-by-side.
- As a user, I see a quality score (0-100) with a color-coded badge (green/yellow/orange/red).
- As a user, I can click any AI field to edit it inline.
- As a user, I can click "Revert to original" on any individual field.
- As a user, I can click "Accept All AI Suggestions" to apply all enhancements without review.
- As a user, I see a list of improvements the AI made (orange badges: "Added disambiguation", "Added return value description", etc.).
- As a user, I see an estimated cost for the AI run (e.g., "$0.04 for 12 tools").
- As a user, I can re-run AI on a single tool or all tools.
- As a user on the free tier, I see my remaining AI credits ("3 enhancements remaining this month").
- As a Pro user, I have unlimited enhancements.
- As a user, I can see real-time progress during AI enhancement (SSE: "Enhancing tool 3 of 12...").
- As a user, I can see the AI prompt that was used (advanced, behind a "Show details" toggle).
- As a user, my edits to AI-enhanced descriptions are tracked (for the F6 "Description Performance" panel).

---

## 3. Architecture Diagram

```
                    ┌─────────────────────┐
                    │  Browser             │
                    │  /servers/{slug}     │
                    │  /tools              │
                    │                      │
                    │  Description Review  │
                    │  Panel:              │
                    │  ┌──────┬──────┐     │
                    │  │Orig  │ AI   │     │
                    │  │      │[edit]│     │
                    │  └──────┴──────┘     │
                    │  Quality: 87/100     │
                    │  [Accept][Revert]    │
                    └──────────┬───────────┘
                               │ POST /servers/{id}/tools/enhance
                               │   body: { tool_names?: string[] }
                               ▼
                    ┌─────────────────────┐
                    │  Main API            │
                    │  POST .../enhance    │
                    │                      │
                    │  1. Check credits    │
                    │  2. Check server     │
                    │     ownership        │
                    │  3. Snapshot tools_  │
                    │     config to        │
                    │     original_        │
                    │     tools_config     │
                    │  4. Enqueue Celery   │
                    │     task             │
                    │  5. Return job_id    │
                    │  6. Stream SSE       │
                    │     events           │
                    └──────────┬───────────┘
                               │
                               ▼  Celery queue=ai
                    ┌─────────────────────┐
                    │  Celery worker       │
                    │  (queue=ai)          │
                    │                      │
                    │  enhance_all_tools() │
                    │  ├─ for each tool:   │
                    │  │   enhance_single()│
                    │  │   ├─ build prompt │
                    │  │   ├─ LLM API     │
                    │  │   │  (OpenAI-     │
                    │  │   │   compatible) │
                    │  │   ├─ parse JSON   │
                    │  │   ├─ score quality│
                    │  │   └─ write back   │
                    │  └─ emit SSE events  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │  LLM Provider           │
                    │  (OpenAI-compatible)    │
                    │                         │
                    │  Primary:               │
                    │  - DeepSeek V4 Flash    │
                    │  - $0.14/$0.28 per MTok│
                    │                         │
                    │  Alt providers:         │
                    │  - OpenAI GPT-4o        │
                    │  - Anthropic Claude     │
                    │  - OpenCode Go          │
                    │  - OpenRouter           │
                    │  - Self-hosted          │
                    │                         │
                    │  Switch via .env:       │
                    │  LLM_PROVIDER=...       │
                    │  LLM_BASE_URL=...       │
                    │  LLM_MODEL=...          │
                    │  LLM_API_KEY=...        │
                    └─────────────────────────┘
```

### 3.1 Data flow

1. User clicks "Re-run AI Enhancement" → `POST /api/v1/servers/{id}/tools/enhance` with `{tool_names?: []}` (all if omitted)
2. Backend validates: user owns server, server has tools_config, user has credits
3. Backend snapshots current tools_config to `mcp_servers.original_tools_config` (preserves for revert)
4. Backend sets `mcp_servers.description_review_status = "in_progress"`, `mcp_servers.last_ai_run_at = now()`
5. Backend enqueues Celery task `enhance_all_descriptions` with server_id, tool_names, request_id
6. Frontend opens SSE: `GET /api/v1/servers/{id}/build-status`
7. SSE stream emits events: `{event: "ai_progress", tool: "search_products", status: "enhancing", progress: 3, total: 12}`
8. For each tool (in parallel up to 5 at a time):
   - Build prompt: tool spec + sibling tools (for disambiguation) + quality framework + 2-3 few-shot examples
   - Call LLM provider via OpenAI-compatible protocol; prompt prefix is reused (DeepSeek caches automatically, Anthropic uses explicit cache_control, others no-op)
   - Parse JSON response
   - Score quality on 4 dimensions (regex/heuristic; LLM self-scoring is unreliable)
   - Write back to `mcp_servers.tools_config[].ai_enhanced_description`, `quality_score`, `improvements_made`
   - Emit SSE: `{event: "tool_enhanced", tool: "search_products", quality_score: 94}`
9. After all done: status = "review", total cost logged to `ai_enhancement_cost_cents`
10. Frontend redirects/updates to show review panel
11. User accepts/rejects/edits; final state saved

### 3.2 Cost economics (DeepSeek primary, with prompt caching)

**Primary provider: DeepSeek V4 Flash** (much cheaper than Anthropic)

| Component | Tokens | Cost (DeepSeek) |
|---|---|---|
| System prompt (cached) | ~3,000 | $0.00042 (cache write, amortized) |
| User prompt (per tool) | ~1,500 | $0.0021 |
| Response (per tool) | ~500 | $0.0014 |
| **Per tool** | | **~$0.004** |
| 12-tool server | | **~$0.05** |
| With cache hit (90%) | | **~$0.02** |
| 1,500 enhancements/mo | | **~$30** |

**Switching to Anthropic Sonnet 4.6 (for higher quality):**
- Per tool: ~$0.012
- 12-tool server: ~$0.14
- 1,500 enhancements/mo: ~$60

**Switching to OpenAI GPT-4o:**
- Per tool: ~$0.013
- 12-tool server: ~$0.16
- 1,500 enhancements/mo: ~$70

DeepSeek is 3-4x cheaper than Anthropic/OpenAI for this workload. Cost optimization strategies:
- Default to DeepSeek for routine enhancements
- Allow users to opt into higher-quality models per server (Pro tier feature)
- Cache the spec prefix (DeepSeek auto-caches, Anthropic explicit, others no-op)
- Batch API for non-urgent re-runs (50% discount) — v1.1

---

## 4. Backend Changes

### 4.1 New dependencies (add to `apps/api/pyproject.toml`)

```toml
"anthropic>=0.50.0",  # Claude API client (with prompt caching + structured output)
"tenacity>=9.0.0",   # for retry helpers (already in F1)
```

### 4.2 New files

```
apps/api/app/
├── services/
│   ├── ai_description_engine.py       # Main orchestrator (NEW)
│   ├── ai_description/
│   │   ├── __init__.py                # (NEW)
│   │   ├── prompts.py                 # Prompt templates (NEW)
│   │   ├── quality_scorer.py          # 4-dimension quality scoring (NEW)
│   │   ├── few_shot_examples.py       # Curated examples (NEW)
│   │   └── tasks.py                   # Celery tasks (NEW)
│   └── server_builder.py              # Orchestrates the build pipeline (NEW)
├── api/v1/endpoints/
│   └── build.py                       # /servers/{id}/build, /build-status SSE (NEW)
├── schemas/
│   └── ai_description.py              # AI response schemas (NEW)
└── core/
    └── anthropic_client.py            # Anthropic SDK wrapper (NEW)

apps/api/tests/
├── test_ai_description_engine.py      # 8 tests (NEW)
├── test_ai_prompts.py                 # 4 tests (NEW)
├── test_quality_scorer.py             # 12 tests (NEW)
├── test_ai_celery_tasks.py             # 6 tests (NEW)
└── test_build_endpoints.py            # 5 tests (NEW)
```

### 4.3 New SQLAlchemy changes

`mcp_servers` table additions (migration `0002_add_ai_enhancement.py`):

```python
"""add AI enhancement fields to mcp_servers"""
def upgrade() -> None:
    op.add_column("mcp_servers", sa.Column("description_review_status", sa.String(20), nullable=False, server_default="pending"))
    op.add_column("mcp_servers", sa.Column("last_ai_run_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("mcp_servers", sa.Column("ai_enhancement_cost_cents", sa.Integer, nullable=False, server_default="0"))
    op.add_column("mcp_servers", sa.Column("original_tools_config", sa.JSON, nullable=True))
    # No index needed (low cardinality)

def downgrade() -> None:
    op.drop_column("mcp_servers", "original_tools_config")
    op.drop_column("mcp_servers", "ai_enhancement_cost_cents")
    op.drop_column("mcp_servers", "last_ai_run_at")
    op.drop_column("mcp_servers", "description_review_status")
```

### 4.4 New Pydantic schemas

#### `app/schemas/ai_description.py` (NEW)

```python
class AIEnhancementRequest(BaseModel):
    tool_names: list[str] | None = None  # None = all tools
    force: bool = False  # bypass quota check (admin only)

class AIEnhancementResponse(BaseModel):
    job_id: str  # Celery task ID
    estimated_cost_cents: int
    estimated_duration_seconds: int
    remaining_credits: int | None  # None for unlimited

class AIQualityScore(BaseModel):
    """Quality score on the 4 dimensions from arxiv 2602.18914."""
    functionality: int = Field(ge=0, le=30)  # out of 30
    accuracy: int = Field(ge=0, le=25)  # out of 25
    completeness: int = Field(ge=0, le=25)  # out of 25
    context: int = Field(ge=0, le=20)  # out of 20
    total: int = Field(ge=0, le=100)
    badge: Literal["Excellent", "Good", "Fair", "Poor"]
    
    @model_validator(mode="after")
    def total_must_equal_sum(self):
        expected = self.functionality + self.accuracy + self.completeness + self.context
        if self.total != expected:
            raise ValueError(f"total ({self.total}) must equal sum of dimensions ({expected})")
        return self

class AIImprovementItem(BaseModel):
    category: Literal[
        "added_disambiguation",
        "rewrote_description",
        "rewrote_parameters",
        "added_return_description",
        "added_when_to_use",
        "added_when_not_to_use",
        "renamed_tool",
        "fixed_parameter_meaning",
    ]
    summary: str  # human-readable, e.g., "Rewrote 3 parameter descriptions"

class AIEnhancedTool(BaseModel):
    name: str  # original (immutable)
    original_description: str
    original_parameters: list[ToolParameter]
    enhanced_name: str | None = None  # AI may suggest rename
    enhanced_description: str
    enhanced_parameters: list[ToolParameter]
    enhanced_return_description: str | None
    quality_score: AIQualityScore
    improvements: list[AIImprovementItem]
    enhanced_at: datetime
    enhanced_by: str  # 'ai' | 'user' (after user edit)

class ToolAcceptRequest(BaseModel):
    """User accepts AI enhancements (all or subset)."""
    accepted_tools: list[str]  # tool names to accept
    rejected_tools: list[str] = []  # tools to revert to original
    custom_edits: dict[str, dict] = {}  # tool_name → {description, parameters, ...}

class BuildEvent(BaseModel):
    """SSE event payload for the build progress stream."""
    event: Literal["start", "ai_progress", "tool_enhanced", "ai_complete", "scanner_start", "scanner_complete", "done", "error"]
    timestamp: datetime
    data: dict  # event-specific data
```

### 4.5 New endpoints

| Method | Path | Handler | Request | Response | Errors |
|---|---|---|---|---|---|
| POST | `/api/v1/servers/{id}/tools/enhance` | `enhance_tools` | `AIEnhancementRequest` | `AIEnhancementResponse` | 402 OUT_OF_CREDITS, 404, 409 ALREADY_RUNNING |
| POST | `/api/v1/servers/{id}/tools/enhance/{name}` | `enhance_single_tool` | — | `AIEnhancedTool` | 402, 404 |
| POST | `/api/v1/servers/{id}/tools/accept` | `accept_tools` | `ToolAcceptRequest` | `MCPServerResponse` | 400, 404 |
| GET | `/api/v1/servers/{id}/build-status` | `build_status_sse` | — | text/event-stream | 404 |
| POST | `/api/v1/servers/{id}/build` | `start_build` | — | `AIEnhancementResponse` | 402, 404 |

### 4.6 New services — pseudocode

#### `app/core/llm_client.py` (NEW, ~150 lines)

```python
"""
Multi-provider LLM client using the OpenAI-compatible Chat Completions protocol.

Works with any provider that speaks OpenAI's API:
- DeepSeek (primary, $0.14/$0.28 per MTok input/output)
- OpenAI (GPT-4o, GPT-4-turbo, etc.)
- Anthropic (via OpenAI-compatible proxy like anthropic-sdk-openai or LiteLLM)
- OpenCode Go
- OpenRouter (unified access to many models)
- Self-hosted models via vLLM, TGI, etc.

The provider, base URL, model, and API key are all controlled via .env:
  LLM_PROVIDER=deepseek
  LLM_BASE_URL=https://api.deepseek.com/v1
  LLM_MODEL=deepseek-v4-flash
  LLM_API_KEY=sk-...
"""

import openai
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# Pricing per 1M tokens (in cents, input/output) — used for cost tracking
# Update when prices change. Add new providers as needed.
PROVIDER_PRICING = {
    "deepseek-v4-flash": {"input": 14.0, "output": 28.0, "cache_read": 1.4, "cache_write": 14.0},
    "deepseek-chat":     {"input": 14.0, "output": 28.0, "cache_read": 1.4, "cache_write": 14.0},
    "gpt-4o":            {"input": 250.0, "output": 1000.0, "cache_read": 125.0, "cache_write": 0.0},
    "gpt-4o-mini":       {"input": 15.0, "output": 60.0, "cache_read": 7.5, "cache_write": 0.0},
    "claude-sonnet-4-6": {"input": 300.0, "output": 1500.0, "cache_read": 30.0, "cache_write": 375.0},
    "claude-haiku-4-5":  {"input": 80.0, "output": 400.0, "cache_read": 8.0, "cache_write": 100.0},
    # Add more as needed; unknown models default to zero
}

# Default pricing when model isn't in the table
DEFAULT_PRICING = {"input": 100.0, "output": 300.0, "cache_read": 10.0, "cache_write": 100.0}


class LLMClient:
    """Singleton wrapper around the OpenAI-compatible SDK with retry + logging."""

    _client: AsyncOpenAI | None = None

    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        if cls._client is None:
            if not settings.LLM_API_KEY:
                raise RuntimeError("LLM_API_KEY not set")
            if not settings.LLM_BASE_URL:
                raise RuntimeError("LLM_BASE_URL not set")
            if not settings.LLM_MODEL:
                raise RuntimeError("LLM_MODEL not set")
            cls._client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                max_retries=0,  # we handle retries ourselves
                timeout=float(settings.LLM_TIMEOUT_SECONDS),
            )
            logger.info("llm_client_initialized", provider=settings.LLM_PROVIDER, base_url=settings.LLM_BASE_URL, model=settings.LLM_MODEL)
        return cls._client

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing or env var changes)."""
        cls._client = None

    @classmethod
    @retry(
        stop=stop_after_attempt(settings.LLM_RETRY_ATTEMPTS),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError)),
        reraise=True,
    )
    async def chat_completion(
        cls,
        messages: list[dict],
        system: str | list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict | None = None,
        extra_body: dict | None = None,
    ) -> dict:
        """
        Call the LLM via OpenAI-compatible Chat Completions API.

        Returns a dict with: content, usage, model, provider
        Raises on error.
        """
        client = cls.get_client()

        # Build messages
        msgs = []
        if system:
            if isinstance(system, str):
                msgs.append({"role": "system", "content": system})
            elif isinstance(system, list):
                # Already structured (e.g., for caching)
                msgs.extend(system)
        msgs.extend(messages)

        # Build kwargs
        kwargs = {
            "model": settings.LLM_MODEL,
            "messages": msgs,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        elif settings.LLM_MAX_TOKENS:
            kwargs["max_tokens"] = int(settings.LLM_MAX_TOKENS)
        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["temperature"] = float(settings.LLM_TEMPERATURE)
        if response_format:
            kwargs["response_format"] = response_format
        if extra_body:
            kwargs["extra_body"] = extra_body

        # Add prompt caching headers if supported and enabled
        # (Anthropic via OpenAI-compatible proxy supports this; DeepSeek caches automatically)
        if settings.LLM_PROMPT_CACHING_ENABLED:
            # Some providers support cache_control via extra_body
            # For Anthropic via proxy: extra_body={"cache_control": {"type": "ephemeral"}}
            # We don't set it by default since it's provider-specific
            pass

        try:
            response = await client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            logger.warning("llm_rate_limit", provider=settings.LLM_PROVIDER, model=settings.LLM_MODEL, retry_after=getattr(e.response, "headers", {}).get("retry-after"))
            raise
        except (openai.APIConnectionError, openai.APITimeoutError) as e:
            logger.warning("llm_transient_error", provider=settings.LLM_PROVIDER, error=str(e))
            raise
        # Don't catch other APIError (4xx); let caller handle

        # Extract content
        if not response.choices:
            raise RuntimeError(f"LLM returned no choices: {response}")

        content = response.choices[0].message.content or ""

        # Extract usage (provider-specific fields)
        usage = response.usage
        usage_dict = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }
        # Some providers include cache info in prompt_tokens_details or extra fields
        if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
            details = usage.prompt_tokens_details
            usage_dict["cache_read_tokens"] = getattr(details, "cached_tokens", 0) or 0
        # DeepSeek and others use different field names; check for common ones
        for field in ("cache_read_input_tokens", "cache_creation_input_tokens", "cached_tokens"):
            if hasattr(usage, field):
                usage_dict[field] = getattr(usage, field, 0) or 0

        return {
            "content": content,
            "usage": usage_dict,
            "model": response.model,
            "provider": settings.LLM_PROVIDER,
            "finish_reason": response.choices[0].finish_reason,
        }

    @classmethod
    def calculate_cost_cents(cls, usage: dict, model: str | None = None) -> int:
        """Calculate cost in cents for a single API call."""
        model = model or settings.LLM_MODEL
        pricing = PROVIDER_PRICING.get(model, DEFAULT_PRICING)

        input_cost = (usage.get("input_tokens", 0) / 1_000_000) * pricing["input"]
        output_cost = (usage.get("output_tokens", 0) / 1_000_000) * pricing["output"]
        cache_read_tokens = usage.get("cache_read_tokens", 0) or usage.get("cache_read_input_tokens", 0) or 0
        cache_read_cost = (cache_read_tokens / 1_000_000) * pricing["cache_read"]
        cache_write_tokens = usage.get("cache_creation_input_tokens", 0) or 0
        cache_write_cost = (cache_write_tokens / 1_000_000) * pricing["cache_write"]

        total_cents = input_cost + output_cost + cache_read_cost + cache_write_cost
        return int(total_cents)
```

#### `app/services/ai_description/prompts.py` (NEW, ~250 lines)

```python
# This is the core of the product. Tune carefully.

SYSTEM_PROMPT = """You are an expert AI tool description engineer for the Model Context Protocol (MCP) ecosystem.

Your job: rewrite OpenAPI tool definitions so LLMs select and use them correctly and reliably.

A peer-reviewed study (arxiv 2602.18914) found that tool descriptions scoring high on 4 quality dimensions are selected 260% more often than mechanically-generated ones. The 4 dimensions are:

1. FUNCTIONALITY (0-30 points): Does the description say WHAT the tool does and WHEN to use it? The strongest predictor of selection. Use "USE THIS WHEN you need X" and "DO NOT USE FOR Y" clauses.

2. ACCURACY (0-25 points): Are parameter types, constraints, and behaviors described correctly? Match exactly what the API does. No hallucinated parameters.

3. COMPLETENESS (0-25 points): Are ALL parameters (including optional ones) AND the return value described? A missing return description is the #2 cause of LLM misuse.

4. CONTEXT (0-20 points): Does the description help an LLM decide WHEN to use this tool vs sibling tools? Reference sibling tools by name when relevant.

You will receive:
- The original tool spec (name, description, parameters, request body, response schema)
- A list of sibling tools (for disambiguation)
- The OpenAPI spec context (for grounding)

Rewrite to score 90+ on all 4 dimensions. Be concise — every token costs money when this tool is loaded into LLM context.

Output MUST be valid JSON matching the schema provided. No prose, no markdown, just JSON.
"""

USER_PROMPT_TEMPLATE = """<original_tool>
Name: {tool_name}
Description: {tool_description}
HTTP method: {method}
Path: {path}
Tags: {tags}

Parameters:
{parameters_formatted}

Request body schema:
{request_body_schema}

Response schemas (by status code):
{response_schemas}

Security requirements:
{security_requirements}
</original_tool>

<sibling_tools_for_disambiguation>
{sibling_tools_formatted}
</sibling_tools_for_disambiguation>

<examples>
{few_shot_examples}
</examples>

<instructions>
1. Read the original tool carefully. Understand its purpose from the spec context.
2. Write a NEW tool name (snake_case, 2-4 words, action-oriented) ONLY if the original is vague (e.g., "get" → "get_user_by_id").
3. Write a NEW tool description (2-4 sentences):
   - Sentence 1: What the tool does
   - Sentence 2: When to use it (with "USE THIS WHEN" clause if siblings exist)
   - Sentence 3: What it returns (key fields, format)
   - Sentence 4 (optional): When NOT to use it
4. For EACH parameter, write a description that explains:
   - What the parameter means in plain English
   - Valid values or format (e.g., "ISO 8601 timestamp", "positive integer")
   - Example value
5. Write a return_description explaining what the caller gets back, including edge cases (empty array, error format).
6. Compute the quality_score: 0-100 based on the 4 dimensions.
7. List the improvements_made as short phrases.

Output ONLY the JSON object. No prose before or after.
</instructions>
"""

FEW_SHOT_EXAMPLES = [
    {
        "input": {
            "name": "get",
            "description": "Get an item",
            "method": "GET",
            "path": "/items/{id}",
        },
        "output": {
            "tool_name": "get_item_by_id",
            "tool_description": "Retrieve a single item by its unique ID. USE THIS WHEN the user has a specific item ID and wants its full details. Returns the item with all its fields, or 404 if not found. DO NOT USE FOR listing multiple items (use list_items instead).",
            "parameters": [
                {
                    "name": "id",
                    "description": "The unique identifier of the item to retrieve. UUID format. Example: 'item_abc123'",
                    "required": True,
                    "type": "string"
                }
            ],
            "return_description": "Returns the item object with all fields populated. Returns 404 with {error: 'not_found'} if no item exists with that ID.",
            "quality_score": 92,
            "improvements_made": [
                "Renamed 'get' to 'get_item_by_id' for clarity",
                "Added disambiguation: 'DO NOT USE FOR listing multiple items'",
                "Added example for parameter",
                "Added return value description with error case"
            ]
        }
    },
    {
        "input": {
            "name": "create",
            "description": "Create a resource",
            "method": "POST",
            "path": "/resources",
        },
        "output": {
            "tool_name": "create_resource",
            "tool_description": "Create a new resource. USE THIS WHEN the user wants to add a new resource to the system. Returns the created resource with its assigned ID. This is a write operation; requires authentication.",
            "parameters": [
                {
                    "name": "name",
                    "description": "The name of the resource. 1-100 characters. Required.",
                    "required": True,
                    "type": "string"
                },
                {
                    "name": "metadata",
                    "description": "Optional key-value pairs to attach to the resource. Each key max 64 chars, each value max 256 chars. Example: {'category': 'documentation', 'priority': 'high'}",
                    "required": False,
                    "type": "object"
                }
            ],
            "return_description": "Returns the created resource object including its server-assigned ID, creation timestamp, and any defaults applied to omitted fields.",
            "quality_score": 88,
            "improvements_made": [
                "Renamed to 'create_resource'",
                "Added 'requires authentication' note",
                "Added constraints to parameters (length, format)",
                "Added return value description"
            ]
        }
    }
]
```

#### `app/services/ai_description/quality_scorer.py` (NEW, ~200 lines)

```python
"""
Scores a tool description on 4 dimensions from arxiv 2602.18914.

Uses regex/heuristic analysis (NOT LLM self-scoring — that's unreliable).
Inspired by the paper's quality framework.

Returns AIQualityScore with per-dimension scores and total.
"""

import re
from app.schemas.ai_description import AIQualityScore, AIImprovementItem

# Patterns
USE_THIS_WHEN_PATTERN = re.compile(r"\b(use this when|when to use|use for|use this to)\b", re.IGNORECASE)
DO_NOT_USE_PATTERN = re.compile(r"\b(do not use|don't use|use .* instead|not for|avoid)\b", re.IGNORECASE)
RETURN_PATTERN = re.compile(r"\b(returns?|response|will get|you get|provides?|output)\b", re.IGNORECASE)

class QualityScorer:
    """Scores a tool description on 4 dimensions."""
    
    def score(self, enhanced_tool: dict, original_tool: dict, all_tools: list[dict]) -> AIQualityScore:
        functionality = self._score_functionality(enhanced_tool, all_tools)
        accuracy = self._score_accuracy(enhanced_tool, original_tool)
        completeness = self._score_completeness(enhanced_tool, original_tool)
        context = self._score_context(enhanced_tool, all_tools)
        
        total = functionality + accuracy + completeness + context
        
        if total >= 90:
            badge = "Excellent"
        elif total >= 70:
            badge = "Good"
        elif total >= 50:
            badge = "Fair"
        else:
            badge = "Poor"
        
        return AIQualityScore(
            functionality=functionality,
            accuracy=accuracy,
            completeness=completeness,
            context=context,
            total=total,
            badge=badge,
        )
    
    def _score_functionality(self, tool: dict, all_tools: list[dict]) -> int:
        """0-30: Does the description say what the tool does and when to use it?"""
        score = 0
        description = tool.get("enhanced_description", "")
        
        # Has a clear action verb at the start
        first_word = description.split()[0].lower() if description.split() else ""
        action_verbs = {"retrieve", "fetch", "create", "update", "delete", "list", "search", "find", "send", "get", "upload", "download", "calculate", "validate", "transform", "convert", "process", "analyze"}
        if first_word in action_verbs:
            score += 8
        elif any(description.lower().startswith(v) for v in action_verbs):
            score += 6
        
        # Description is 50-300 chars (sweet spot)
        desc_len = len(description)
        if 50 <= desc_len <= 300:
            score += 7
        elif 30 <= desc_len < 50 or 300 < desc_len <= 500:
            score += 4
        else:
            score += 2
        
        # Has "USE THIS WHEN" or "use this for" guidance
        if USE_THIS_WHEN_PATTERN.search(description):
            score += 10
        elif any(phrase in description.lower() for phrase in ["when", "if you need", "for getting", "for creating"]):
            score += 5
        
        # No vague single-word descriptions
        if description.lower().strip() in {"get", "create", "update", "delete", "list"}:
            score -= 15
        
        return min(max(score, 0), 30)
    
    def _score_accuracy(self, tool: dict, original: dict) -> int:
        """0-25: Do parameter descriptions match their types and constraints?"""
        score = 0
        params = tool.get("enhanced_parameters", [])
        orig_params = original.get("parameters", [])
        
        if not params:
            return 0  # No parameters = no accuracy concerns
        
        # All params have descriptions
        described = sum(1 for p in params if p.get("description", "").strip())
        score += int(15 * described / len(params))
        
        # Descriptions are non-trivial (>10 chars)
        detailed = sum(1 for p in params if len(p.get("description", "")) > 10)
        score += int(5 * detailed / len(params))
        
        # Parameter types match (sanity check)
        for p, op in zip(params, orig_params):
            if p.get("type") != op.get("type"):
                score -= 3  # mismatch penalty
        
        # Required flag preserved
        for p, op in zip(params, orig_params):
            if p.get("required") != op.get("required"):
                score -= 2
        
        return min(max(score, 0), 25)
    
    def _score_completeness(self, tool: dict, original: dict) -> int:
        """0-25: Are all parameters + return value described?"""
        score = 0
        orig_params = original.get("parameters", [])
        params = tool.get("enhanced_parameters", [])
        return_desc = tool.get("enhanced_return_description", "")
        
        # All original parameters have descriptions
        if len(params) == len(orig_params) and len(params) > 0:
            score += 10
        elif len(params) > 0:
            score += int(10 * len(params) / max(len(orig_params), 1))
        
        # Optional parameters are described
        optional = [p for p in orig_params if not p.get("required")]
        if optional:
            optional_described = sum(1 for p in params if not p.get("required") and p.get("description"))
            score += int(8 * optional_described / len(optional))
        
        # Return value described
        if return_desc and len(return_desc) > 20:
            score += 7
        elif return_desc:
            score += 3
        
        # Has edge case mention
        if any(phrase in return_desc.lower() for phrase in ["empty", "null", "not found", "error", "[]", "{}"]):
            score += 3
        
        return min(max(score, 0), 25)
    
    def _score_context(self, tool: dict, all_tools: list[dict]) -> int:
        """0-20: Does description help LLM decide when to use vs siblings?"""
        score = 0
        description = tool.get("enhanced_description", "")
        tool_name = tool.get("enhanced_name") or tool.get("name", "")
        
        # Has "USE THIS WHEN" or similar
        if USE_THIS_WHEN_PATTERN.search(description):
            score += 7
        
        # Has "DO NOT USE" or disambiguation
        if DO_NOT_USE_PATTERN.search(description):
            score += 8
        
        # References a sibling tool by name
        sibling_names = [t.get("name", "") for t in all_tools if t.get("name") != tool_name]
        if any(name in description for name in sibling_names):
            score += 5
        
        # Has tags or category info
        tags = tool.get("tags", [])
        if tags and any(tag in description.lower() for tag in tags):
            score += 2
        
        return min(max(score, 0), 20)
```

#### `app/services/ai_description_engine.py` (NEW, ~250 lines)

```python
"""
The AI Description Engine. Coordinates:
- Prompt construction
- LLM API call (OpenAI-compatible; prompt caching if supported)
- Quality scoring
- Database persistence
- SSE event emission
"""

from app.core.anthropic_client import AnthropicClient
from app.services.ai_description.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, FEW_SHOT_EXAMPLES
from app.services.ai_description.quality_scorer import QualityScorer
from app.schemas.ai_description import AIQualityScore, AIImprovementItem

class AIDescriptionEngine:

    def __init__(self, settings, llm_client: LLMClient, scorer: QualityScorer):
        self.settings = settings
        self.client = llm_client
        self.scorer = scorer
        # Model is set via env (LLM_MODEL); no hardcoded value here
    
    async def enhance_tool(
        self,
        tool: dict,
        all_tools: list[dict],
        spec_context: dict,  # for grounding
        spec_prefix_cache_id: str | None = None,  # for prompt caching
    ) -> dict:
        """
        Enhances a single tool description.
        Returns the enhanced tool dict with quality score and improvements.
        """
        # 1. Build prompt
        sibling_tools = self._format_siblings(all_tools, exclude=tool["name"])
        parameters_formatted = self._format_parameters(tool.get("parameters", []))
        few_shot = self._format_few_shot()
        
        user_prompt = USER_PROMPT_TEMPLATE.format(
            tool_name=tool.get("name", ""),
            tool_description=tool.get("description", ""),
            method=tool.get("method", ""),
            path=tool.get("path", ""),
            tags=", ".join(tool.get("tags", [])),
            parameters_formatted=parameters_formatted,
            request_body_schema=json.dumps(tool.get("request_body_schema", {}), indent=2),
            response_schemas=json.dumps(tool.get("response_schemas", {}), indent=2),
            security_requirements=json.dumps(tool.get("security_requirements", []), indent=2),
            sibling_tools_formatted=sibling_tools,
            few_shot_examples=few_shot,
        )
        
        # 2. Call LLM (OpenAI-compatible) with structured JSON output
        # Build messages: system prompt + spec context (cacheable prefix) + user prompt
        system_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        # If the provider supports prompt caching (DeepSeek auto, Anthropic via proxy),
        # the repeated prefix is cached automatically. We can hint via extra_body for some providers.
        extra_body = None
        if self.settings.LLM_PROMPT_CACHING_ENABLED and self.settings.LLM_PROVIDER == "anthropic":
            # Anthropic via OpenAI-compatible proxy supports cache_control via extra_body
            extra_body = {"cache_control": {"type": "ephemeral"}}

        try:
            result = await self.client.chat_completion(
                messages=[
                    # Include spec context as a separate "user" message to maximize cache hits
                    {"role": "user", "content": f"<spec_context>\n{json.dumps(spec_context, indent=2)}\n</spec_context>"},
                    {"role": "user", "content": user_prompt},
                ],
                system=system_messages[0]["content"],
                max_tokens=2000,
                temperature=0.0,
                response_format={"type": "json_object"} if self.settings.LLM_JSON_MODE else None,
                extra_body=extra_body,
            )
        except openai.APIError as e:
            logger.error("llm_api_error", tool=tool["name"], provider=self.settings.LLM_PROVIDER, error=str(e))
            raise AIDescriptionError(f"LLM API error: {e.message}") from e

        # 3. Parse response
        response_text = result["content"]
        try:
            enhanced = self._parse_json_response(response_text)
        except ValueError as e:
            logger.error("ai_response_parse_failed", tool=tool["name"], response=response_text[:500])
            raise AIDescriptionError(f"AI returned invalid JSON: {e}") from e

        # 4. Quality score
        quality = self.scorer.score(enhanced, tool, all_tools)

        # 5. Compute improvements made
        improvements = self._compute_improvements(tool, enhanced)

        # 6. Calculate cost (provider-aware)
        cost_cents = self.client.calculate_cost_cents(result["usage"], model=result["model"])
        
        return {
            **tool,  # preserve original
            "enhanced_name": enhanced.get("tool_name"),
            "enhanced_description": enhanced.get("tool_description", tool["description"]),
            "enhanced_parameters": self._normalize_parameters(enhanced.get("parameters", tool.get("parameters", []))),
            "enhanced_return_description": enhanced.get("return_description"),
            "quality_score": quality,
            "improvements_made": improvements,
            "cost_cents": cost_cents,
            "enhanced_at": datetime.utcnow(),
            "enhanced_by": "ai",
            "llm_usage": {
                "input_tokens": result["usage"]["input_tokens"],
                "output_tokens": result["usage"]["output_tokens"],
                "cache_read_tokens": result["usage"].get("cache_read_tokens", 0) or result["usage"].get("cache_read_input_tokens", 0),
                "cache_write_tokens": result["usage"].get("cache_creation_input_tokens", 0) or result["usage"].get("cache_write_tokens", 0),
            },
            "model": result["model"],
            "provider": result["provider"],
        }
    
    def _parse_json_response(self, text: str) -> dict:
        # Sometimes Claude wraps in ```json ... ``` despite instruction not to
        text = text.strip()
        if text.startswith("```"):
            # Strip code fence
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
            if text.startswith("json"):
                text = text[4:].strip()
        
        return json.loads(text)
    
    def _format_siblings(self, all_tools: list[dict], exclude: str) -> str:
        siblings = [t for t in all_tools if t.get("name") != exclude]
        if not siblings:
            return "(no sibling tools)"
        lines = []
        for s in siblings[:20]:  # limit to 20 to keep prompt small
            lines.append(f"- {s.get('name')}: {s.get('description', '')[:100]}")
        return "\n".join(lines)
    
    def _format_parameters(self, parameters: list[dict]) -> str:
        if not parameters:
            return "(no parameters)"
        lines = []
        for p in parameters:
            req = "required" if p.get("required") else "optional"
            desc = p.get("description", "(no description)")
            lines.append(f"- `{p.get('name')}` ({p.get('type', '?')}, {req}): {desc}")
        return "\n".join(lines)
    
    def _format_few_shot(self) -> str:
        # Format the few-shot examples as XML
        formatted = []
        for ex in FEW_SHOT_EXAMPLES:
            formatted.append(f"<example>")
            formatted.append(f"<input>{json.dumps(ex['input'])}</input>")
            formatted.append(f"<output>{json.dumps(ex['output'], indent=2)}</output>")
            formatted.append(f"</example>")
        return "\n".join(formatted)
    
    def _compute_improvements(self, original: dict, enhanced: dict) -> list[AIImprovementItem]:
        improvements = []
        
        if enhanced.get("tool_name") and enhanced["tool_name"] != original.get("name"):
            improvements.append(AIImprovementItem(
                category="renamed_tool",
                summary=f"Renamed from '{original.get('name')}' to '{enhanced['tool_name']}'",
            ))
        
        if enhanced.get("tool_description", "") != original.get("description", ""):
            improvements.append(AIImprovementItem(
                category="rewrote_description",
                summary="Rewrote description for clarity",
            ))
        
        if USE_THIS_WHEN_PATTERN.search(enhanced.get("tool_description", "")):
            improvements.append(AIImprovementItem(
                category="added_when_to_use",
                summary="Added 'USE THIS WHEN' guidance",
            ))
        
        if DO_NOT_USE_PATTERN.search(enhanced.get("tool_description", "")):
            improvements.append(AIImprovementItem(
                category="added_when_not_to_use",
                summary="Added 'DO NOT USE FOR' disambiguation",
            ))
        
        if enhanced.get("return_description") and not original.get("return_description"):
            improvements.append(AIImprovementItem(
                category="added_return_description",
                summary="Added return value description",
            ))
        
        # Parameter improvements
        orig_params = {p["name"]: p for p in original.get("parameters", [])}
        enhanced_params = {p["name"]: p for p in enhanced.get("parameters", [])}
        param_rewrites = sum(1 for name, p in enhanced_params.items() if orig_params.get(name, {}).get("description", "") != p.get("description", ""))
        if param_rewrites > 0:
            improvements.append(AIImprovementItem(
                category="rewrote_parameters",
                summary=f"Rewrote {param_rewrites} parameter description(s)",
            ))
        
        return improvements
    
    def _calculate_cost(self, usage: dict) -> int:
        """Provider-aware cost calculation. Delegates to LLMClient.calculate_cost_cents."""
        return self.client.calculate_cost_cents(usage)
    
    def _normalize_parameters(self, parameters: list) -> list[dict]:
        """Convert AI response parameters to our internal schema format."""
        normalized = []
        for p in parameters:
            if isinstance(p, dict):
                normalized.append({
                    "name": p.get("name", ""),
                    "description": p.get("description", ""),
                    "required": p.get("required", False),
                    "type": p.get("type", "string"),
                    "in": p.get("in", "query"),  # not specified by AI; default
                })
        return normalized
```

#### `app/services/ai_description/tasks.py` (NEW, ~120 lines)

```python
"""
Celery tasks for the AI Description Engine.
"""

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.services.ai_description_engine import AIDescriptionEngine
from app.services.ai_description.quality_scorer import QualityScorer
from app.core.llm_client import LLMClient
from app.services.ai_description.quality_scorer import QualityScorer
from app.core.sse import sse_manager  # see § 4.7

@celery_app.task(
    bind=True,
    name="app.services.ai_description.tasks.enhance_all_descriptions",
    max_retries=2,
    default_retry_delay=60,
    autoretry_for=(AIDescriptionError,),
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
)
def enhance_all_descriptions(self, server_id: str, tool_names: list[str] | None = None, request_id: str = ""):
    """Enhance descriptions for all (or specified) tools of a server."""
    logger.info("ai_enhance_start", server_id=server_id, request_id=request_id)
    
    async def run():
        async with async_session_factory() as session:
            # 1. Load server
            server = await server_repo.get_by_id(UUID(server_id))
            if not server:
                raise AIDescriptionError(f"Server {server_id} not found")
            
            # 2. Get tools to enhance
            all_tools = server.tools_config.get("tools", [])
            tools_to_enhance = all_tools if tool_names is None else [t for t in all_tools if t["name"] in tool_names]
            
            if not tools_to_enhance:
                logger.warning("ai_enhance_no_tools", server_id=server_id)
                return
            
            # 3. Snapshot original (for revert)
            if not server.original_tools_config:
                server.original_tools_config = deepcopy(server.tools_config)
            
            # 4. Enhance in parallel (semaphore = 5)
            engine = AIDescriptionEngine(...)
            scorer = QualityScorer()
            llm_client = LLMClient()
            
            sem = asyncio.Semaphore(5)
            async def enhance_with_semaphore(tool):
                async with sem:
                    try:
                        result = await engine.enhance_tool(tool, all_tools, ...)
                        await sse_manager.publish(server_id, {
                            "event": "tool_enhanced",
                            "tool": tool["name"],
                            "quality_score": result["quality_score"].total,
                        })
                        return result
                    except AIDescriptionError as e:
                        await sse_manager.publish(server_id, {
                            "event": "tool_error",
                            "tool": tool["name"],
                            "error": str(e),
                        })
                        return None  # continue with others
            
            results = await asyncio.gather(*[enhance_with_semaphore(t) for t in tools_to_enhance])
            
            # 5. Write back
            successful = [r for r in results if r]
            for result in successful:
                # Update the tool in server.tools_config
                for i, t in enumerate(server.tools_config["tools"]):
                    if t["name"] == result["name"]:
                        server.tools_config["tools"][i].update({
                            "ai_enhanced_description": result["enhanced_description"],
                            "ai_enhanced_parameters": result["enhanced_parameters"],
                            "ai_enhanced_return_description": result["enhanced_return_description"],
                            "ai_enhanced_name": result.get("enhanced_name"),
                            "ai_quality_score": result["quality_score"].model_dump(),
                            "ai_improvements_made": [i.model_dump() for i in result["improvements_made"]],
                            "ai_enhanced_at": result["enhanced_at"].isoformat(),
                            "ai_enhanced_by": "ai",
                        })
                        break
            
            # 6. Update cost
            total_cost = sum(r.get("cost_cents", 0) for r in successful)
            server.ai_enhancement_cost_cents += total_cost
            server.description_review_status = "review"
            server.last_ai_run_at = datetime.utcnow()
            
            await session.commit()
            
            # 7. Emit final event
            await sse_manager.publish(server_id, {
                "event": "ai_complete",
                "tools_enhanced": len(successful),
                "tools_failed": len(tools_to_enhance) - len(successful),
                "total_cost_cents": total_cost,
            })
            
            # 8. Decrement user credits (if free tier)
            if server.owner.plan == "free":
                user_repo = UserRepository(session)
                await user_repo.decrement_credits(server.user_id, 1)
            
            logger.info("ai_enhance_complete", server_id=server_id, enhanced=len(successful), cost_cents=total_cost, request_id=request_id)
    
    asyncio.run(run())
```

#### `app/services/server_builder.py` (NEW, ~100 lines)

```python
"""
The orchestrator for the full server build pipeline.
Coordinates: spec validation → AI enhancement → security scan → ready.
"""

class ServerBuilder:
    """Builds a server from its tools_config. Emits SSE events at each stage."""
    
    async def build_server(self, server_id: UUID, request_id: str) -> None:
        logger.info("build_start", server_id=str(server_id), request_id=request_id)
        
        # Stage 1: Parsing (already done in F1; just verify)
        await sse_manager.publish(server_id, {"event": "stage", "name": "parsing", "status": "complete"})
        
        # Stage 2: AI Enhancement
        await sse_manager.publish(server_id, {"event": "stage", "name": "ai_enhancement", "status": "starting"})
        enhance_all_descriptions.delay(str(server_id), request_id=request_id)
        # Don't wait — AI runs in worker, emits its own events
        
        # Stage 3: Security Scanner (F5)
        # Will be triggered after AI completes (separate flow)
        # For now, just queue it
        # scan_server_security.delay(str(server_id), request_id=request_id)
```

### 4.7 New core module: SSE event manager

#### `app/core/sse.py` (NEW, ~80 lines)

```python
"""
Server-Sent Events manager for real-time build progress.
Uses Redis pub/sub to fan out events to all connected clients for a server.
"""

import asyncio
import json
from collections import defaultdict
from app.core.redis import get_redis

class SSEManager:
    """Pub/sub for SSE events keyed by server_id."""
    
    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
    
    async def publish(self, server_id: str, event: dict) -> None:
        """Publish an event to all subscribers of this server."""
        r = await get_redis()
        await r.publish(f"sse:{server_id}", json.dumps(event, default=str))
    
    async def subscribe(self, server_id: str) -> asyncio.Queue:
        """Subscribe to events for a server. Returns a queue that receives events."""
        queue = asyncio.Queue()
        self._subscribers[server_id].add(queue)
        return queue
    
    async def unsubscribe(self, server_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[server_id].discard(queue)
        if not self._subscribers[server_id]:
            del self._subscribers[server_id]
    
    async def listener(self):
        """Background task that listens to Redis pub/sub and fans out to queues."""
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.psubscribe("sse:*")
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
            server_id = channel.split(":", 1)[1]
            data = json.loads(message["data"])
            for queue in list(self._subscribers.get(server_id, set())):
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass  # drop if consumer is slow

sse_manager = SSEManager()
```

### 4.8 Test plan

| File | Test count | Coverage |
|---|---|---|
| `test_ai_prompts.py` | 4 | system prompt is non-empty, user prompt template has all placeholders, few-shot examples are valid, prompts fit in 4K tokens |
| `test_quality_scorer.py` | 12 | perfect score (90+), good score (70-89), fair score (50-69), poor (<50), functionality scoring, accuracy scoring, completeness scoring, context scoring with siblings, edge case (empty params), edge case (no description) |
| `test_ai_description_engine.py` | 8 | happy path (mocked Anthropic), response parse error, API error handling, prompt caching set up, cost calculation correct, quality score applied, improvements list populated, normalized parameters |
| `test_ai_celery_tasks.py` | 6 | enhance_all happy, single tool failure (others continue), credit decrement (free tier), no credit decrement (Pro), SSE events emitted, server config updated |
| `test_build_endpoints.py` | 5 | enhance endpoint with credits, enhance without credits (402), single tool enhance, accept endpoint, SSE stream format |

**Mocking strategy:**
- Mock `anthropic.AsyncAnthropic` with `respx` (it wraps httpx)
- For Celery tasks, use `celery_app.task` in eager mode (`task_always_eager=True` in test config)
- Use a fixed `ANTHROPIC_API_KEY` for tests (`sk-test-xxx`)

---

## 5. Frontend Changes

### 5.1 New dependencies (add to `apps/web/package.json`)

(Already in F1's deps; verify these are installed)
- `monaco-editor` + `@monaco-editor/react` (for the description editor)
- `react-resizable-panels` (for side-by-side comparison)
- `@radix-ui/react-tabs` (for the review panel tabs)
- `clsx` (already)

### 5.2 New pages

| Path | Component | Notes |
|---|---|---|
| `/dashboard/servers/[slug]/tools` | Modify from F1 | Add the "AI Review" tab (default) |

### 5.3 New components

```
src/components/builder/  (extend F1's components)
├── ai-review-panel.tsx                    # Main container (NEW)
├── ai-review-tool-card.tsx                # One tool's review (NEW)
├── original-vs-enhanced.tsx               # Side-by-side display (NEW)
├── quality-score-badge.tsx                # Color-coded 0-100 (NEW)
├── quality-score-breakdown.tsx            # 4-dimension detail (NEW)
├── improvements-badges.tsx                # List of improvement chips (NEW)
├── inline-edit-field.tsx                  # Editable AI field (NEW)
├── description-monaco-editor.tsx          # Monaco wrapper (NEW)
├── bulk-accept-button.tsx                 # "Accept All" (NEW)
├── revert-field-button.tsx                # "Revert to original" (NEW)
├── ai-cost-display.tsx                    # "$0.04 for 12 tools" (NEW)
└── ai-credits-indicator.tsx               # "3 enhancements left" (NEW)
```

### 5.4 New hooks

```typescript
// src/hooks/use-ai.ts (NEW)
export function useEnhanceTools(serverId: string) {
  return useMutation({
    mutationFn: (toolNames?: string[]) =>
      api.servers.enhanceTools(serverId, { tool_names: toolNames }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['server', serverId] });
    },
  });
}

export function useEnhanceSingleTool(serverId: string, toolName: string) {
  return useMutation({
    mutationFn: () => api.servers.enhanceSingleTool(serverId, toolName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['server-tools', serverId] });
    },
  });
}

export function useAcceptTools(serverId: string) {
  return useMutation({
    mutationFn: (input: ToolAcceptRequest) => api.servers.acceptTools(serverId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['server', serverId] });
    },
  });
}

export function useBuildStatusSSE(serverId: string) {
  // Uses EventSource, returns { events: BuildEvent[], status: 'idle' | 'running' | 'complete' | 'error' }
  // Reuses logic from F1's useBuildStatus
}
```

### 5.5 New types

```typescript
// src/types/api.ts — add
export interface AIQualityScore {
  functionality: number;  // 0-30
  accuracy: number;       // 0-25
  completeness: number;   // 0-25
  context: number;        // 0-20
  total: number;          // 0-100
  badge: 'Excellent' | 'Good' | 'Fair' | 'Poor';
}

export interface AIImprovementItem {
  category: 'added_disambiguation' | 'rewrote_description' | 'rewrote_parameters' | 'added_return_description' | 'added_when_to_use' | 'added_when_not_to_use' | 'renamed_tool' | 'fixed_parameter_meaning';
  summary: string;
}

export interface AIEnhancedTool {
  name: string;
  original_description: string;
  original_parameters: ToolParameter[];
  enhanced_name: string | null;
  enhanced_description: string;
  enhanced_parameters: ToolParameter[];
  enhanced_return_description: string | null;
  quality_score: AIQualityScore;
  improvements_made: AIImprovementItem[];
  enhanced_at: string;
  enhanced_by: 'ai' | 'user';
}

export interface BuildEvent {
  event: 'start' | 'ai_progress' | 'tool_enhanced' | 'tool_error' | 'ai_complete' | 'scanner_start' | 'scanner_complete' | 'done' | 'error' | 'stage';
  timestamp: string;
  data: Record<string, any>;
}
```

### 5.6 Update `lib/api.ts`

```typescript
servers: {
  // ... existing from F1 ...
  enhanceTools: (serverId: string, input: { tool_names?: string[] }) =>
    request<{ job_id: string; estimated_cost_cents: number; estimated_duration_seconds: number; remaining_credits: number | null }>(
      `/api/v1/servers/${serverId}/tools/enhance`, { method: 'POST', body: input }
    ),
  enhanceSingleTool: (serverId: string, toolName: string) =>
    request<AIEnhancedTool>(`/api/v1/servers/${serverId}/tools/enhance/${toolName}`, { method: 'POST' }),
  acceptTools: (serverId: string, input: { accepted_tools: string[]; rejected_tools: string[]; custom_edits: Record<string, any> }) =>
    request<MCPServer>(`/api/v1/servers/${serverId}/tools/accept`, { method: 'POST', body: input }),
},
```

### 5.7 Test plan

**Vitest component tests:**
- `QualityScoreBadge.test.tsx`: renders correct color for each badge level
- `OriginalVsEnhanced.test.tsx`: shows both columns, edit triggers onClick
- `ImprovementsBadges.test.tsx`: renders each improvement category with correct icon
- `InlineEditField.test.tsx`: switches between display and edit mode
- `RevertFieldButton.test.tsx`: reverts field to original value

**Playwright E2E:**
- `04-ai-review.spec.ts`: create server → wait for AI → review panel appears → accept all → see updated descriptions
- `05-ai-edit-single.spec.ts`: edit one AI field → save → verify it persists

---

## 6. Database / Migration Plan

Migration `0002_add_ai_enhancement.py` (created in this feature):
- Adds `description_review_status`, `last_ai_run_at`, `ai_enhancement_cost_cents`, `original_tools_config` to `mcp_servers`
- Reversible: drops all 4 columns on downgrade

---

## 7. Environment Variables

| Var | Required? | Default | Notes |
|---|---|---|---|
| `LLM_PROVIDER` | Yes (F2) | `deepseek` | One of: `deepseek`, `openai`, `anthropic`, `opencode-go`, `openrouter`, `custom` |
| `LLM_BASE_URL` | Yes (F2) | `https://api.deepseek.com/v1` | OpenAI-compatible base URL |
| `LLM_MODEL` | Yes (F2) | `deepseek-v4-flash` | Primary model name |
| `LLM_API_KEY` | Yes (F2) | (empty) | Provider API key |
| `LLM_MAX_TOKENS` | No | `2000` | Per-request max output |
| `LLM_TEMPERATURE` | No | `0.0` | 0.0 = deterministic |
| `LLM_TIMEOUT_SECONDS` | No | `60` | Per-request timeout |
| `LLM_RETRY_ATTEMPTS` | No | `3` | Retries on 429/5xx |
| `LLM_PROMPT_CACHING_ENABLED` | No | `true` | Provider-dependent; degrades gracefully |
| `LLM_JSON_MODE` | No | `true` | Use OpenAI-style JSON response_format |
| `MAX_AI_CREDITS_PER_USER_PER_DAY` | No | `100` | Hard cap per user (free tier quota) |

### Provider-specific notes

**DeepSeek (primary):**
- Base URL: `https://api.deepseek.com/v1`
- Model: `deepseek-v4-flash` (fast, cheap, high quality)
- Alternative: `deepseek-chat` (similar)
- Supports JSON mode: yes
- Prompt caching: automatic on repeated prefixes (free)
- Pricing: $0.14/$0.28 per MTok input/output

**OpenAI:**
- Base URL: `https://api.openai.com/v1`
- Models: `gpt-4o`, `gpt-4o-mini`, `o1`, etc.
- Supports JSON mode: yes
- Prompt caching: automatic on prefixes (since 2024)
- Pricing varies

**Anthropic (via OpenAI-compatible proxy):**
- Base URL: depends on proxy (e.g., LiteLLM, anthropic-sdk-openai)
- Models: `claude-sonnet-4-6`, `claude-haiku-4-5`
- Supports JSON mode: yes
- Prompt caching: explicit via `cache_control` in extra_body

**OpenCode Go:**
- Base URL: `https://api.opencode-go.com/v1` (verify with provider)
- Model: per OpenCode Go docs
- Supports JSON mode: check provider docs
- Pricing: per OpenCode Go

**OpenRouter:**
- Base URL: `https://openrouter.ai/api/v1`
- Models: any (e.g., `anthropic/claude-sonnet-4-6`, `deepseek/deepseek-chat`)
- Unified access to many providers
- Single API key

**Custom (self-hosted):**
- Base URL: your inference server (vLLM, TGI, etc.)
- Model: whatever your server serves
- Must implement OpenAI Chat Completions protocol

### Switching providers at runtime

To switch from DeepSeek to OpenAI in production:
```bash
# In Render dashboard, update env vars:
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
# No code change, no redeploy needed beyond env var reload
```

The app reads these at startup. To change without restart, expose a `POST /api/v1/admin/llm-config` endpoint (admin-only) that updates the LLMClient singleton.

---

## 8. Observability

### 8.1 Structured logs

```python
logger.info("ai_enhance_start", server_id=server_id, tool_count=len(tools), request_id=request_id)
logger.info("ai_enhance_complete", server_id=server_id, enhanced=len(successful), failed=len(failed), cost_cents=total_cost, duration_ms=duration, request_id=request_id)
logger.warning("ai_enhance_partial", server_id=server_id, failed=len(failed), errors=[e[:200] for e in errors], request_id=request_id)
logger.error("ai_enhance_failed", server_id=server_id, error_code="ALL_TOOLS_FAILED", request_id=request_id)
logger.info("llm_api_call", server_id=server_id, provider=settings.LLM_PROVIDER, model=settings.LLM_MODEL, input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"], cache_read=usage.get("cache_read_tokens", 0), cache_write=usage.get("cache_write_tokens", 0), cost_cents=cost, request_id=request_id)
logger.info("ai_credit_decremented", user_id=user_id, plan=user.plan, remaining_credits=user.ai_enhancement_credits)
```

### 8.2 Metrics (counted, not Prometheus)

- `mcp_servers.ai_enhancement_cost_cents` — total per server
- `users.ai_enhancement_credits` — free tier remaining
- We can derive: total AI cost across all servers, average cost per server, free-tier exhaustion rate

### 8.3 Sentry

- `anthropic.APIError` automatically captured
- Add breadcrumb on each AI call: `{category: "ai_engine", message: "Enhanced tool X with score Y", level: "info"}`
- Don't capture `AIDescriptionError` for individual tool failures (expected sometimes); DO capture if all tools fail

---

## 9. Edge Cases & Failure Modes

| Edge case | Detection | Response |
|---|---|---|
| User has 0 AI credits (free tier) | Credit check in endpoint | Return 402 with `error_code=OUT_OF_CREDITS`, suggestion: "Upgrade to Pro for unlimited AI enhancements" |
| LLM API returns invalid JSON | JSON parse in `_parse_json_response` | Mark tool as failed, emit SSE `tool_error`, continue with other tools |
| LLM API rate limit (429) | `RateLimitError` from `openai` lib | Tenacity retries 3x with jitter; if all fail, mark all tools failed, status → "error" |
| LLM API key missing | Startup check | App fails to start with clear error |
| Provider not supported (LLM_PROVIDER is invalid) | Config validation at startup | App fails to start with clear error listing supported providers |
| Base URL unreachable | `APIConnectionError` from `openai` lib | Retry; if all fail, mark all tools failed |
| JSON mode not supported by provider | API returns 400 | Set `LLM_JSON_MODE=false`, retry; document as limitation |
| Tool has no parameters | Handle in prompt | AI is told "no parameters"; return_description gets extra weight |
| Tool has no description | Use operation summary as fallback | AI sees a degraded input; output may be lower quality |
| Tool name too long (>64 chars) | OpenAPI spec analyzer should already handle | AI may suggest shorter name |
| User re-runs AI on a tool they already accepted | Snapshot already exists in `original_tools_config` | Restore from snapshot, then re-enhance |
| User on free tier runs AI on 100 tools at once | Credit check sees user has 0 credits | Return 402 immediately |
| Spec has 500+ tools (cost ceiling) | Frontend warning | Show "Enhancing 500 tools will cost ~$6 and take ~30 min. Continue?" |
| All tools fail (e.g., API key wrong) | All tool_enhanced events are `tool_error` | Emit `ai_complete` with `tools_failed=N`, status stays "in_progress", user sees error toast |
| Network disconnect during SSE | EventSource auto-reconnects | Frontend reconnects, re-subscribes, replays from `Last-Event-ID` |
| Concurrent edits (user A and user B editing same server) | Optimistic concurrency | Tools PATCH requires `If-Match: <version>` header (mcp_servers.version) |
| AI enhancement in progress when user deletes server | Delete check in Celery task | Task checks server exists, exits gracefully if not |

---

## 10. Definition of Done

- [ ] `apps/api/pyproject.toml` has `anthropic` and `tenacity`
- [ ] Migration `0002_add_ai_enhancement.py` created and reversible
- [ ] `app/core/anthropic_client.py` implemented with retry
- [ ] `app/core/sse.py` implemented (SSE pub/sub)
- [ ] `app/services/ai_description/prompts.py` implemented with system prompt, user template, few-shot examples
- [ ] `app/services/ai_description/quality_scorer.py` implemented with 4-dimension scoring
- [ ] `app/services/ai_description_engine.py` implemented with Claude API integration
- [ ] `app/services/ai_description/tasks.py` implemented with Celery
- [ ] `app/services/server_builder.py` implemented (orchestrator)
- [ ] `app/schemas/ai_description.py` implemented
- [ ] `app/api/v1/endpoints/build.py` implemented (4 endpoints)
- [ ] All env vars added to `apps/api/.env.example`
- [ ] Backend tests: 35+ tests for F2, all passing
- [ ] Frontend: `components/builder/ai-review-panel.tsx` and related components implemented
- [ ] Frontend: `hooks/use-ai.ts` implemented
- [ ] Frontend: SSE consumption in `useBuildStatusSSE`
- [ ] Playwright E2E: AI review flow passes
- [ ] Manual test: paste a real spec (e.g., Stripe) → AI enhances all ~150 tools → review panel shows 90+ scores on most
- [ ] Manual test: AI enhancement for 12 tools costs <$0.10
- [ ] CI: all checks pass
- [ ] Sentry captures API errors
- [ ] Cost tracking verified end-to-end (`ai_enhancement_cost_cents` updates in DB)

---

## 11. Build Sequence (for AI agents)

### Step 1: Foundation
- [ ] Add deps: `anthropic`, `tenacity` to `apps/api/pyproject.toml`
- [ ] Add env vars to `.env.example`: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `MAX_AI_CREDITS_PER_USER_PER_DAY`
- [ ] Run `uv sync`

### Step 2: Migration
- [ ] Create migration `0002_add_ai_enhancement.py` (4 columns on mcp_servers)
- [ ] Run `alembic upgrade head` and `alembic downgrade -1` to verify

### Step 3: Anthropic client core
- [ ] Create `app/core/anthropic_client.py` with retry
- [ ] Create `tests/test_anthropic_client.py` with 3 tests (happy, retry on 429, no retry on 400)

### Step 4: SSE manager
- [ ] Create `app/core/sse.py` with pub/sub
- [ ] Create `tests/test_sse.py` with 4 tests (publish/subscribe, multiple subscribers, unsubscribed, slow consumer doesn't block)

### Step 5: Prompts
- [ ] Create `app/services/ai_description/prompts.py`
- [ ] Create `app/services/ai_description/few_shot_examples.py`
- [ ] Create `tests/test_ai_prompts.py` with 4 tests

### Step 6: Quality scorer
- [ ] Create `app/services/ai_description/quality_scorer.py`
- [ ] Create `tests/test_quality_scorer.py` with 12 tests covering each dimension

### Step 7: AI engine
- [ ] Create `app/services/ai_description_engine.py` (uses `LLMClient` from `app/core/llm_client.py`)
- [ ] Create `tests/test_ai_description_engine.py` with 8 tests using mocked OpenAI client (which simulates any OpenAI-compatible provider)
- [ ] For tests, mock `AsyncOpenAI.chat.completions.create` to return canned responses
- [ ] Verify the engine uses `response_format={"type": "json_object"}` when `LLM_JSON_MODE=true`
- [ ] Verify cost calculation uses provider-specific pricing

### Step 8: Celery tasks
- [ ] Create `app/services/ai_description/tasks.py`
- [ ] Create `app/services/server_builder.py`
- [ ] Create `tests/test_ai_celery_tasks.py` with 6 tests (eager mode)

### Step 9: Schemas
- [ ] Create `app/schemas/ai_description.py`
- [ ] Add `BuildEvent` to `app/schemas/build.py`

### Step 10: Endpoints
- [ ] Create `app/api/v1/endpoints/build.py` with 4 endpoints (including SSE)
- [ ] Create `tests/test_build_endpoints.py` with 5 tests

### Step 11: Update User model + credits
- [ ] Verify `users.ai_enhancement_credits` field exists (it does, per CURRENT-STATE)
- [ ] Add `UserRepository.decrement_credits(user_id, amount)` method
- [ ] Add tests for credit decrement

### Step 12: Frontend deps (verify F1 installed them)
- [ ] Verify `monaco-editor`, `@monaco-editor/react`, `react-resizable-panels`, `@radix-ui/react-tabs` are in `apps/web/package.json`
- [ ] If not, add them

### Step 13: Frontend types
- [ ] Add to `src/types/api.ts`: `AIQualityScore`, `AIImprovementItem`, `AIEnhancedTool`, `BuildEvent`

### Step 14: Frontend API client
- [ ] Update `src/lib/api.ts` to add `api.servers.enhanceTools`, `enhanceSingleTool`, `acceptTools`

### Step 15: Frontend hooks
- [ ] Create `src/hooks/use-ai.ts` with 4 hooks

### Step 16: Review panel components
- [ ] Create `components/builder/quality-score-badge.tsx`
- [ ] Create `components/builder/quality-score-breakdown.tsx`
- [ ] Create `components/builder/inline-edit-field.tsx`
- [ ] Create `components/builder/description-monaco-editor.tsx`
- [ ] Create `components/builder/improvements-badges.tsx`
- [ ] Create `components/builder/revert-field-button.tsx`
- [ ] Create `components/builder/ai-cost-display.tsx`
- [ ] Create `components/builder/ai-credits-indicator.tsx`
- [ ] Create `components/builder/original-vs-enhanced.tsx`
- [ ] Create `components/builder/ai-review-tool-card.tsx`
- [ ] Create `components/builder/ai-review-panel.tsx` (container)

### Step 17: Wire into server tools page
- [ ] Update `app/(dashboard)/servers/[slug]/tools/page.tsx`
- [ ] Add tabs: "AI Review" (default), "Manual Edit"
- [ ] AI Review tab shows the review panel
- [ ] Manual Edit tab shows Monaco editor for direct tool description editing

### Step 18: Vitest tests
- [ ] Tests for all new components
- [ ] Run `pnpm test` — all pass

### Step 19: Playwright E2E
- [ ] Add `04-ai-review.spec.ts`
- [ ] Add `05-ai-edit-single.spec.ts`
- [ ] Run `pnpm playwright test` — all pass

### Step 20: Update shared types
- [ ] Re-fetch OpenAPI, regenerate `api-types.d.ts`
- [ ] Verify new endpoints appear

### Step 21: Manual end-to-end test
- [ ] Use a real Anthropic API key
- [ ] Run full stack
- [ ] Create a server with a small spec (e.g., petstore, 19 tools)
- [ ] Trigger AI enhancement
- [ ] Verify review panel appears with 90+ scores
- [ ] Accept all
- [ ] Verify tools_config updated
- [ ] Check `ai_enhancement_cost_cents` in DB — should be <$0.20 for 19 tools
- [ ] Check Stripe Sentry (or local) — no errors

### Step 22: Load test
- [ ] Run AI on 100 tools (use a large spec)
- [ ] Verify all complete in <2 minutes (with 5-way parallel)
- [ ] Verify cost is <$1.00 (with prompt caching)

**Total estimated time:** 5-7 days for one engineer.

---

## 12. Open Questions

- **Q1 (P0):** Should the AI enhancement use Sonnet 4.6 or Haiku 4.5 by default? (Decision: Sonnet 4.6 — better quality, prompt caching makes cost ~equal. Haiku as fallback if Sonnet overloaded.)
- **Q2 (P0):** What's the right parallel concurrency for Claude API calls? (Decision: 5 — balances speed vs. rate limit. Configurable via env var `AI_ENHANCEMENT_CONCURRENCY`.)
- **Q3 (P1):** When user clicks "Re-run AI on single tool", should we snapshot the previous AI version? (Decision: yes, store in `ai_enhancement_history` JSONB for v1.1; for v1.0, just overwrite with `last_ai_run_at` timestamp.)
- **Q4 (P1):** Should we A/B test prompt variants? (Decision: not in v1.0. Track in v1.1.)
- **Q5 (P2):** What's the retry strategy for partial failures? (Decision: tools that fail are marked with `ai_enhancement_status = "failed"`, can be retried individually. Don't fail the whole batch.)

---

*This is the core product. See `features/05-FEATURE-MCP-GATEWAY.md` for how the AI-enhanced descriptions are served. See `features/06-FEATURE-SECURITY-SCANNER.md` for the security gate that runs before deploy.*
