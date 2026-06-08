"""Tests for ServerConfigCache — read-through Redis cache for server configs.

Uses fakeredis for Redis mocking and the test DB fixtures from conftest
for database access. The ``AsyncSessionLocal`` used by the cache service
is patched with a test-session factory so all DB operations go through
the test engine.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from unittest.mock import patch

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.mcp_server import MCPServer
from app.models.user import User
from app.repositories.mcp_server_repo import MCPServerRepository
from app.services.server_config_cache import ServerConfigCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """Create an async_sessionmaker bound to the test engine.

    Used to patch ``AsyncSessionLocal`` inside the cache module so that
    the cache's DB queries hit the test database.
    """
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    return factory


@pytest.fixture
def fake_redis():
    """Create a fakeredis instance with decoded responses.

    The returned ``FakeAsyncRedis`` implements the same async interface
    as ``redis.asyncio.Redis`` and supports ``get``, ``setex``, ``ttl``,
    ``delete``, etc.
    """
    return FakeAsyncRedis(decode_responses=True)


@pytest_asyncio.fixture
async def persisted_server(test_session: AsyncSession) -> tuple[MCPServer, User]:
    """Create a test user + server committed to the test DB.

    Returns ``(server, user)``. Data is committed so that sessions
    created from ``test_session_factory`` (which use the same engine)
    can read it.
    """
    u = User(
        email=f"cache-{uuid_mod.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    test_session.add(u)
    await test_session.flush()

    s = MCPServer(
        user_id=u.id,
        slug=f"cache-{uuid_mod.uuid4().hex[:8]}",
        name="Cache Test Server",
        base_url="https://api.example.com",
        auth_scheme="bearer",
        tools_config={"tools": [{"name": "echo"}]},
        status="active",
        transport_mode="sse",
    )
    test_session.add(s)
    await test_session.commit()

    return s, u


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_miss_loads_from_db(
    test_session_factory,
    fake_redis: FakeAsyncRedis,
    persisted_server: tuple[MCPServer, User],
) -> None:
    """A fresh (uncached) slug loads the server from DB and caches the result."""
    server, user = persisted_server
    slug = server.slug

    with patch(
        "app.services.server_config_cache.AsyncSessionLocal",
        test_session_factory,
    ):
        config = await ServerConfigCache.get(slug=slug, redis=fake_redis)

    assert config is not None
    assert config["slug"] == slug
    assert config["server_id"] == str(server.id)
    assert config["name"] == server.name
    assert config["user_id"] == str(server.user_id)
    assert config["plan"] == user.plan
    assert config["status"] == "active"
    assert config["transport_mode"] == "sse"

    # Verify the result is now cached in Redis
    cache_key = f"server_config:{slug}"
    cached_raw = await fake_redis.get(cache_key)
    assert cached_raw is not None
    cached = json.loads(cached_raw)
    assert cached["slug"] == slug
    assert cached["plan"] == user.plan


@pytest.mark.asyncio
async def test_cache_hit_returns_cached(
    fake_redis: FakeAsyncRedis,
    persisted_server: tuple[MCPServer, User],
) -> None:
    """A cached value is returned without hitting the database."""
    server, _ = persisted_server
    slug = server.slug

    # Seed the cache directly
    seed_config = {
        "server_id": str(server.id),
        "user_id": str(server.user_id),
        "slug": slug,
        "name": server.name,
        "base_url": server.base_url,
        "auth_scheme": server.auth_scheme,
        "auth_header_name": server.auth_header_name,
        "tools_config": server.tools_config,
        "status": server.status,
        "plan": "free",
        "transport_mode": server.transport_mode,
    }
    cache_key = f"server_config:{slug}"
    await fake_redis.setex(cache_key, 300, json.dumps(seed_config, default=str))

    # Call get() — should return cached value WITHOUT touching the DB
    with patch(
        "app.services.server_config_cache.AsyncSessionLocal",
    ) as mock_factory:
        # If the code tries to open a DB session, fail fast
        mock_factory.side_effect = RuntimeError("DB session opened on cache hit")
        config = await ServerConfigCache.get(slug=slug, redis=fake_redis)

    assert config is not None
    assert config["slug"] == slug
    assert config["plan"] == "free"


@pytest.mark.asyncio
async def test_cache_ttl(
    test_session_factory,
    fake_redis: FakeAsyncRedis,
    persisted_server: tuple[MCPServer, User],
) -> None:
    """The cache entry is set with the correct TTL (300 s)."""
    server, _ = persisted_server
    slug = server.slug
    cache_key = f"server_config:{slug}"

    # Load through cache (this should set the TTL)
    with patch(
        "app.services.server_config_cache.AsyncSessionLocal",
        test_session_factory,
    ):
        await ServerConfigCache.get(slug=slug, redis=fake_redis)

    ttl = await fake_redis.ttl(cache_key)
    # The TTL should be 300 (or close to it; fakeredis may not
    # decrement in real-time, so assert a generous bound).
    assert ttl > 0, "Cache entry must have a positive TTL"
    assert ttl <= 300, "Cache entry TTL must not exceed the configured value"


@pytest.mark.asyncio
async def test_cache_invalidation(
    fake_redis: FakeAsyncRedis,
    persisted_server: tuple[MCPServer, User],
) -> None:
    """Invalidate removes the cache key; subsequent get re-loads."""
    server, _ = persisted_server
    slug = server.slug
    cache_key = f"server_config:{slug}"

    # Seed the cache
    seed = {"slug": slug, "name": "stale"}
    await fake_redis.setex(cache_key, 300, json.dumps(seed))

    # Invalidate
    await ServerConfigCache.invalidate(slug=slug, redis=fake_redis)

    # Key must be gone
    assert await fake_redis.get(cache_key) is None


@pytest.mark.asyncio
async def test_nonexistent_server(
    test_session_factory,
    fake_redis: FakeAsyncRedis,
) -> None:
    """A slug that does not exist in the DB returns None."""
    with patch(
        "app.services.server_config_cache.AsyncSessionLocal",
        test_session_factory,
    ):
        config = await ServerConfigCache.get(
            slug="this-slug-does-not-exist",
            redis=fake_redis,
        )

    assert config is None


@pytest.mark.asyncio
async def test_status_changes_reflected(
    test_session_factory,
    fake_redis: FakeAsyncRedis,
    persisted_server: tuple[MCPServer, User],
) -> None:
    """After invalidation, a subsequent get loads fresh data from DB."""
    server, _ = persisted_server
    slug = server.slug

    # 1. First load — cache miss, pulls from DB
    with patch(
        "app.services.server_config_cache.AsyncSessionLocal",
        test_session_factory,
    ):
        config1 = await ServerConfigCache.get(slug=slug, redis=fake_redis)
    assert config1 is not None
    assert config1["status"] == "active"

    # 2. Update the server's status in the database
    async with test_session_factory() as session:
        repo = MCPServerRepository(session)
        db_server = await repo.get_by_slug(slug)
        assert db_server is not None
        db_server.status = "paused"
        await session.commit()

    # 3. Invalidate the cache so the next read goes to DB
    await ServerConfigCache.invalidate(slug=slug, redis=fake_redis)

    # 4. Re-read — should get the updated status from DB
    with patch(
        "app.services.server_config_cache.AsyncSessionLocal",
        test_session_factory,
    ):
        config2 = await ServerConfigCache.get(slug=slug, redis=fake_redis)
    assert config2 is not None
    assert config2["status"] == "paused"


