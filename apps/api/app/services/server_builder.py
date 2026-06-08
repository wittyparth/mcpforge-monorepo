"""Server build pipeline orchestrator.

Manages the end-to-end build process for an MCP server:

1. F2: AI description enhancement
2. F5: Security scanner (future)
3. F4: Gateway deployment (future)

The pipeline is started by calling ``start_build()``, which enqueues a
Celery task and returns immediately with job metadata.
"""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.repositories.mcp_server_repo import MCPServerRepository
from app.schemas.ai_description import AIEnhancementResponse

logger = get_logger(__name__)

# Rough cost estimate: 1 cent per tool (DeepSeek pricing rounded up).
_COST_PER_TOOL_CENTS = 1


class ServerBuilder:
    """Orchestrates the build pipeline stages.

    Usage::

        repo = MCPServerRepository(session)
        builder = ServerBuilder(repo)
        response = builder.start_build(server_id, user_id)
    """

    def __init__(self, server_repo: MCPServerRepository) -> None:
        """Store a reference to the server repository.

        Args:
            server_repo: Repository for MCP server data access.
        """
        self.server_repo: MCPServerRepository = server_repo

    async def estimate_cost(self, server_id: UUID) -> int:
        """Estimate the cost of the build in cents based on tool count.

        Rough estimate: ~1 cent per tool (DeepSeek pricing rounded up).

        Args:
            server_id: UUID of the server to estimate for.

        Returns:
            Estimated cost in cents (minimum 1).

        Raises:
            NotFoundError: If the server does not exist.
        """
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise NotFoundError("Server not found")
        tools = server.tools_config.get("tools", [])
        return max(1, len(tools)) * _COST_PER_TOOL_CENTS

    def start_build(
        self,
        server_id: UUID,
        user_id: UUID,
        tool_names: list[str] | None = None,
    ) -> AIEnhancementResponse:
        """Start the build pipeline.

        Enqueues the AI enhancement Celery task and returns job info
        immediately. The caller can poll progress via the SSE stream.

        Args:
            server_id: UUID of the server to build.
            user_id: UUID of the requesting user.
            tool_names: If set, only enhance these specific tools.
                When ``None``, all tools are enhanced.

        Returns:
            An ``AIEnhancementResponse`` with the job ID and cost estimate.
        """
        tool_count = len(tool_names) if tool_names else 0
        estimated_cost = tool_count * _COST_PER_TOOL_CENTS

        job = enhance_all_descriptions.delay(
            server_id=str(server_id),
            user_id=str(user_id),
            tool_names=tool_names,
            request_id="",
        )

        logger.info(
            "build_started",
            server_id=str(server_id),
            user_id=str(user_id),
            job_id=job.id,
        )

        return AIEnhancementResponse(
            job_id=job.id,
            estimated_cost_cents=estimated_cost,
            estimated_duration_seconds=30,
            remaining_credits=None,
        )


# Import the task at module level so Celery can register it.
# The import is placed at the bottom to keep the task dependency
# clearly separated from the infrastructure imports above.
from app.services.ai_description.tasks import enhance_all_descriptions  # noqa: E402, F811
