"""MCP Gateway endpoints.

Provides the MCP protocol endpoints for the hosted gateway. All
protocol-bearing routes (SSE, message, StreamableHTTP) require JWT
authentication; the health check remains public for monitoring.

The WebSocket playground in `app.playground.ws` uses the same auth
mechanism (token in query string).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.gateway.transport_http import handle_http_request
from app.gateway.transport_sse import handle_message, handle_sse_connection
from app.repositories.user_repo import UserRepository

router = APIRouter()


async def authenticate_mcp_request(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> object:
    """Authenticate a gateway request, accepting JWT from any of:

    - `Authorization: Bearer <token>` header (programmatic clients)
    - `access_token` httpOnly cookie (browser clients)

    Raises:
        UnauthorizedError: 401 if no valid token is present.

    Unlike `get_current_user`, this returns the user object directly
    (same semantics; the name reflects intent at the call site).
    """
    token: str | None = None
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise UnauthorizedError("Authentication required for MCP gateway")

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        from uuid import UUID
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise UnauthorizedError("Invalid or expired token") from None

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedError("User not found")
    return user


@router.get("/mcp/v1/{slug}/health")
async def mcp_server_health(slug: str) -> dict[str, str]:
    """Health check for a specific MCP server (public)."""
    return {
        "status": "ok",
        "slug": slug,
        "version": "0.1.0",
    }


@router.get("/mcp/v1/{slug}/sse", dependencies=[Depends(authenticate_mcp_request)])
async def mcp_sse_endpoint(
    slug: str,
    request: Request,
) -> StreamingResponse:
    """SSE transport endpoint for MCP protocol (auth required)."""
    return await handle_sse_connection(slug, request)


@router.post("/mcp/v1/{slug}/message", dependencies=[Depends(authenticate_mcp_request)])
async def mcp_message_endpoint(
    slug: str,
    request: Request,
    session_id: str | None = None,
) -> JSONResponse:
    """Message endpoint for SSE transport (auth required)."""
    body: dict[str, Any] = await request.json()
    result = await handle_message(slug, session_id or "http", body)
    return JSONResponse(content=result)


@router.post("/mcp/v1/{slug}/", dependencies=[Depends(authenticate_mcp_request)])
async def mcp_http_endpoint(
    slug: str,
    request: Request,
) -> JSONResponse:
    """StreamableHTTP transport endpoint for MCP protocol (auth required)."""
    body: dict[str, Any] = await request.json()
    result = await handle_http_request(slug, body)
    return JSONResponse(content=result)


# Re-export the dependency under the canonical name for routers that
# already use `get_current_user` semantics.
get_current_user_required = authenticate_mcp_request
