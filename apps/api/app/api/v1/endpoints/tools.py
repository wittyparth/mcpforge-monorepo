"""Tool workspace endpoints (F1 + F2).

F1: List + update tools (live).
F2: AI description enhancement (ServerBuilder).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.repositories.mcp_server_repo import MCPServerRepository
from app.repositories.user_repo import UserRepository
from app.schemas.ai_description import AIEnhancementRequest, AIEnhancementResponse
from app.schemas.mcp_server import ToolListResponse, ToolUpdateRequest
from app.services.mcp_server_service import MCPServerService
from app.services.server_builder import ServerBuilder

logger = get_logger(__name__)

router = APIRouter(prefix="/servers/{server_id}/tools", tags=["tools"])


async def _get_server_and_check_ownership(
    server_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> MCPServer:
    """Load a server and verify the current user owns it."""
    svc = MCPServerService(session)
    server = await svc.get_server(server_id)
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")
    return server


@router.get("", response_model=ToolListResponse)
async def list_tools(
    server_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ToolListResponse:
    """List all tools for a server."""
    server = await _get_server_and_check_ownership(server_id, current_user, session)
    tools = server.tools_config.get("tools", [])

    logger.info("tool_listed", server_id=str(server_id), tool_count=len(tools))

    return ToolListResponse(server_id=server.id, tool_count=len(tools), tools=tools)


@router.patch("/{tool_name}", response_model=dict)
async def update_tool(
    server_id: UUID,
    tool_name: str,
    body: ToolUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a single tool (description, enabled, rename)."""
    server = await _get_server_and_check_ownership(server_id, current_user, session)

    tools_config = server.tools_config
    tools: list[dict[str, Any]] = tools_config.get("tools", [])
    if not tools:
        raise NotFoundError(f"Tool '{tool_name}' not found")

    # Find the tool index by name
    tool_idx: int | None = None
    for i, tool in enumerate(tools):
        if tool.get("name") == tool_name:
            tool_idx = i
            break

    if tool_idx is None:
        raise NotFoundError(f"Tool '{tool_name}' not found")

    # Build update dict from non-None request fields
    update: dict[str, Any] = {}
    if body.description is not None:
        update["description"] = body.description
    if body.enabled is not None:
        update["enabled"] = body.enabled
    if body.name is not None:
        new_name = body.name
        # Check for collision with other tools
        for i, tool in enumerate(tools):
            if i != tool_idx and tool.get("name") == new_name:
                raise ConflictError(f"Tool name '{new_name}' is already in use")
        update["name"] = new_name

    if update:
        # Apply the update in-place
        tools[tool_idx].update(update)
        tools_config["tools"] = tools

        # Persist via the service layer
        svc = MCPServerService(session)
        await svc.update_server(
            server_id=server_id,
            user_id=current_user.id,
            tools_config=tools_config,
        )

        logger.info(
            "tool_updated",
            server_id=str(server_id),
            tool_name=tool_name,
            updated_fields=list(update.keys()),
        )

    return tools[tool_idx]


@router.post("/enhance", response_model=AIEnhancementResponse)
async def enhance_tools(
    server_id: UUID,
    body: AIEnhancementRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIEnhancementResponse:
    """Re-run AI enhancement on the server's tools."""
    repo = MCPServerRepository(session)
    server = await repo.get_by_id(server_id)
    if not server:
        raise NotFoundError("Server not found")
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")

    tools = server.tools_config.get("tools", [])
    if not tools:
        raise NotFoundError("Server has no tools to enhance")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(current_user.id)
    if user is not None and user.plan == "free" and user.ai_enhancement_credits <= 0:
        raise ForbiddenError(
            "Insufficient AI enhancement credits. "
            "Upgrade your plan or wait for the next billing cycle."
        )

    builder = ServerBuilder(repo)
    response = builder.start_build(
        server_id,
        current_user.id,
        tool_names=body.tool_names,
    )

    logger.info(
        "ai_enhancement_started",
        server_id=str(server_id),
        tool_count=len(tools),
        tool_names=body.tool_names,
    )
    return response
