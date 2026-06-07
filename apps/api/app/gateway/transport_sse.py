"""SSE (Server-Sent Events) transport for the MCP protocol.

Handles the SSE connection lifecycle for the MCP gateway.
# TODO(phase-2): Implement proper JSON-RPC message handling per MCP spec.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.gateway.tool_executor import execute_tool, get_tools_config


async def handle_sse_connection(
    slug: str,
    request: Request,
) -> StreamingResponse:
    """Handle an incoming SSE connection for an MCP server.

    Implements the MCP protocol over SSE:
    1. Sends an 'endpoint' event with the message endpoint URL
    2. Listens for JSON-RPC messages on the message endpoint
    3. For Phase 1, responds to initialize, tools/list, and tools/call

    # TODO(phase-2): Implement full JSON-RPC over SSE per MCP spec.
    # TODO(phase-2): Support StreamableHTTP transport in addition to SSE.
    """
    session_id = str(uuid.uuid4())

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send the endpoint event (message URL)
        endpoint_url = f"/mcp/v1/{slug}/message?session_id={session_id}"
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"

        # Send the initialize response
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": f"mcpforge-{slug}",
                    "version": "0.1.0",
                },
            },
        }
        yield f"event: message\ndata: {json.dumps(init_response)}\n\n"

        # Keep connection alive until client disconnects
        try:
            while True:
                if await request.is_disconnected():
                    break
                # Send heartbeat every 30 seconds
                yield ": heartbeat\n\n"
                await __import__("asyncio").sleep(30)
        except Exception:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def handle_message(
    slug: str,
    session_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Handle an incoming JSON-RPC message via the message endpoint.

    Args:
        slug: The server slug.
        session_id: The SSE session ID.
        body: The JSON-RPC request body.

    Returns:
        JSON-RPC response.
    """
    jsonrpc_id = body.get("id", 1)
    method = body.get("method", "")

    if method == "tools/list":
        tools = get_tools_config()
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "result": {
                "tools": tools,
            },
        }

    elif method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            result = await execute_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "result": result,
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "error": {
                    "code": -32603,
                    "message": str(e),
                },
            }

    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": f"mcpforge-{slug}",
                    "version": "0.1.0",
                },
            },
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }
