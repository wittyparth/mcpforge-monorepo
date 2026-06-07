"""WebSocket playground handler.

Provides a WebSocket endpoint for browser-based MCP testing.

Auth: clients pass the JWT either as a `?token=<jwt>` query parameter
(typical for the browser playground) or as a `Sec-WebSocket-Protocol`
subprotocol header. Cookies are not sent on WebSocket upgrade by
browsers, so we cannot rely on the `access_token` cookie here.

The token is validated ONCE on connection. A failed auth closes the
WebSocket with code 1008 (policy violation) and an error message
delivered as a single text frame.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.gateway.tool_executor import execute_tool, get_tools_config

router = APIRouter()


async def _authenticate_ws(token: str | None) -> str:
    """Validate the JWT from the WebSocket query string.

    Returns the user_id (UUID string) on success.
    Raises UnauthorizedError on failure (caller closes the socket).
    """
    if not token:
        raise UnauthorizedError("Missing token query parameter")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        return str(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


@router.websocket("/ws/playground/{slug}")
async def playground_websocket(
    websocket: WebSocket,
    slug: str,
    token: str | None = Query(default=None),
) -> None:
    """WebSocket endpoint for the MCP Playground (auth required)."""
    await websocket.accept()
    try:
        user_id = await _authenticate_ws(token)
    except UnauthorizedError as exc:
        await websocket.send_text(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 0,
                    "error": {"code": -32001, "message": exc.message},
                }
            )
        )
        await websocket.close(code=1008, reason=exc.message)
        return

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
