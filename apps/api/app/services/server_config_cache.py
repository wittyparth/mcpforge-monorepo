"""Server configuration cache backed by Redis.

Provides a read-through cache for MCP server configurations. On cache
miss, the config is loaded from the database and stored in Redis with
a 5-minute TTL. On subsequent requests the cached value is returned
without a database round-trip.

Usage::

    from app.core.redis import get_redis_pool
    from redis.asyncio import Redis

    pool = await get_redis_pool()
    redis = Redis.from_pool(pool)
    config = await ServerConfigCache.get(slug="my-server", redis=redis)
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.mcp_server import MCPServer

logger = get_logger(__name__)


class ServerConfigCache:
    """Read-through cache for MCP server configurations.

    All methods are static and require a ``redis: Redis`` instance to be
    passed explicitly. This avoids coupling to FastAPI's ``Depends`` and
    allows the cache to be used from non-HTTP contexts (background tasks,
    MCP gateway handlers, etc.).

    Cache keys:
        - ``server_config:{slug}`` — by server slug
        - ``server_config:id:{server_id}`` — by server UUID

    TTL: 300 seconds (5 minutes).
    """

    _CACHE_PREFIX: str = "server_config:"
    _ID_CACHE_PREFIX: str = "server_config:id:"
    _CACHE_TTL: int = 300

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    async def get(slug: str, redis: Redis) -> dict[str, Any] | None:
        """Get server configuration by slug.

        1. Checks Redis for a cached config at ``server_config:{slug}``.
        2. On cache hit, returns the parsed JSON dict.
        3. On cache miss, loads the server from the database, builds a
           config dict, stores it in Redis with a 5-minute TTL, and
           returns it.

        Returns:
            The server configuration dict, or ``None`` if no server
            exists for the given slug.
        """
        cache_key = f"{ServerConfigCache._CACHE_PREFIX}{slug}"

        # ── Cache hit ────────────────────────────────────────────
        cached = await redis.get(cache_key)
        if cached is not None:
            logger.info("config_cache_hit", slug=slug)
            return json.loads(cached)

        # ── Cache miss — load from DB ────────────────────────────
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MCPServer)
                .options(selectinload(MCPServer.owner))
                .where(MCPServer.slug == slug)
            )
            server = result.scalar_one_or_none()

            if server is None:
                logger.info("config_server_not_found", slug=slug)
                return None

            config = ServerConfigCache._build_config(server)
            serialized = json.dumps(config, default=str)
            await redis.setex(cache_key, ServerConfigCache._CACHE_TTL, serialized)

            logger.info(
                "config_cache_miss",
                slug=slug,
                server_id=str(server.id),
            )

            return config

    @staticmethod
    async def invalidate(slug: str, redis: Redis) -> None:
        """Remove the cached configuration for the given slug.

        The next call to :meth:`get` for this slug will result in a
        cache miss and re-fetch from the database.
        """
        cache_key = f"{ServerConfigCache._CACHE_PREFIX}{slug}"
        await redis.delete(cache_key)
        logger.info("config_cache_invalidated", slug=slug)

    @staticmethod
    async def get_by_id(server_id: UUID, redis: Redis) -> dict[str, Any] | None:
        """Get server configuration by server UUID.

        Works identically to :meth:`get` but uses the key
        ``server_config:id:{server_id}`` and looks up the server by
        primary key instead of slug.
        """
        cache_key = f"{ServerConfigCache._ID_CACHE_PREFIX}{server_id}"

        # ── Cache hit ────────────────────────────────────────────
        cached = await redis.get(cache_key)
        if cached is not None:
            logger.info("config_cache_hit", server_id=str(server_id))
            return json.loads(cached)

        # ── Cache miss — load from DB ────────────────────────────
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MCPServer)
                .options(selectinload(MCPServer.owner))
                .where(MCPServer.id == server_id)
            )
            server = result.scalar_one_or_none()

            if server is None:
                logger.info("config_server_not_found", server_id=str(server_id))
                return None

            config = ServerConfigCache._build_config(server)
            serialized = json.dumps(config, default=str)
            await redis.setex(cache_key, ServerConfigCache._CACHE_TTL, serialized)

            logger.info(
                "config_cache_miss",
                server_id=str(server_id),
            )

            return config

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_config(server: MCPServer) -> dict[str, Any]:
        """Build a serialisable config dict from an ``MCPServer`` ORM instance.

        Accesses ``server.owner.plan`` via the lazy-loaded relationship.
        Falls back to ``"free"`` if the owner relationship is not
        available (e.g. orphaned server row).
        """
        return {
            "server_id": str(server.id),
            "user_id": str(server.user_id),
            "slug": server.slug,
            "name": server.name,
            "base_url": server.base_url,
            "auth_scheme": server.auth_scheme,
            "auth_header_name": server.auth_header_name,
            "tools_config": server.tools_config,
            "status": server.status,
            "plan": server.owner.plan if server.owner else "free",
            "transport_mode": server.transport_mode,
        }
