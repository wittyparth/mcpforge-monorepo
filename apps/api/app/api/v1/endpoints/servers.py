"""MCP Server CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
)
from app.services.mcp_server_service import MCPServerService

router = APIRouter()


@router.get("", response_model=list[MCPServerResponse])
async def list_servers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MCPServerResponse]:
    """List all MCP servers for the current user."""
    svc = MCPServerService(session)
    servers = await svc.list_user_servers(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return [MCPServerResponse.model_validate(s) for s in servers]


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create_server(
    body: MCPServerCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """Create a new MCP server."""
    svc = MCPServerService(session)
    server = await svc.create_server(
        user_id=current_user.id,
        slug=body.slug,
        name=body.name,
        base_url=body.base_url,
        description=body.description,
        spec_url=body.spec_url,
        auth_scheme=body.auth_scheme,
        auth_header_name=body.auth_header_name,
        tools_config=body.tools_config,
        transport_mode=body.transport_mode,
    )
    return MCPServerResponse.model_validate(server)


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """Get a specific MCP server by ID."""
    svc = MCPServerService(session)
    # Verify ownership via update_server check
    server = await svc.get_server(server_id)
    if server.user_id != current_user.id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("You do not own this server")
    return MCPServerResponse.model_validate(server)


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: UUID,
    body: MCPServerUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """Update an MCP server."""
    svc = MCPServerService(session)
    update_kwargs = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    server = await svc.update_server(
        server_id=server_id,
        user_id=current_user.id,
        **update_kwargs,
    )
    return MCPServerResponse.model_validate(server)


@router.delete("/{server_id}", status_code=204, response_model=None)
async def delete_server(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete an MCP server."""
    svc = MCPServerService(session)
    await svc.delete_server(server_id=server_id, user_id=current_user.id)
