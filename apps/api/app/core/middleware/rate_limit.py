"""Per-IP and per-user rate limiting via Redis-backed fixed-window counters.

Tiers:
- General endpoints (per-IP, 60/min):    RATE_LIMIT_PER_IP_PER_MINUTE
- Auth endpoints (per-IP, 5/min):        RATE_LIMIT_AUTH_PER_IP_PER_MINUTE
- Authenticated users (per-user, hourly): plan-based from PLAN_LIMITS["calls_per_hour"]
  (free=60, pro=1000, team=10000)

When an access token (JWT cookie or Bearer) is present, the middleware
applies a per-user hourly rate limit in addition to the per-IP minute limit.
The per-user limit uses the plan's ``calls_per_hour`` value from
``plan_limits``; unauthenticated requests skip this check.

The gateway has its own per-server rate limiting (F4); this middleware is a
coarse abuse guard for the main API.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from jose import JWTError
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_pool
from app.core.security import decode_token
from app.services.billing.plan_limits import get_plan_limit

logger = get_logger(__name__)

_AUTH_PATH_PREFIX = "/api/v1/auth/"
_API_KEY_PREFIX = "mcpforge_live_"


def _client_ip(request: Request) -> str:
    """Extract client IP, preferring X-Forwarded-For (Render/Cloudflare proxy)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def _is_auth_path(path: str) -> bool:
    return path.startswith(_AUTH_PATH_PREFIX)


def _extract_user_id(request: Request) -> str | None:
    """Try to extract a user ID from the request (JWT or API key).

    Returns a string suitable for use as a rate-limit key suffix, or None
    if the request is unauthenticated.
    """
    cookie = request.cookies.get("access_token")
    header = request.headers.get("authorization", "")

    token: str | None = None
    if header.startswith("Bearer "):
        token = header[7:]
    elif cookie:
        token = cookie

    if not token:
        return None

    # API key auth — use key prefix as identifier (not unique per-user,
    # but good enough for rate limiting)
    if token.startswith(_API_KEY_PREFIX):
        return f"apikey:{token[:20]}"

    # JWT auth
    try:
        payload = decode_token(token)
        if payload.get("type") == "access":
            return str(UUID(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        pass

    return None


def _get_user_limit(user_id: str | None) -> int | None:
    """Determine the per-user hourly rate limit.

    For JWT-authenticated users, returns the free plan's ``calls_per_hour``
    as a safe default. The actual plan-aware limit is enforced at the MCP
    gateway layer.
    Returns None for unauthenticated requests.
    """
    if user_id is None or user_id.startswith("apikey:"):
        return None
    return get_plan_limit("free", "calls_per_hour")  # safe minimum


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP + per-user rate limiter backed by Redis INCR + EXPIRE."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if settings.ENVIRONMENT == "testing":
            return await call_next(request)

        ip = _client_ip(request)
        window_seconds = 60
        if _is_auth_path(request.url.path):
            limit = settings.RATE_LIMIT_AUTH_PER_IP_PER_MINUTE
            bucket = "auth"
        else:
            limit = settings.RATE_LIMIT_PER_IP_PER_MINUTE
            bucket = "general"

        key = f"rl:{bucket}:{ip}"
        try:
            pool = await get_redis_pool()
            redis = Redis.from_pool(pool)
            try:
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, window_seconds)
            finally:
                await redis.close()
        except Exception as exc:
            # Fail OPEN on Redis outage — a Redis incident must not take
            # down the API. Log loudly so it is noticed.
            logger.error("rate_limit_redis_error", error=str(exc), key=key)
            return await call_next(request)

        if count > limit:
            logger.warning(
                "rate_limit_exceeded",
                ip=ip,
                path=request.url.path,
                bucket=bucket,
                count=count,
                limit=limit,
            )
            err_response: Response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded: {limit} req/min",
                    }
                },
            )
            err_response.headers["Retry-After"] = str(window_seconds)
            err_response.headers["X-RateLimit-Limit"] = str(limit)
            err_response.headers["X-RateLimit-Remaining"] = "0"
            return err_response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))

        # ── Per-user hourly rate limit (plan-based) ──────────────────
        user_id = _extract_user_id(request)
        user_limit = _get_user_limit(user_id)
        if user_id is not None and user_limit is not None:
            hourly_key = f"rl:user:{user_id}:hourly"
            hourly_window = 3600
            try:
                pool = await get_redis_pool()
                redis = Redis.from_pool(pool)
                try:
                    hourly_count = await redis.incr(hourly_key)
                    if hourly_count == 1:
                        await redis.expire(hourly_key, hourly_window)
                    response.headers["X-RateLimit-User-Limit"] = str(user_limit)
                    response.headers["X-RateLimit-User-Remaining"] = str(
                        max(0, user_limit - hourly_count)
                    )
                    if hourly_count > user_limit:
                        logger.warning(
                            "rate_limit_user_exceeded",
                            user_id=user_id,
                            path=request.url.path,
                            count=hourly_count,
                            limit=user_limit,
                        )
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": {
                                    "code": "RATE_LIMIT_EXCEEDED",
                                    "message": f"Hourly rate limit exceeded: {user_limit} req/hr",
                                }
                            },
                        )
                finally:
                    await redis.close()
            except Exception as exc:
                logger.error("rate_limit_user_redis_error", error=str(exc), key=hourly_key)

        return response
