"""MCPServer data access layer."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServer


class MCPServerRepository:
    """Repository for MCPServer CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        slug: str,
        name: str,
        base_url: str,
        description: str | None = None,
        spec_url: str | None = None,
        auth_scheme: str = "none",
        auth_header_name: str | None = None,
        tools_config: dict[str, Any] | None = None,
        transport_mode: str = "sse",
    ) -> MCPServer:
        """Create a new MCP server record."""
        server = MCPServer(
            user_id=user_id,
            slug=slug,
            name=name,
            description=description,
            base_url=base_url,
            spec_url=spec_url,
            auth_scheme=auth_scheme,
            auth_header_name=auth_header_name,
            tools_config=tools_config or {},
            transport_mode=transport_mode,
        )
        self.session.add(server)
        await self.session.flush()
        return server

    async def get_by_id(self, server_id: UUID) -> MCPServer | None:
        """Get a server by its UUID."""
        result = await self.session.execute(
            select(MCPServer).where(MCPServer.id == server_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> MCPServer | None:
        """Get a server by its unique slug."""
        result = await self.session.execute(
            select(MCPServer).where(MCPServer.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[MCPServer]:
        """List servers belonging to a user (paginated)."""
        result = await self.session.execute(
            select(MCPServer)
            .where(MCPServer.user_id == user_id)
            .order_by(MCPServer.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        """Count servers belonging to a user."""
        result = await self.session.execute(
            select(MCPServer).where(MCPServer.user_id == user_id)
        )
        return len(list(result.scalars().all()))

    async def update(self, server: MCPServer, **kwargs: object) -> MCPServer:
        """Update server fields in-place."""
        for key, value in kwargs.items():
            if hasattr(server, key):
                setattr(server, key, value)
        await self.session.flush()
        return server

    async def delete(self, server: MCPServer) -> None:
        """Delete a server."""
        await self.session.delete(server)
        await self.session.flush()

    async def increment_calls(self, server_id: UUID) -> None:
        """Increment total_calls and monthly_calls counters."""
        stmt = (
            update(MCPServer)
            .where(MCPServer.id == server_id)
            .values(
                total_calls=MCPServer.total_calls + 1,
                monthly_calls=MCPServer.monthly_calls + 1,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
