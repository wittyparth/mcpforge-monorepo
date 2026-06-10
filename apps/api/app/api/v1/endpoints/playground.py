"""Playground endpoints for browser MCP Playground (F3).

Includes:
  - POST /{slug}/playground/share — create a shareable test link
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.redis import get_redis_pool
from app.models.user import User
from app.repositories.mcp_server_repo import MCPServerRepository
from app.schemas.playground import (
    PlaygroundShareTestRequest,
    PlaygroundShareTestResponse,
)

logger = get_logger(__name__)

router = APIRouter()

# Keys that should never be included in share URLs or stored in share data.
_SENSITIVE_ARG_KEYS: set[str] = {
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "auth",
    "token",
    "secret",
    "password",
    "passwd",
    "client_secret",
    "clientsecret",
    "access_token",
    "refresh_token",
    "x-api-key",
    "x-auth-token",
}

SHARE_REDIS_PREFIX = "playground_share:"
"""Redis key prefix for share data.  Full key: ``playground_share:{share_id}``."""


def _strip_credentials(arguments: dict[str, object]) -> dict[str, object]:
    """Return a copy of ``arguments`` with sensitive credential keys removed.

    Case-insensitive matching against ``_SENSITIVE_ARG_KEYS``.
    """
    lower_map = {k.lower(): k for k in arguments}
    sensitive_lower = _SENSITIVE_ARG_KEYS & lower_map.keys()
    if not sensitive_lower:
        return arguments.copy()
    return {
        k: v
        for k, v in arguments.items()
        if k.lower() not in _SENSITIVE_ARG_KEYS
    }


@router.post(
    "/{slug}/playground/share",
    response_model=PlaygroundShareTestResponse,
    status_code=201,
)
async def create_share_link(
    slug: str,
    body: PlaygroundShareTestRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaygroundShareTestResponse:
    """Create a shareable test link for a server's playground tool.

    The link embeds a ``share_id`` that the playground front-end uses to
    fetch pre-filled tool arguments from Redis.  Credential-like keys are
    stripped from the stored payload before persisting.
    """
    # ── Look up server ──────────────────────────────────────────────
    repo = MCPServerRepository(session)
    server = await repo.get_by_slug(slug)
    if server is None:
        raise NotFoundError(f"Server with slug '{slug}' not found")

    # ── Ownership check ─────────────────────────────────────────────
    if server.user_id != current_user.id:
        raise ForbiddenError("You do not own this server")

    # ── Build share payload ─────────────────────────────────────────
    share_id = str(uuid.uuid4())
    safe_arguments = _strip_credentials(body.arguments)

    share_data: dict[str, object] = {
        "tool_name": body.tool_name,
        "arguments": safe_arguments,
        "server_slug": slug,
        "server_id": str(server.id),
        "user_id": str(current_user.id),
    }

    ttl_seconds = body.expires_in_hours * 3600
    redis_key = f"{SHARE_REDIS_PREFIX}{share_id}"

    # ── Persist to Redis ────────────────────────────────────────────
    pool = await get_redis_pool()
    r = Redis.from_pool(pool)
    try:
        await r.setex(redis_key, ttl_seconds, json.dumps(share_data))
    finally:
        await r.close()

    # ── Build response ──────────────────────────────────────────────
    expires_at = datetime.now(UTC) + timedelta(hours=body.expires_in_hours)
    share_url = f"/dashboard/servers/{slug}/playground?share={share_id}"

    return PlaygroundShareTestResponse(
        share_id=share_id,
        url=share_url,
        expires_at=expires_at,
    )
