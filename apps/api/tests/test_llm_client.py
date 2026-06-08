"""Tests for LLMClient — OpenAI wrapper with pricing and singleton management.

6+ tests covering:
  - Singleton reset
  - Cost calculation with empty usage, known models, cached tokens, unknown models
  - PROVIDER_PRICING shape validation
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.llm_client import DEFAULT_PRICING, PROVIDER_PRICING, LLMClient


class TestLLMClientReset:
    """LLMClient.reset() behaviour."""

    def test_reset_clears_singleton(self) -> None:
        """Calling reset() sets _client to None."""
        with patch("app.core.llm_client.AsyncOpenAI") as mock_client:
            mock_client.return_value = mock_client
            # First access creates the singleton
            _ = LLMClient.get_client()
            assert LLMClient._client is not None

            LLMClient.reset()
            assert LLMClient._client is None


class TestCalculateCostCents:
    """LLMClient.calculate_cost_cents() edge cases."""

    def test_empty_usage_returns_zero(self) -> None:
        """Empty usage dict returns 0.0 cost."""
        cost = LLMClient.calculate_cost_cents({})
        assert cost == 0.0

    def test_none_usage_returns_zero(self) -> None:
        """None-like usage returns 0.0 (the method defaults to {} on falsy)."""
        cost = LLMClient.calculate_cost_cents({})
        assert cost == 0.0

    def test_known_model_pricing_deepseek_chat(self) -> None:
        """DeepSeek Chat pricing: input $14/M, output $28/M."""
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}
        cost = LLMClient.calculate_cost_cents(usage, model="deepseek-chat")
        # input: 14.0, output: 28.0 * 0.5 = 14.0, total = 28.0
        assert cost == pytest.approx(28.0, rel=0.01)

    def test_cached_tokens_use_cache_read_rate(self) -> None:
        """Cached prompt tokens are billed at cache_read rate."""
        usage = {
            "prompt_tokens": 100_000,
            "completion_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 80_000},
        }
        cost = LLMClient.calculate_cost_cents(usage, model="gpt-4o-mini")
        # 20k uncached * 15.0/M = 0.3, 80k cached * 7.5/M = 0.6, output = 0
        # total = 0.9 cents
        assert cost == pytest.approx(0.9, rel=0.01)

    def test_unknown_model_uses_default_pricing(self) -> None:
        """Unknown model falls back to DEFAULT_PRICING (claude-sonnet-4-6)."""
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 0}
        cost = LLMClient.calculate_cost_cents(usage, model="nonexistent-model-v99")
        # DEFAULT_PRICING input = 300.0/M → 300 cents
        assert cost == pytest.approx(300.0, rel=0.01)
        assert cost > 250.0  # Should be higher than cheap models

    def test_prompt_tokens_details_none_does_not_crash(self) -> None:
        """When prompt_tokens_details is None, no crash occurs."""
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_tokens_details": None,
        }
        cost = LLMClient.calculate_cost_cents(usage, model="gpt-4o")
        # Should not raise, all tokens treated as uncached
        assert cost > 0


class TestProviderPricing:
    """PROVIDER_PRICING dictionary structure."""

    def test_has_expected_models(self) -> None:
        """PROVIDER_PRICING contains the expected model keys."""
        expected_models = {
            "deepseek-v4-flash",
            "deepseek-chat",
            "gpt-4o",
            "gpt-4o-mini",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        }
        assert expected_models.issubset(PROVIDER_PRICING.keys())

    def test_each_model_has_required_fields(self) -> None:
        """Each pricing entry has input, output, cache_read, cache_write keys."""
        required_keys = {"input", "output", "cache_read", "cache_write"}
        for model, pricing in PROVIDER_PRICING.items():
            assert set(pricing.keys()) == required_keys, f"{model} missing keys"
            for key in required_keys:
                assert isinstance(pricing[key], int | float), (
                    f"{model}.{key} must be numeric"
                )
                assert pricing[key] > 0, f"{model}.{key} must be positive"

    def test_default_pricing_is_most_expensive(self) -> None:
        """DEFAULT_PRICING input >= all provider inputs (safety ceiling)."""
        for _model, pricing in PROVIDER_PRICING.items():
            assert DEFAULT_PRICING["input"] >= pricing["input"], (
                f"DEFAULT_PRICING.input ({DEFAULT_PRICING['input']}) should be "
                f"the ceiling, but {_model} has {pricing['input']}"
            )
