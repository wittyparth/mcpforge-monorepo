"""Per-IP rate limiting via a Redis-backed fixed-window counter.

Two tiers:
- General endpoints:    `RATE_LIMIT_PER_IP_PER_MINUTE` (default 60/min)
- Auth endpoints:       `RATE_LIMIT_AUTH_PER_IP_PER_MINUTE` (default 5/min)

Auth endpoints are matched by path prefix `/api/v1/auth/`. The gateway has
its own per-server rate limiting (F4); this middleware is a coarse abuse
guard for the main API.

A production system would use a sliding window or token bucket; we use
fixed windows (INCR + EXPIRE) for simplicity. The atomic INCR-then-EXPIRE
pattern is race-free in Redis.

The middleware accesses Redis directly via the shared connection pool
(middlewares run outside FastAPI's dependency injection, so we cannot use
`Depends(get_redis)` here).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_pool

logger = get_logger(__name__)

_AUTH_PATH_PREFIX = "/api/v1/auth/"


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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP rate limiter backed by Redis INCR + EXPIRE."""

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
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded: {limit} req/min",
                    }
                },
            )
            response.headers["Retry-After"] = str(window_seconds)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response
