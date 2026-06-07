# LLM Providers — Reference (OpenAI-Compatible, Multi-Provider)

> **For AI agents:** Reference for the AI Description Engine (F2). Use this when building prompts, configuring providers, switching models via .env, or troubleshooting LLM calls.
>
> **MCPForge constraint:** We use the **OpenAI-compatible Chat Completions protocol** for all LLM providers, allowing us to switch providers (DeepSeek, OpenAI, Anthropic via proxy, OpenCode Go, OpenRouter, self-hosted) via environment variables — no code changes required.

---

## 1. Primary Configuration

**Default (recommended for v1.0):**
```
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=<your-deepseek-key>
```

The OpenAI Python package (`openai>=1.50`) is used with `base_url` overridden to the provider's endpoint.

## 2. Supported Providers

### 2.1 DeepSeek (Primary)
- **Base URL:** `https://api.deepseek.com/v1`
- **Models:** `deepseek-v4-flash` (primary, fast & cheap), `deepseek-chat` (similar), `deepseek-coder`, `deepseek-reasoner`
- **Auth:** API key
- **JSON mode:** Supported (`response_format={"type": "json_object"}`)
- **Prompt caching:** Automatic on repeated prefixes (free)
- **Pricing (deepseek-v4-flash):** ~$0.14/MTok input, ~$0.28/MTok output (3-4x cheaper than Anthropic/OpenAI)
- **Signup:** https://platform.deepseek.com

### 2.2 OpenAI
- **Base URL:** `https://api.openai.com/v1`
- **Models:** `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `o1`, `o1-mini`, `o3-mini`
- **Auth:** API key
- **JSON mode:** Supported
- **Prompt caching:** Automatic on prefixes (since 2024, 50% discount on cached reads)
- **Pricing (gpt-4o):** $2.50/MTok input, $10/MTok output
- **Pricing (gpt-4o-mini):** $0.15/MTok input, $0.60/MTok output

### 2.3 Anthropic (via OpenAI-compatible proxy)
- **Base URL:** Depends on proxy
- **Proxies:** LiteLLM, anthropic-sdk-openai, Portkey, Cloudflare AI Gateway
- **Models:** `claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-opus-4-8`
- **Auth:** Anthropic API key (configured in the proxy)
- **JSON mode:** Supported
- **Prompt caching:** Explicit via `cache_control` in `extra_body`
- **Pricing (claude-sonnet-4-6):** $3/MTok input, $15/MTok output (cache reads: $0.30, 90% discount)

### 2.4 OpenCode Go
- **Base URL:** Check provider docs (likely `https://api.opencode-go.com/v1` or similar)
- **Auth:** API key
- **JSON mode:** Verify with provider
- **Pricing:** Per OpenCode Go

### 2.5 OpenRouter
- **Base URL:** `https://openrouter.ai/api/v1`
- **Auth:** Single API key, access to many models
- **Models:** Any (e.g., `anthropic/claude-sonnet-4-6`, `deepseek/deepseek-chat`, `openai/gpt-4o`)
- **JSON mode:** Supported
- **Pricing:** Per model (OpenRouter adds small markup)

### 2.6 Custom (Self-Hosted)
- **Base URL:** Your inference server (vLLM, TGI, llama.cpp server, etc.)
- **Models:** Whatever your server serves
- **Auth:** Per server (often none for local dev)
- **Must implement:** OpenAI Chat Completions protocol

## 3. The OpenAI Python Client

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key="sk-...",  # or "sk-deepseek-..." for DeepSeek
    base_url="https://api.deepseek.com/v1",  # the key to provider switching
    max_retries=0,  # we handle retries
    timeout=60.0,
)

response = await client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
    ],
    max_tokens=2000,
    temperature=0.0,
    response_format={"type": "json_object"},  # for structured output
    # extra_body={"cache_control": {"type": "ephemeral"}},  # Anthropic via proxy
)
```

**Response shape:**
```python
response.choices[0].message.content  # the text
response.choices[0].finish_reason  # "stop" | "length" | "tool_calls"
response.usage.prompt_tokens  # input
response.usage.completion_tokens  # output
response.usage.total_tokens
response.model  # actual model used (may differ from requested)
```

## 4. Structured JSON Output

### Approach 1: JSON mode (preferred)
```python
response = await client.chat.completions.create(
    model=...,
    messages=[...],
    response_format={"type": "json_object"},
)
# response.choices[0].message.content is guaranteed valid JSON
```

Supported by: OpenAI (gpt-4o, gpt-4-turbo, gpt-3.5-turbo), DeepSeek, OpenRouter, most providers.

**Important:** When using JSON mode, you MUST include the word "JSON" in the system or user prompt, or the API may return an error. We always include it.

### Approach 2: Prompt engineering (fallback)
If a provider doesn't support JSON mode:
```python
system = """Output ONLY valid JSON in the format:
{"tool_name": "...", "tool_description": "..."}
No prose, no markdown, no code fences."""

response = await client.chat.completions.create(
    model=...,
    messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
)
# Parse response with robust JSON extraction (strip code fences if present)
```

**MCPForge:** Uses Approach 1 with `LLM_JSON_MODE=true` default; falls back to Approach 2 if disabled.

## 5. Prompt Caching (Provider-Agnostic)

### 5.1 DeepSeek: Automatic
- Repeated prefixes are automatically cached
- No API call changes needed
- Cached reads are free (no separate charge)
- Cache TTL: ~5 min (handled by DeepSeek's backend)

### 5.2 OpenAI: Automatic
- Cache hits when prefix matches a previous request
- Cached reads are 50% off input price
- 128 token minimum

### 5.3 Anthropic (via proxy): Explicit
```python
response = await client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[
        {"role": "system", "content": "long system prompt"},
        {"role": "user", "content": "user query"},
    ],
    extra_body={
        "cache_control": {"type": "ephemeral"}  # 5-min cache
    },
)
```

### 5.4 MCPForge caching strategy
- System prompt + spec context (~5K tokens) is the cacheable prefix
- Sent as the first user message (or system) to maximize prefix matching
- Provider-agnostic: works whether the provider supports caching or not
- No code changes needed when switching providers

## 6. Error Handling

```python
import openai
from openai import (
    APIError, APIConnectionError, APITimeoutError, RateLimitError,
    BadRequestError, AuthenticationError, NotFoundError, PermissionDeniedError,
)

try:
    response = await client.chat.completions.create(...)
except RateLimitError as e:
    # 429 — back off and retry
    wait = int(e.response.headers.get('retry-after', 5)) if e.response else 5
    await asyncio.sleep(wait)
    # retry
except APIConnectionError as e:
    # Network issue
    await asyncio.sleep(1)
    # retry
except APITimeoutError as e:
    # Request took too long
    await asyncio.sleep(1)
    # retry
except BadRequestError as e:
    # 400 — don't retry (provider rejected request; check schema, params)
    logger.error("llm_bad_request", error=str(e))
    raise
except AuthenticationError as e:
    # 401 — API key invalid
    logger.error("llm_auth_failed", provider=settings.LLM_PROVIDER)
    raise
except PermissionDeniedError as e:
    # 403 — API key doesn't have access to this model
    logger.error("llm_permission_denied", model=settings.LLM_MODEL)
    raise
except NotFoundError as e:
    # 404 — model not found
    logger.error("llm_model_not_found", model=settings.LLM_MODEL)
    raise
except APIError as e:
    # Other 5xx
    if e.status_code and e.status_code >= 500:
        await asyncio.sleep(5)
        # retry
    else:
        raise
```

**With Tenacity:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    reraise=True,
)
async def call_llm(messages, **kwargs):
    return await client.chat.completions.create(model=..., messages=messages, **kwargs)
```

## 7. Parallel API Calls

```python
import asyncio

async def enhance_tool(tool):
    response = await client.chat.completions.create(...)
    return parse_response(response)

results = await asyncio.gather(*[enhance_tool(t) for t in tools])
```

**Concurrency control** (avoid rate limits):
```python
sem = asyncio.Semaphore(5)  # max 5 concurrent

async def enhance_with_semaphore(tool):
    async with sem:
        return await enhance_tool(tool)

results = await asyncio.gather(*[enhance_with_semaphore(t) for t in tools])
```

**MCPForge default:** 5 concurrent LLM calls per server build (configurable).

## 8. Pricing Table (in cents per 1M tokens)

| Model | Input | Output | Cache Read | Cache Write | Source |
|---|---|---|---|---|---|
| deepseek-v4-flash | 14.0 | 28.0 | 1.4 | 14.0 | Primary; 3-4x cheaper |
| deepseek-chat | 14.0 | 28.0 | 1.4 | 14.0 | |
| gpt-4o | 250.0 | 1000.0 | 125.0 | 0.0 | OpenAI |
| gpt-4o-mini | 15.0 | 60.0 | 7.5 | 0.0 | OpenAI |
| claude-sonnet-4-6 | 300.0 | 1500.0 | 30.0 | 375.0 | Anthropic |
| claude-haiku-4-5 | 80.0 | 400.0 | 8.0 | 100.0 | Anthropic |
| claude-opus-4-8 | 1500.0 | 7500.0 | 150.0 | 1875.0 | Anthropic (premium) |
| o1 | 1500.0 | 6000.0 | 750.0 | 0.0 | OpenAI reasoning |

**Update this table** when prices change. New models default to `{input: 100, output: 300, cache_read: 10, cache_write: 100}` (a safe overestimate that we can correct).

## 9. Cost Example: MCPForge AI Engine

**15-tool server, DeepSeek primary, with prompt caching:**

| Component | Cost (DeepSeek) | Cost (Sonnet 4.6) | Cost (GPT-4o) |
|---|---|---|---|
| System prompt (cache write, 5K tokens) | $0.0007 | $0.019 | $0.0125 |
| Per tool (cache reads + output) | $0.004 | $0.012 | $0.013 |
| **15-tool server** | **~$0.06** | **~$0.20** | **~$0.21** |
| **1,500 enhancements/mo** | **~$30** | **~$100** | **~$105** |

DeepSeek is **3x cheaper** than Anthropic/OpenAI for this workload.

## 10. Provider Switching (No Code Change)

To switch from DeepSeek to OpenAI mid-deployment:

**Method 1: Update Render env vars + redeploy**
```bash
# In Render dashboard, change:
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
# Trigger manual deploy
```

**Method 2: Hot reload via admin endpoint (v1.1)**
```bash
curl -X POST https://api.mcpforge.io/api/v1/admin/llm-config \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-..."}'
# LLMClient singleton resets, next call uses new config
```

## 11. Prompt Engineering (Provider-Agnostic)

These principles work across all providers.

### 11.1 Be explicit
- ❌ "Can you suggest changes"
- ✅ "Rewrite this tool description to score 90+ on the 4 quality dimensions"

### 11.2 Use XML tags for structure
```xml
<instructions>You are an AI description engineer.</instructions>
<context>This is a payment API.</context>
<examples>
  <example>
    <input>{"name": "get_user", "description": "Get user"}</input>
    <output>Retrieve user by ID...</output>
  </example>
</examples>
```

### 11.3 Few-shot examples dramatically improve quality
MCPForge includes 2-3 examples per prompt.

### 11.4 Specify output format precisely
```
Output ONLY valid JSON in this exact format:
{"tool_name": "...", "tool_description": "...", "parameters": [...]}
No prose, no markdown, no code fences.
```

### 11.5 Use temperature=0.0 for deterministic JSON output

### 11.6 Place longer content (examples, schemas) at the END
Most models attend more to recent content.

## 12. Tool Description Pattern (from arxiv 2602.18914)

```
<tool name="search_groups">
  USE THIS WHEN you know a group name and need its ID.
  Performs a fuzzy search across all groups and returns matching results.

  Parameters:
  - query (required, string): The group name to search for (min 2 chars)

  Returns: JSON array of {id, name, leader} objects
  - Returns empty array if no matches
  - Throws on network error — retry if transient

  This tool is READ-ONLY (readOnlyHint=True)
</tool>
```

Key patterns from production servers:
1. "USE THIS WHEN" / "DO NOT USE FOR" — explicit trigger
2. `readOnlyHint` — prevents destructive warnings
3. Return format + error conditions
4. Keep under 200 tokens per description

## 13. MCPForge-Specific Patterns

### 13.1 AI Description Engine Prompt Structure
- System: defines the 4-dimension quality framework
- User message 1: spec context (cacheable)
- User message 2: the tool spec + sibling tools + few-shot examples
- Output: structured JSON (validated)

### 13.2 Quality Scoring
Uses regex/heuristic scoring on the 4 dimensions, NOT LLM self-scoring (LLM self-scoring is unreliable).

### 13.3 Cost Optimization
- Default to DeepSeek (cheapest)
- Allow per-server model override (Pro tier)
- Cache the spec prefix (DeepSeek auto, OpenAI auto, Anthropic explicit)
- Batch API for non-urgent re-runs (50% discount) — v1.1

## 14. Testing Patterns

### 14.1 Mock the OpenAI client
```python
from unittest.mock import AsyncMock, patch

@patch("app.core.llm_client.AsyncOpenAI")
async def test_enhance_tool(mock_openai_class):
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    
    # Mock the chat completion response
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = '{"tool_name": "...", "tool_description": "..."}'
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage.prompt_tokens = 1500
    mock_response.usage.completion_tokens = 500
    mock_response.usage.total_tokens = 2000
    mock_response.model = "deepseek-v4-flash"
    
    mock_client.chat.completions.create.return_value = mock_response
    
    # Run test
    result = await enhance_tool(tool, all_tools, spec_context)
    assert result["enhanced_description"] == "..."
```

### 14.2 Test with real LLM (integration)
For CI, optionally test against a real DeepSeek API:
```python
@pytest.mark.integration
async def test_real_deepseek_call():
    settings.LLM_API_KEY = os.environ["DEEPSEEK_API_KEY_TEST"]
    LLMClient.reset()
    result = await LLMClient.chat_completion(
        messages=[{"role": "user", "content": "What is 2+2?"}],
        max_tokens=10,
    )
    assert "4" in result["content"]
```

## 15. Fallback Strategy

If primary provider is overloaded, fall back to a secondary:

```python
async def chat_completion_with_fallback(messages, **kwargs):
    providers = [
        ("deepseek", "https://api.deepseek.com/v1", "deepseek-v4-flash", settings.LLM_API_KEY),
        ("openai", "https://api.openai.com/v1", "gpt-4o-mini", settings.LLM_API_KEY_FALLBACK),
    ]
    
    last_error = None
    for provider, base_url, model, api_key in providers:
        if not api_key:
            continue
        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30)
            return await client.chat.completions.create(model=model, messages=messages, **kwargs)
        except (RateLimitError, APIConnectionError, APITimeoutError) as e:
            last_error = e
            continue
    
    raise last_error
```

(MCPForge v1.0 uses single provider; v1.1 can add fallback.)

## 16. References

- **OpenAI API reference:** https://platform.openai.com/docs/api-reference/chat
- **OpenAI Python SDK:** https://github.com/openai/openai-python
- **DeepSeek API docs:** https://platform.deepseek.com/api-docs/
- **OpenRouter API:** https://openrouter.ai/docs
- **LiteLLM (Anthropic proxy):** https://docs.litellm.ai/
- **Anthropic OpenAI compatibility:** https://docs.anthropic.com/en/api/openai-sdk
- **OpenAI prompt engineering:** https://platform.openai.com/docs/guides/prompt-engineering
- **Anthropic prompt engineering:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview
- **Anthropic SDK on OpenAI:** https://github.com/anthropics/anthropic-sdk-openai
