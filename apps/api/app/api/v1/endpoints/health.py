"""Health check endpoints.

Provides /api/v1/servers/health with basic API info.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import APIHealthResponse

router = APIRouter()


@router.get("/health", response_model=APIHealthResponse)
async def api_health() -> APIHealthResponse:
    """Health check endpoint for the API service."""
    return APIHealthResponse(
        status="ok",
        version=settings.API_VERSION,
        environment=settings.ENVIRONMENT,
    )
