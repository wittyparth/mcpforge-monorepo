"""MCP Server CRUD and management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.team_repo import TeamRepository
from app.repositories.user_repo import UserRepository
from app.schemas.mcp_server import (
    DuplicateServerRequest,
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
    RollbackRequest,
    ServerVersionResponse,
    ServerVersionsResponse,
)
from app.services.mcp_server_service import MCPServerService, _slugify

logger = get_logger(__name__)

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


@router.post("/{server_id}/duplicate", response_model=MCPServerResponse, status_code=201)
async def duplicate_server(
    server_id: UUID,
    body: DuplicateServerRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """Duplicate an existing MCP server.

    Creates a new server with the same configuration (tools_config)
    but resets version, stats, and status. Credentials are NOT copied.
    The new server starts in ``building`` status.
    """
    svc = MCPServerService(session)
    new_slug = body.new_slug or _slugify(body.new_name)

    server = await svc.duplicate_server(
        source_server_id=server_id,
        new_owner_user_id=current_user.id,
        new_name=body.new_name,
        new_slug=new_slug,
    )

    # Write audit log if part of a team
    if server.team_id:
        try:
            team_repo = TeamRepository(session)
            await team_repo.create_audit_log(
                team_id=server.team_id,
                user_id=current_user.id,
                action="server.duplicate",
                resource_type="server",
                resource_id=server.id,
                metadata={"source_server_id": str(server_id)},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except Exception:
            logger.warning("audit_log_failed", server_id=str(server_id), action="server.duplicate")

    return MCPServerResponse.model_validate(server)


@router.get("/{server_id}/versions", response_model=ServerVersionsResponse)
async def list_server_versions(
    server_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ServerVersionsResponse:
    """List version history for a server, newest first."""
    svc = MCPServerService(session)

    # Verify access
    await svc.get_server_with_access_check(server_id, current_user.id, "viewer")

    items, total = await svc.list_versions(server_id, skip=skip, limit=limit)

    # Enrich with user email
    user_repo = UserRepository(session)
    version_responses: list[ServerVersionResponse] = []
    for item in items:
        changed_by_email: str | None = None
        if item.changed_by:
            user = await user_repo.get_by_id(item.changed_by)
            changed_by_email = user.email if user else None
        version_responses.append(
            ServerVersionResponse(
                id=item.id,
                version=item.version,
                change_note=item.change_note,
                changed_by=item.changed_by,
                changed_by_email=changed_by_email,
                created_at=item.created_at,
            )
        )

    return ServerVersionsResponse(
        items=version_responses,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/{server_id}/rollback", response_model=MCPServerResponse)
async def rollback_server(
    server_id: UUID,
    body: RollbackRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """Rollback a server to a previous version.

    The current state is snapshotted first (so rollback is reversible).
    The server's version counter is incremented.
    """
    svc = MCPServerService(session)
    server = await svc.rollback_to_version(
        server_id=server_id,
        target_version=body.version,
        actor_id=current_user.id,
    )

    # Write audit log if part of a team
    if server.team_id:
        try:
            team_repo = TeamRepository(session)
            await team_repo.create_audit_log(
                team_id=server.team_id,
                user_id=current_user.id,
                action="server.rollback",
                resource_type="server",
                resource_id=server.id,
                metadata={
                    "from_version": server.version - 1,
                    "to_version": body.version,
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except Exception:
            logger.warning("audit_log_failed", server_id=str(server_id), action="server.rollback")

    return MCPServerResponse.model_validate(server)
