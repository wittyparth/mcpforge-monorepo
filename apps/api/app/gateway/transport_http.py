"""StreamableHTTP transport for the MCP protocol.

Handles POST requests to /mcp/v1/{slug}/ for the StreamableHTTP transport.
# TODO(phase-2): Implement streaming response per MCP StreamableHTTP spec.
"""

from __future__ import annotations

from typing import Any

from app.gateway.transport_sse import handle_message


async def handle_http_request(
    slug: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Handle an incoming StreamableHTTP request.

    For Phase 1, delegates to the SSE message handler since we
    don't yet support streaming responses.

    # TODO(phase-2): Implement proper StreamableHTTP with streaming responses.
    """
    # For non-streaming requests, use the same handler as SSE messages
    return await handle_message(slug, "http", body)
