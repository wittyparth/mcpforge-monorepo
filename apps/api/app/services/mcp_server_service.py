"""MCP server management business logic."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.mcp_server import MCPServer
from app.repositories.mcp_server_repo import MCPServerRepository
from app.repositories.user_repo import UserRepository


class MCPServerService:
    """Service-layer logic for MCP server CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.server_repo = MCPServerRepository(session)
        self.user_repo = UserRepository(session)

    async def create_server(
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
        """Create a new MCP server.

        Raises:
            ConflictError: If the slug is already taken.
        """
        existing = await self.server_repo.get_by_slug(slug)
        if existing:
            raise ConflictError(f"Slug '{slug}' is already in use")

        return await self.server_repo.create(
            user_id=user_id,
            slug=slug,
            name=name,
            base_url=base_url,
            description=description,
            spec_url=spec_url,
            auth_scheme=auth_scheme,
            auth_header_name=auth_header_name,
            tools_config=tools_config,
            transport_mode=transport_mode,
        )

    async def get_server(self, server_id: UUID) -> MCPServer:
        """Get a server by ID.

        Raises:
            NotFoundError: If the server doesn't exist.
        """
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise NotFoundError("Server not found")
        return server

    async def get_server_by_slug(self, slug: str) -> MCPServer:
        """Get a server by slug.

        Raises:
            NotFoundError: If the server doesn't exist.
        """
        server = await self.server_repo.get_by_slug(slug)
        if not server:
            raise NotFoundError("Server not found")
        return server

    async def list_user_servers(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[MCPServer]:
        """List servers for a user."""
        return await self.server_repo.list_by_user(user_id, skip=skip, limit=limit)

    async def update_server(
        self,
        server_id: UUID,
        user_id: UUID,
        **kwargs: object,
    ) -> MCPServer:
        """Update a server, verifying ownership.

        Raises:
            NotFoundError: If the server doesn't exist.
            PermissionError: If the user doesn't own the server.
        """
        server = await self.get_server(server_id)
        if server.user_id != user_id:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError("You do not own this server")
        return await self.server_repo.update(server, **kwargs)

    async def delete_server(self, server_id: UUID, user_id: UUID) -> None:
        """Delete a server, verifying ownership.

        Raises:
            NotFoundError: If the server doesn't exist.
            ForbiddenError: If the user doesn't own the server.
        """
        server = await self.get_server(server_id)
        if server.user_id != user_id:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError("You do not own this server")
        await self.server_repo.delete(server)
