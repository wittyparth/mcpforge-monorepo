"""Celery tasks for the AI Description Engine.

Enhances all (or specified) tool descriptions for a server in parallel
with a semaphore of 5 concurrent LLM calls. Emits SSE events throughout
the process so the frontend can render a live progress bar.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AIDescriptionError
from app.core.logging import get_logger
from app.core.sse import sse_manager
from app.repositories.mcp_server_repo import MCPServerRepository
from app.repositories.user_repo import UserRepository
from app.services.ai_description_engine import AIDescriptionEngine

logger = get_logger(__name__)

# Maximum number of concurrent LLM enhancement calls.
_CONCURRENCY_LIMIT = 5


@celery_app.task(
    bind=True,
    name="app.services.ai_description.tasks.enhance_all_descriptions",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    autoretry_for=(AIDescriptionError,),
    retry_backoff=True,
    retry_backoff_max=300,
)  # type: ignore[misc]
def enhance_all_descriptions(
    self: Any,
    server_id: str,
    user_id: str,
    tool_names: list[str] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    """Enhance all (or specified) tool descriptions for a server.

    Runs as a Celery task with eager mode for testing.
    Uses ``asyncio.run()`` internally since Celery tasks are synchronous.

    Returns a dict with ``enhanced``, ``failed``, and ``total_cost_cents`` keys.
    """
    logger.info("ai_enhance_start", server_id=server_id, request_id=request_id)

    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            # 1. Load server and verify it exists
            server_repo = MCPServerRepository(session)
            user_repo = UserRepository(session)
            server = await server_repo.get_by_id(UUID(server_id))
            if not server:
                raise AIDescriptionError(f"Server {server_id} not found")

            # 2. Determine which tools to enhance
            all_tools: list[dict[str, Any]] = server.tools_config.get("tools", [])
            if tool_names:
                tools_to_enhance = [t for t in all_tools if t["name"] in tool_names]
            else:
                tools_to_enhance = list(all_tools)

            if not tools_to_enhance:
                logger.warning("ai_enhance_no_tools", server_id=server_id)
                return {"enhanced": 0, "failed": 0, "total_cost_cents": 0}

            # 3. Snapshot original tools_config for potential revert
            if not server.original_tools_config:
                server.original_tools_config = deepcopy(server.tools_config)

            # 4. Mark status as in_progress
            server.description_review_status = "in_progress"
            server.last_ai_run_at = datetime.now(UTC)

            # 5. Emit SSE start event
            total_tools = len(tools_to_enhance)
            await sse_manager.publish(server_id, {
                "event": "start",
                "server_id": server_id,
                "total": total_tools,
                "progress": 0,
            })

            # 6. Enhance tools in parallel with bounded concurrency
            engine = AIDescriptionEngine()
            sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

            async def _enhance_one(
                tool: dict[str, Any],
                index: int,
            ) -> dict[str, Any] | None:
                async with sem:
                    try:
                        await sse_manager.publish(server_id, {
                            "event": "ai_progress",
                            "server_id": server_id,
                            "tool_name": tool.get("name", ""),
                            "status": "enhancing",
                            "progress": index,
                            "total": total_tools,
                        })

                        result = await engine.enhance_tool(tool, all_tools)
                        quality = result.get("quality_score", {})

                        await sse_manager.publish(server_id, {
                            "event": "tool_enhanced",
                            "server_id": server_id,
                            "tool_name": tool.get("name", ""),
                            "quality_score": (
                                quality.get("total", 0)
                                if isinstance(quality, dict)
                                else 0
                            ),
                            "cost_cents": result.get("cost_cents", 0),
                        })

                        return result
                    except AIDescriptionError as e:
                        await sse_manager.publish(server_id, {
                            "event": "tool_failed",
                            "server_id": server_id,
                            "tool_name": tool.get("name", ""),
                            "error": str(e),
                        })
                        logger.error(
                            "ai_enhance_tool_failed",
                            server_id=server_id,
                            tool_name=tool.get("name"),
                            error=str(e),
                        )
                        return None

            tasks = [_enhance_one(t, i) for i, t in enumerate(tools_to_enhance)]
            results = await asyncio.gather(*tasks)

            # 7. Write results back into tools_config
            successful: list[dict[str, Any]] = [r for r in results if r is not None]
            total_cost = sum(r.get("cost_cents", 0) for r in successful)

            tools_config = server.tools_config
            for result in successful:
                tool_name = result.get("name", "")
                for i, t in enumerate(tools_config.get("tools", [])):
                    if t.get("name") == tool_name:
                        tools_config["tools"][i].update({
                            "enhanced_name": result.get("enhanced_name"),
                            "enhanced_description": result.get(
                                "enhanced_description",
                                t.get("description", ""),
                            ),
                            "enhanced_parameters": result.get(
                                "enhanced_parameters",
                                result.get("parameters", []),
                            ),
                            "enhanced_return_description": result.get(
                                "enhanced_return_description",
                            ),
                            "quality_score": result.get("quality_score", {}),
                            "improvements_made": result.get("improvements", []),
                            "enhanced_at": result.get("enhanced_at", ""),
                            "enhanced_by": "ai",
                        })

            server.tools_config = tools_config
            server.description_review_status = "review"
            server.ai_enhancement_cost_cents = (
                (server.ai_enhancement_cost_cents or 0) + total_cost
            )

            # 8. Decrement user credits (free tier only)
            user = await user_repo.get_by_id(UUID(user_id))
            if user is not None and user.plan == "free":
                await user_repo.decrement_credits(UUID(user_id), 1)

            await session.flush()

            # 9. Emit completion event
            await sse_manager.publish(server_id, {
                "event": "ai_complete",
                "server_id": server_id,
                "total": total_tools,
                "successful": len(successful),
                "failed": total_tools - len(successful),
                "cost_cents": total_cost,
            })

            await session.commit()

            logger.info(
                "ai_enhance_complete",
                server_id=server_id,
                enhanced=len(successful),
                failed=total_tools - len(successful),
                cost_cents=total_cost,
            )

            return {
                "enhanced": len(successful),
                "failed": total_tools - len(successful),
                "total_cost_cents": total_cost,
            }

    return asyncio.run(_run())
