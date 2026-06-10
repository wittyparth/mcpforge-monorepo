"""Test fixtures and configuration.

Uses a test PostgreSQL database by default. Falls back to SQLite for local runs.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

# Register UUID adapter for SQLite — aiosqlite does not natively understand
# Python uuid.UUID objects passed as query parameters. This adapter converts
# them to strings transparently.
try:
    import sqlite3

    # Use uuid.hex (no dashes) to match the ORM's PG_UUID bind processor format.
    # PG_UUID bind_processor converts UUID → hex string without dashes (e.g.
    # "8daddf22991645a9987bd176a1cf2883"). The adapter must produce the same
    # format so that raw-SQL inserts and ORM WHERE clauses compare consistently.
    sqlite3.register_adapter(uuid.UUID, lambda u: u.hex)
except ImportError:
    pass

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_current_user, get_db
from app.core.celery_app import celery_app
from app.core.config import settings
from app.main import app
from app.models.base import Base
from app.models.user import User

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

# Wave 0 hardening: disable features that make network calls or depend
# on external services in the default test environment. Individual tests
# can override these with monkeypatch.
settings.ENVIRONMENT = "testing"
settings.HIBP_ENABLED = False

# SQLite by default for local dev (zero setup).
# CI workflows override via DATABASE_URL=postgresql+asyncpg://...
_DEFAULT_SQLITE = "sqlite+aiosqlite:///./test.db"
TEST_DATABASE_URL = settings.DATABASE_URL
if "sqlite" not in str(TEST_DATABASE_URL).lower():
    TEST_DATABASE_URL = _DEFAULT_SQLITE


@pytest_asyncio.fixture
async def test_engine():
    """Create a test engine and create all tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with dependency overrides."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_user(test_session: AsyncSession) -> User:
    """Create a test user for use with the ``auth_client`` fixture."""
    u = User(
        email=f"auth-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
    )
    test_session.add(u)
    await test_session.flush()
    return u


@pytest_asyncio.fixture
async def auth_client(
    test_session: AsyncSession, auth_user: User
) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with the ``auth_user`` injected as the current user.

    Overrides both ``get_db`` (→ ``test_session``) and ``get_current_user``
    (→ ``auth_user``) so endpoint tests can call protected routes without
    going through the real JWT decode path.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    def override_get_current_user() -> User:
        return auth_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
