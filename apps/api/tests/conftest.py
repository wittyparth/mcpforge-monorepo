"""Test fixtures and configuration.

Uses a test PostgreSQL database by default. Falls back to SQLite for local runs.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.base import Base

# Wave 0 hardening: disable features that make network calls or depend
# on external services in the default test environment. Individual tests
# can override these with monkeypatch.
settings.HIBP_ENABLED = False

# Use SQLite by default for local testing. Override with
# `DATABASE_URL=postgresql+asyncpg://...` env var for CI.
_TEST_SQLITE = "sqlite+aiosqlite:///./test.db"
TEST_DATABASE_URL = settings.TEST_DATABASE_URL if hasattr(settings, 'TEST_DATABASE_URL') else _TEST_SQLITE
if "postgresql" in TEST_DATABASE_URL or "localhost" in TEST_DATABASE_URL:
    # Called from CI where a real PostgreSQL test database is available.
    # Use the provided URL directly; else fall back to SQLite.
    if "sqlite" not in str(TEST_DATABASE_URL):
        pass  # CI provides postgres
    else:
        TEST_DATABASE_URL = _TEST_SQLITE
else:
    TEST_DATABASE_URL = _TEST_SQLITE


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
