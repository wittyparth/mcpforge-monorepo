"""Tests for ServerBuilder — build pipeline orchestrator (F2).

2+ tests covering:
  - Constructor stores repo reference
  - estimate_cost calculates based on tool count
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.mcp_server_repo import MCPServerRepository
from app.services.server_builder import ServerBuilder


class TestServerBuilderInit:
    """ServerBuilder construction."""

    def test_init_stores_server_repo(self, test_session: AsyncSession) -> None:
        """The repo reference should be stored."""
        repo = MCPServerRepository(test_session)
        builder = ServerBuilder(repo)
        assert builder.server_repo is repo


class TestEstimateCost:
    """estimate_cost behaviour."""

    @pytest.mark.asyncio
    async def test_estimate_cost_with_tools(self, test_session: AsyncSession) -> None:
        """estimate_cost should return cost based on tool count."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=uuid.uuid4(),
            slug=f"cost-test-{uuid.uuid4().hex[:8]}",
            name="Cost Test",
            base_url="https://api.example.com",
            tools_config={
                "tools": [
                    {"name": "tool_1", "description": "First tool"},
                    {"name": "tool_2", "description": "Second tool"},
                    {"name": "tool_3", "description": "Third tool"},
                ]
            },
        )

        builder = ServerBuilder(repo)
        cost = await builder.estimate_cost(server.id)
        # 3 tools * 1 cent per tool = 3 cents, minimum 1
        assert cost == 3

    @pytest.mark.asyncio
    async def test_estimate_cost_minimum_one(self, test_session: AsyncSession) -> None:
        """estimate_cost should return at least 1 even with no tools."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=uuid.uuid4(),
            slug=f"cost-min-{uuid.uuid4().hex[:8]}",
            name="Cost Min",
            base_url="https://api.example.com",
            tools_config={"tools": []},
        )

        builder = ServerBuilder(repo)
        cost = await builder.estimate_cost(server.id)
        # 0 tools, but minimum is 1
        assert cost == 1

    @pytest.mark.asyncio
    async def test_estimate_cost_nonexistent_server(self, test_session: AsyncSession) -> None:
        """estimate_cost should raise NotFoundError for non-existent server."""
        from app.core.exceptions import NotFoundError

        repo = MCPServerRepository(test_session)
        builder = ServerBuilder(repo)

        with pytest.raises(NotFoundError):
            await builder.estimate_cost(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_start_build_returns_response(self, test_session: AsyncSession) -> None:
        """start_build should return an AIEnhancementResponse."""
        repo = MCPServerRepository(test_session)
        server = await repo.create(
            user_id=uuid.uuid4(),
            slug=f"start-build-{uuid.uuid4().hex[:8]}",
            name="Start Build Test",
            base_url="https://api.example.com",
            tools_config={
                "tools": [
                    {"name": "tool_1", "description": "First tool"},
                ]
            },
        )

        builder = ServerBuilder(repo)

        # Mock Celery task delay to avoid Redis dependency
        with patch("app.services.server_builder.enhance_all_descriptions.delay") as mock_delay:
            mock_delay.return_value.id = "mock-job-id"

            response = builder.start_build(
                server_id=server.id,
                user_id=uuid.uuid4(),
                tool_names=["tool_1"],
            )

            assert response.job_id == "mock-job-id"
            assert response.estimated_cost_cents == 1  # 1 tool * 1 cent
            assert response.estimated_duration_seconds == 30
