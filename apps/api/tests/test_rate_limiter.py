"""Tests for the MCP gateway rate limiter.

Covers plan-based rate limits (free, pro, team), atomic Lua-script-backed
check-and-increment, and edge cases (unknown plan → free default).
Since ``fakeredis`` does not support ``EVAL``, the ``redis.eval`` method is
monkeypatched with an ``AsyncMock`` in each test.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import fakeredis
import pytest

from app.gateway.rate_limiter import (
    RATE_LIMITS,
    GatewayRateLimiter,
)


@pytest.fixture
def server_id() -> UUID:
    """A deterministic server UUID for reproducible tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def free_limits() -> dict[str, int]:
    """Shortcut to the free-plan rate limits."""
    return RATE_LIMITS["free"]


async def _make_limiter(
    eval_return: list,
) -> tuple[GatewayRateLimiter, fakeredis.FakeAsyncRedis]:
    """Create a ``GatewayRateLimiter`` with a monkeypatched ``eval``.

    Args:
        eval_return: The value that ``redis.eval`` should return.

    Returns:
        A ``(limiter, redis)`` tuple.
    """
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    redis.eval = AsyncMock(return_value=eval_return)
    return GatewayRateLimiter(redis), redis


# ---------------------------------------------------------------------------
# First request allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_request_allowed(
    server_id: UUID,
    free_limits: dict[str, int],
) -> None:
    """A fresh server should have its first call allowed."""
    limiter, _ = await _make_limiter([1, "ok", 1, free_limits["hour"]])

    result = await limiter.check(server_id, "free")

    assert result.allowed is True
    assert result.reason == "ok"
    assert result.current == 1
    assert result.limit == free_limits["hour"]


# ---------------------------------------------------------------------------
# Hour limit hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hour_limit_hit(server_id: UUID) -> None:
    """Request should be denied when the hourly limit is reached."""
    free_limits = RATE_LIMITS["free"]
    limiter, _ = await _make_limiter(
        [0, "hour", free_limits["hour"], free_limits["hour"]],
    )

    result = await limiter.check(server_id, "free")

    assert result.allowed is False
    assert result.reason == "hour"
    assert result.current == free_limits["hour"]
    assert result.limit == free_limits["hour"]


# ---------------------------------------------------------------------------
# Month limit hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_month_limit_hit(server_id: UUID) -> None:
    """Request should be denied when the monthly limit is reached."""
    free_limits = RATE_LIMITS["free"]
    limiter, _ = await _make_limiter(
        [0, "month", free_limits["month"], free_limits["month"]],
    )

    result = await limiter.check(server_id, "free")

    assert result.allowed is False
    assert result.reason == "month"
    assert result.current == free_limits["month"]
    assert result.limit == free_limits["month"]


# ---------------------------------------------------------------------------
# Free plan limits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_plan_limits(server_id: UUID) -> None:
    """Free plan should have the correct hourly and monthly limits."""
    free_limits = RATE_LIMITS["free"]
    limiter, _ = await _make_limiter([1, "ok", 1, free_limits["hour"]])

    result = await limiter.check(server_id, "free")

    assert result.allowed is True
    assert result.limit == free_limits["hour"]

    # Hour limit denied
    limiter2, _ = await _make_limiter(
        [0, "hour", free_limits["hour"], free_limits["hour"]],
    )
    result2 = await limiter2.check(server_id, "free")

    assert result2.allowed is False
    assert result2.reason == "hour"
    assert result2.current == free_limits["hour"]
    assert result2.limit == free_limits["hour"]

    # Month limit denied
    limiter3, _ = await _make_limiter(
        [0, "month", free_limits["month"], free_limits["month"]],
    )
    result3 = await limiter3.check(server_id, "free")

    assert result3.allowed is False
    assert result3.reason == "month"
    assert result3.current == free_limits["month"]
    assert result3.limit == free_limits["month"]


# ---------------------------------------------------------------------------
# Pro plan limits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pro_plan_limits(server_id: UUID) -> None:
    """Pro plan should have limits higher than free."""
    free_limits = RATE_LIMITS["free"]
    pro_limits = RATE_LIMITS["pro"]
    assert pro_limits["hour"] > free_limits["hour"]
    assert pro_limits["month"] > free_limits["month"]

    limiter, _ = await _make_limiter([1, "ok", 1, pro_limits["hour"]])

    result = await limiter.check(server_id, "pro")

    assert result.allowed is True
    assert result.limit == pro_limits["hour"]


# ---------------------------------------------------------------------------
# Unknown plan defaults to free
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_plan_defaults_to_free(server_id: UUID) -> None:
    """An unrecognised plan name should fall back to free-tier limits."""
    free_limits = RATE_LIMITS["free"]
    limiter, _ = await _make_limiter([1, "ok", 1, free_limits["hour"]])

    result = await limiter.check(server_id, "unknown_plan")

    assert result.allowed is True
    assert result.limit == free_limits["hour"]


# ---------------------------------------------------------------------------
# Redis error — default allow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_error_default_allow(server_id: UUID) -> None:
    """When Redis itself raises (e.g. connection error), the limiter should
    default to allowing the request."""
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)

    async def _raise_error(*args: object, **kwargs: object) -> list:
        msg = "mock connection error"
        raise ConnectionError(msg)

    redis.eval = AsyncMock(side_effect=_raise_error)
    limiter = GatewayRateLimiter(redis)

    result = await limiter.check(server_id, "free")

    assert result.allowed is True
    assert result.reason == "error_default_allow"
    assert result.current == 0
    assert result.limit == RATE_LIMITS["free"]["hour"]
