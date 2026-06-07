"""WebSocket playground handler.

Provides a WebSocket endpoint for browser-based MCP testing.
# TODO(phase-2): Implement full WebSocket ↔ MCP protocol bridge.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.gateway.tool_executor import execute_tool, get_tools_config

router = APIRouter()


@router.websocket("/ws/playground/{slug}")
async def playground_websocket(websocket: WebSocket, slug: str) -> None:
    """WebSocket endpoint for the MCP Playground.

    Accepts WebSocket connections and proxies MCP protocol messages
    to the tool executor. For Phase 1, supports:
    - tools/list
    - tools/call (echo tool only)

    # TODO(phase-2): Implement full MCP protocol bridge with
    #                real server lookup, auth, and HTTP proxying.
    """
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message: dict[str, Any] = json.loads(data)
            method = message.get("method", "")
            msg_id = message.get("id", 1)

            if method == "tools/list":
                tools = get_tools_config()
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": tools},
                }
                await websocket.send_text(json.dumps(response))

            elif method == "tools/call":
                params = message.get("params", {})
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                try:
                    result = await execute_tool(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": result,
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32603,
                            "message": str(e),
                        },
                    }
                await websocket.send_text(json.dumps(response))

            elif method == "ping":
                await websocket.send_text(
                    json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": "pong"})
                )

            else:
                await websocket.send_text(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "error": {
                                "code": -32601,
                                "message": f"Method '{method}' not found",
                            },
                        }
                    )
                )

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
