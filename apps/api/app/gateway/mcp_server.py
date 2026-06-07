"""MCP Gateway endpoints.

Provides the MCP protocol endpoints for the hosted gateway.
# TODO(phase-2): split MCP gateway into separate service when traffic justifies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.gateway.transport_http import handle_http_request
from app.gateway.transport_sse import handle_message, handle_sse_connection

router = APIRouter()


@router.get("/mcp/v1/{slug}/health")
async def mcp_server_health(slug: str) -> dict[str, str]:
    """Health check for a specific MCP server."""
    return {
        "status": "ok",
        "slug": slug,
        "version": "0.1.0",
    }


@router.get("/mcp/v1/{slug}/sse")
async def mcp_sse_endpoint(
    slug: str,
    request: Request,
) -> StreamingResponse:
    """SSE transport endpoint for MCP protocol.

    Establishes an SSE connection and handles the MCP protocol lifecycle.
    """
    return await handle_sse_connection(slug, request)


@router.post("/mcp/v1/{slug}/message")
async def mcp_message_endpoint(
    slug: str,
    request: Request,
    session_id: str | None = None,
) -> JSONResponse:
    """Message endpoint for SSE transport.

    Receives JSON-RPC messages sent via POST during an SSE session.
    """
    body: dict[str, Any] = await request.json()
    result = await handle_message(slug, session_id or "http", body)
    return JSONResponse(content=result)


@router.post("/mcp/v1/{slug}/")
async def mcp_http_endpoint(
    slug: str,
    request: Request,
) -> JSONResponse:
    """StreamableHTTP transport endpoint for MCP protocol.

    For Phase 1, returns a single JSON-RPC response.
    # TODO(phase-2): Implement streaming response for StreamableHTTP.
    """
    body: dict[str, Any] = await request.json()
    result = await handle_http_request(slug, body)
    return JSONResponse(content=result)
