"""Rate limiter for MCP gateway — plan-based rate limiting with Redis Lua scripting.

Uses a Lua script for atomic check-and-increment operations against Redis,
ensuring race-condition-free rate limit enforcement across multiple gateway
instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

from app.core.logging import get_logger

logger = get_logger(__name__)

# Rate limit definitions per plan: hourly and monthly call quotas.
RATE_LIMITS: dict[str, dict[str, int]] = {
    "free": {"hour": 60, "month": 500},
    "pro": {"hour": 1000, "month": 10000},
    "team": {"hour": 10000, "month": 100000},
}

# Lua script for atomic rate limit check-and-increment.
#
# KEYS[1] — hour key   (rl:{server_id}:hour)
# KEYS[2] — month key  (rl:{server_id}:month)
# ARGV[1] — hour limit
# ARGV[2] — month limit
#
# Returns:
#   {1, "ok", hour_count, month_count}  — request allowed
#   {0, "hour"|"month", current, limit}  — request denied
_RATE_LIMIT_LUA = """
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


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is permitted under current rate limits.
        reason: Short reason string — ``"ok"``, ``"hour"``, or ``"month"``.
        current: Current count for the relevant window (hour or month).
        limit: The limit that was checked (hour or month, matching ``reason``).
    """

    allowed: bool
    reason: str
    current: int
    limit: int


class GatewayRateLimiter:
    """Plan-based rate limiter for MCP gateway tool calls.

    Uses a Redis Lua script for atomic check-and-increment operations.
    Each server has per-hour and per-month counters tracked by Redis keys.

    The limiter does **not** depend on FastAPI dependency injection;
    it takes a ``redis.asyncio.Redis`` instance directly as a constructor
    argument.
    """

    def __init__(self, redis_client: Redis) -> None:
        """Initialise the rate limiter.

        Args:
            redis_client: A ``redis.asyncio.Redis`` instance used for rate
                limit counter storage.
        """
        self._redis: Redis = redis_client

    async def check(self, server_id: UUID, plan: str) -> RateLimitResult:
        """Check and increment rate limits for a server call.

        Args:
            server_id: The UUID of the MCP server making the call.
            plan: The billing plan of the server owner (``"free"``,
                ``"pro"``, ``"team"``).  Defaults to ``"free"`` if the plan
                is not recognised.

        Returns:
            A ``RateLimitResult`` indicating whether the call is allowed.
        """
        limits = RATE_LIMITS.get(plan, RATE_LIMITS["free"])
        hour_key = f"rl:{server_id}:hour"
        month_key = f"rl:{server_id}:month"

        try:
            # type ignore: the redis-py async stub says eval()->str|Awaitable[str]
            # but in practice with the async client it is always awaitable.
            result = await self._redis.eval(  # type: ignore[reportGeneralTypeIssues]
                _RATE_LIMIT_LUA,
                2,  # number of Redis keys passed
                hour_key,
                month_key,
                str(limits["hour"]),
                str(limits["month"]),
            )
        except Exception:
            logger.exception("rate limit check failed, allowing request by default")
            return RateLimitResult(
                allowed=True,
                reason="error_default_allow",
                current=0,
                limit=limits["hour"],
            )

        allowed = bool(result[0])
        reason = str(result[1])

        if allowed:
            hour_count = int(result[2])
            return RateLimitResult(
                allowed=True,
                reason="ok",
                current=hour_count,
                limit=limits["hour"],
            )

        current = int(result[2])
        limit = int(result[3])
        return RateLimitResult(
            allowed=False,
            reason=reason,
            current=current,
            limit=limit,
        )
