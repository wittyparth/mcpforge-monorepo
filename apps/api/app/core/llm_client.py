"""AsyncOpenAI wrapper with retry, pricing, and singleton management.

Provides the LLMClient class for interacting with OpenAI-compatible
providers (DeepSeek, OpenAI, OpenCode Go, etc.) with built-in retry
logic, cost calculation, and a singleton pattern for the underlying
AsyncOpenAI client.
"""

from __future__ import annotations

from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# Cost in cents per 1M tokens (input, output, cache_read, cache_write).
# Source: provider pricing pages. Default pricing is the most expensive
# tier used as a safety ceiling for unknown models.
PROVIDER_PRICING: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {
        "input": 14.0,
        "output": 28.0,
        "cache_read": 1.4,
        "cache_write": 14.0,
    },
    "deepseek-chat": {
        "input": 14.0,
        "output": 28.0,
        "cache_read": 1.4,
        "cache_write": 14.0,
    },
    "gpt-4o": {
        "input": 250.0,
        "output": 1000.0,
        "cache_read": 125.0,
        "cache_write": 250.0,
    },
    "gpt-4o-mini": {
        "input": 15.0,
        "output": 60.0,
        "cache_read": 7.5,
        "cache_write": 15.0,
    },
    "claude-sonnet-4-6": {
        "input": 300.0,
        "output": 1500.0,
        "cache_read": 30.0,
        "cache_write": 300.0,
    },
    "claude-haiku-4-5": {
        "input": 80.0,
        "output": 400.0,
        "cache_read": 8.0,
        "cache_write": 80.0,
    },
}

# Default pricing: claude-sonnet-4-6 level (safest upper bound).
DEFAULT_PRICING: dict[str, float] = {
    "input": 300.0,
    "output": 1500.0,
    "cache_read": 30.0,
    "cache_write": 300.0,
}

_RETRYABLE_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
)


def _retry_before_sleep(retry_state: Any) -> None:
    """Log a warning before each retry attempt."""
    logger.warning(
        "LLM API call failed, retrying",
        attempt=retry_state.attempt_number,
        exception=(
            retry_state.outcome.exception().__class__.__name__
            if retry_state.outcome and retry_state.outcome.exception()
            else "unknown"
        ),
    )


class LLMClient:
    """AsyncOpenAI wrapper with retry, pricing, and singleton management.

    Usage:
        response = await LLMClient.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            system="You are a helpful assistant.",
        )
        cost = LLMClient.calculate_cost_cents(response["usage"], response["model"])
    """

    _client: AsyncOpenAI | None = None

    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        """Get or create the singleton AsyncOpenAI client.

        Creates the client with zero SDK-level retries since tenacity
        handles retry logic with proper exponential backoff.
        """
        if cls._client is None:
            cls._client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
                max_retries=0,
            )
        return cls._client

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton client (useful for testing).

        Call between tests to ensure a fresh client is created.
        """
        cls._client = None

    @classmethod
    @retry(
        stop=stop_after_attempt(settings.LLM_RETRY_ATTEMPTS),
        wait=wait_random_exponential(min=1, max=30),
        retry=retry_if_exception_type(_RETRYABLE_ERRORS),
        reraise=True,
        before_sleep=_retry_before_sleep,
    )
    async def chat_completion(
        cls,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request with automatic retry.

        Args:
            messages: List of message dicts with ``role`` and ``content``.
            system: Optional system prompt (prepended as a system message).
            max_tokens: Maximum tokens in the response (defaults to
                ``settings.LLM_MAX_TOKENS``).
            temperature: Sampling temperature (defaults to
                ``settings.LLM_TEMPERATURE``).
            response_format: Optional response format dict, e.g.
                ``{"type": "json_object"}``.
            extra_body: Additional body parameters for provider-specific
                features (e.g. ``{"prefix": True}`` for DeepSeek prefix
                caching).

        Returns:
            Dict with keys:
            - ``content``: The response text.
            - ``usage``: Token usage dict (prompt_tokens, completion_tokens,
              total_tokens, prompt_tokens_details).
            - ``model``: The model name used.
            - ``provider``: The provider identifier.
            - ``finish_reason``: The finish reason string.
        """
        client = cls.get_client()

        merged_messages: list[dict[str, str]] = []
        if system:
            merged_messages.append({"role": "system", "content": system})
        merged_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": settings.LLM_MODEL,
            "messages": merged_messages,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        if extra_body is not None:
            kwargs["extra_body"] = extra_body

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        usage_dict: dict[str, Any] = {}
        if response.usage is not None:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            if response.usage.prompt_tokens_details is not None:
                usage_dict["prompt_tokens_details"] = {
                    "cached_tokens": response.usage.prompt_tokens_details.cached_tokens or 0,
                }

        return {
            "content": choice.message.content or "",
            "usage": usage_dict,
            "model": response.model,
            "provider": settings.LLM_PROVIDER,
            "finish_reason": choice.finish_reason or "stop",
        }

    @classmethod
    def calculate_cost_cents(cls, usage: dict[str, Any], model: str = "") -> float:
        """Calculate the cost of a completion in cents.

        Accounts for cached prompt tokens (prompt_tokens_details.cached_tokens)
        which are billed at the cache_read rate.

        Args:
            usage: The usage dict from a ``chat_completion`` response.
            model: The model name used. Defaults to ``settings.LLM_MODEL``
                if empty.

        Returns:
            Cost in cents (rounded to 6 decimal places).
        """
        if not usage:
            return 0.0

        resolved_model = model or settings.LLM_MODEL
        pricing = PROVIDER_PRICING.get(resolved_model, DEFAULT_PRICING)

        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)

        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_tokens: int = 0
        if isinstance(prompt_details, dict):
            cached_tokens = int(prompt_details.get("cached_tokens", 0) or 0)
        uncached_prompt = max(0, prompt_tokens - cached_tokens)

        raw_input = uncached_prompt * pricing["input"] + cached_tokens * pricing["cache_read"]
        input_cost = raw_input / 1_000_000
        output_cost = (completion_tokens * pricing["output"]) / 1_000_000

        result = input_cost + output_cost
        return float(round(result, 6))
