"""Session manager for MCP gateway connections.

Manages in-memory MCP sessions keyed by session ID. Sessions represent
active MCP protocol connections (SSE or StreamableHTTP) to a specific
server. For v1.0, sessions are stored in memory only — Redis-based
distributed sessions will be added when horizontal scaling is needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.logging import get_logger

logger = get_logger(__name__)

# 30 minutes in seconds
_SESSION_TIMEOUT_S: int = 1800


@dataclass
class MCPSession:
    """Represents an active MCP protocol session.

    Attributes:
        session_id: Unique identifier for the session.
        server_id: The UUID of the target MCP server.
        user_id: The UUID of the owning user.
        slug: Server slug (used for routing in gateway URLs).
        initialized: Whether the MCP handshake (initialize) has completed.
        client_name: Optional client-provided name (e.g. "Claude Desktop").
        created_at: When the session was created (UTC).
    """

    session_id: str
    server_id: str
    user_id: str
    slug: str
    initialized: bool = False
    client_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SessionManager:
    """In-memory session manager for MCP gateway connections.

    Thread-safe by design: all operations are async and there is no
    shared mutable state across concurrent accesses within a single
    event loop. For multi-process deployments, replace this with a
    Redis-backed session store.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, MCPSession] = {}

    async def add(self, session: MCPSession) -> None:
        """Store a session in memory.

        If a session with the same ID already exists, it is overwritten
        (idempotent — no error is raised).
        """
        self._sessions[session.session_id] = session
        logger.info(
            "session_created",
            session_id=session.session_id,
            slug=session.slug,
            server_id=session.server_id,
        )

    async def get(self, session_id: str) -> MCPSession | None:
        """Retrieve a session by its ID.

        Returns None if the session does not exist.
        """
        return self._sessions.get(session_id)

    async def remove(self, session_id: str) -> None:
        """Remove a session by its ID.

        Logs a warning if the session did not exist.
        """
        session = self._sessions.pop(session_id, None)
        if session is not None:
            logger.info(
                "session_removed",
                session_id=session_id,
                slug=session.slug,
            )
        else:
            logger.warning(
                "session_remove_missing",
                session_id=session_id,
            )

    async def cleanup_expired(self) -> list[str]:
        """Remove sessions older than the configured timeout.

        Returns:
            A list of session IDs that were removed.
        """
        now = datetime.now(UTC)
        expired_ids = [
            sid
            for sid, s in self._sessions.items()
            if (now - s.created_at).total_seconds() > _SESSION_TIMEOUT_S
        ]
        for sid in expired_ids:
            self._sessions.pop(sid, None)

        if expired_ids:
            logger.info(
                "sessions_cleanup_expired",
                count=len(expired_ids),
                session_ids=expired_ids,
            )

        return expired_ids
