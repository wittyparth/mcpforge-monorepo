"""Celery tasks for the AI Description Engine.

Uses asyncio.run() per task invocation to create a fresh event loop
and avoid the macOS kqueue selector bug (I/O operation on closed
kqueue) that occurs when reusing a loop across multiple Celery runs.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy import select, update

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AIDescriptionError
from app.core.logging import get_logger
from app.core.sse import sse_manager
from app.models.mcp_server import MCPServer
from app.models.user import User
from app.services.ai_description_engine import AIDescriptionEngine

logger = get_logger(__name__)


async def _enhance_async(
    server_id: str,
    user_id: str,
    tool_names: list[str] | None,
    request_id: str,
) -> dict[str, Any]:
    """Core async enhancement logic."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MCPServer).where(MCPServer.id == UUID(server_id)))
        server = result.scalar_one_or_none()
        if not server:
            raise AIDescriptionError(f"Server {server_id} not found")

        all_tools: list[dict[str, Any]] = server.tools_config.get("tools", [])
        tools_to_enhance = (
            [t for t in all_tools if t["name"] in tool_names] if tool_names else list(all_tools)
        )
        if not tools_to_enhance:
            logger.warning("ai_enhance_no_tools", server_id=server_id)
            return {"enhanced": 0, "failed": 0, "total_cost_cents": 0}

        if not server.original_tools_config:
            server.original_tools_config = deepcopy(server.tools_config)

        server.description_review_status = "in_progress"
        server.last_ai_run_at = datetime.now(timezone.utc).replace(tzinfo=None)

        total_tools = len(tools_to_enhance)

        await sse_manager.publish(server_id, {
            "event": "start", "server_id": server_id, "total": total_tools, "progress": 0,
        })

        engine = AIDescriptionEngine()
        sem = asyncio.Semaphore(5)

        async def _enhance_one(tool: dict[str, Any], index: int) -> dict[str, Any] | None:
            async with sem:
                try:
                    await sse_manager.publish(server_id, {
                        "event": "ai_progress", "server_id": server_id,
                        "tool_name": tool.get("name", ""), "progress": index, "total": total_tools,
                    })
                    result = await engine.enhance_tool(tool, all_tools)
                    quality = result.get("quality_score", {})
                    await sse_manager.publish(server_id, {
                        "event": "tool_enhanced", "server_id": server_id,
                        "tool_name": tool.get("name", ""),
                        "quality_score": quality.get("total", 0) if isinstance(quality, dict) else 0,
                        "cost_cents": result.get("cost_cents", 0),
                    })
                    return result
                except AIDescriptionError as e:
                    await sse_manager.publish(server_id, {
                        "event": "tool_failed", "server_id": server_id,
                        "tool_name": tool.get("name", ""), "error": str(e),
                    })
                    logger.error("ai_enhance_tool_failed", server_id=server_id, tool_name=tool.get("name"), error=str(e))
                    return None

        tasks = [_enhance_one(t, i) for i, t in enumerate(tools_to_enhance)]
        results = await asyncio.gather(*tasks)

        successful = [r for r in results if r is not None]
        total_cost = sum(r.get("cost_cents", 0) for r in successful)

        for result in successful:
            t_name = result.get("name", "")
            for i, t in enumerate(server.tools_config.get("tools", [])):
                if t.get("name") == t_name:
                    t.update({
                        "enhanced_name": result.get("enhanced_name"),
                        "enhanced_description": result.get("enhanced_description", t.get("description", "")),
                        "enhanced_parameters": result.get("enhanced_parameters", result.get("parameters", [])),
                        "enhanced_return_description": result.get("enhanced_return_description"),
                        "quality_score": result.get("quality_score", {}),
                        "improvements_made": result.get("improvements", []),
                        "enhanced_at": result.get("enhanced_at", ""),
                        "enhanced_by": "ai",
                    })

        # Build the updated tools_config as a plain dict and use an UPDATE
        # statement to bypass SQLAlchemy's JSON mutation tracking.
        updated_tools_config = dict(server.tools_config)
        await session.execute(
            update(MCPServer)
            .where(MCPServer.id == UUID(server_id))
            .values(
                tools_config=updated_tools_config,
                status="active",
                description_review_status=server.description_review_status,
                ai_enhancement_cost_cents=server.ai_enhancement_cost_cents,
            )
        )

        server.description_review_status = "review"
        server.ai_enhancement_cost_cents = (server.ai_enhancement_cost_cents or 0) + total_cost
        server.status = "active"

        if user_id:
            user_result = await session.execute(select(User).where(User.id == UUID(user_id)))
            user = user_result.scalar_one_or_none()
            if user is not None and user.plan == "free" and user.ai_enhancement_credits > 0:
                user.ai_enhancement_credits -= 1

        await session.commit()

    await sse_manager.publish(server_id, {
        "event": "ai_complete", "server_id": server_id,
        "total": total_tools, "successful": len(successful),
        "failed": total_tools - len(successful), "cost_cents": total_cost,
    })

    await sse_manager.publish(server_id, {
        "event": "done", "server_id": server_id,
        "progress": 98,
    })

    await sse_manager.publish(server_id, {
        "event": "complete", "server_id": server_id,
        "progress": 100,
    })

    logger.info("ai_enhance_complete", server_id=server_id, enhanced=len(successful), failed=total_tools - len(successful), cost_cents=total_cost)
    return {"enhanced": len(successful), "failed": total_tools - len(successful), "total_cost_cents": total_cost}


@celery_app.task(
    bind=True,
    name="app.services.ai_description.tasks.enhance_all_descriptions",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    autoretry_for=(AIDescriptionError,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def enhance_all_descriptions(
    self: Task,
    server_id: str,
    user_id: str,
    tool_names: list[str] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    """Enhance all (or specified) tool descriptions for a server."""
    logger.info("ai_enhance_start", server_id=server_id, request_id=request_id)
    return asyncio.run(_enhance_async(server_id, user_id, tool_names, request_id))
