"""Health check endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health(client: AsyncClient) -> None:
    """GET /health should return 200 with status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "db" in data
    assert "redis" in data


@pytest.mark.asyncio
async def test_api_health(client: AsyncClient) -> None:
    """GET /api/v1/servers/health should return 200 with API info."""
    response = await client.get("/api/v1/servers/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "environment" in data
