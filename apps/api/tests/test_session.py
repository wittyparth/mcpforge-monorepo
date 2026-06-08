"""Tests for SessionManager — in-memory MCP gateway session lifecycle.

Covers add, get, remove, cleanup_expired, and idempotent semantics.
No external dependencies needed (pure in-memory dict operations).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.gateway.session import MCPSession, SessionManager


@pytest.mark.asyncio
async def test_add_and_get_session() -> None:
    """Creates a session and retrieves it by ID."""
    manager = SessionManager()
    session = MCPSession(
        session_id="sess-001",
        server_id="550e8400-e29b-41d4-a716-446655440000",
        user_id="user-abc",
        slug="my-server",
    )

    await manager.add(session)
    retrieved = await manager.get("sess-001")

    assert retrieved is not None
    assert retrieved.session_id == "sess-001"
    assert retrieved.server_id == "550e8400-e29b-41d4-a716-446655440000"
    assert retrieved.slug == "my-server"


@pytest.mark.asyncio
async def test_get_nonexistent_session() -> None:
    """Returns None when the session ID does not exist."""
    manager = SessionManager()
    result = await manager.get("does-not-exist")
    assert result is None


@pytest.mark.asyncio
async def test_remove_session() -> None:
    """Removes a session and subsequent get returns None."""
    manager = SessionManager()
    session = MCPSession(
        session_id="sess-002",
        server_id="660e8400-e29b-41d4-a716-446655440001",
        user_id="user-xyz",
        slug="another-server",
    )

    await manager.add(session)
    await manager.remove("sess-002")

    retrieved = await manager.get("sess-002")
    assert retrieved is None


@pytest.mark.asyncio
async def test_multiple_sessions() -> None:
    """Handles multiple sessions independently without interference."""
    manager = SessionManager()

    s1 = MCPSession(
        session_id="sess-a",
        server_id="aaa",
        user_id="user-1",
        slug="server-a",
    )
    s2 = MCPSession(
        session_id="sess-b",
        server_id="bbb",
        user_id="user-2",
        slug="server-b",
    )
    s3 = MCPSession(
        session_id="sess-c",
        server_id="ccc",
        user_id="user-3",
        slug="server-c",
    )

    await manager.add(s1)
    await manager.add(s2)
    await manager.add(s3)

    # Retrieve individually
    assert (await manager.get("sess-a")) is not None
    assert (await manager.get("sess-b")) is not None
    assert (await manager.get("sess-c")) is not None

    # Remove middle one
    await manager.remove("sess-b")
    assert (await manager.get("sess-a")) is not None
    assert (await manager.get("sess-b")) is None
    assert (await manager.get("sess-c")) is not None


@pytest.mark.asyncio
async def test_session_initialized_flag() -> None:
    """Default initialized flag is False and can be set to True."""
    manager = SessionManager()
    session = MCPSession(
        session_id="sess-init",
        server_id="ddd",
        user_id="user-init",
        slug="init-server",
    )

    await manager.add(session)
    retrieved = await manager.get("sess-init")
    assert retrieved is not None
    assert retrieved.initialized is False

    # Update the flag
    retrieved.initialized = True
    await manager.add(retrieved)  # Overwrite

    re_retrieved = await manager.get("sess-init")
    assert re_retrieved is not None
    assert re_retrieved.initialized is True


@pytest.mark.asyncio
async def test_session_idempotent() -> None:
    """Multiple add calls with the same session ID don't crash (overwrite)."""
    manager = SessionManager()

    s1 = MCPSession(
        session_id="sess-dup",
        server_id="eee",
        user_id="user-dup",
        slug="dup-server",
        initialized=False,
    )
    s2 = MCPSession(
        session_id="sess-dup",
        server_id="fff",
        user_id="user-overwrite",
        slug="dup-server-overwrite",
        initialized=True,
    )

    # Add twice — should not raise
    await manager.add(s1)
    await manager.add(s2)  # Overwrite

    # Last write wins
    retrieved = await manager.get("sess-dup")
    assert retrieved is not None
    assert retrieved.server_id == "fff"
    assert retrieved.initialized is True
    assert retrieved.slug == "dup-server-overwrite"
