"""MCP Tool Executor — maps MCP tool calls to actual execution.

For Phase 1, this provides a hardcoded "echo" tool.
# TODO(phase-2): Implement real OpenAPI → tool mapping with HTTP request building.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationError

# Hardcoded echo tool definition for Phase 1
ECHO_TOOL: dict[str, Any] = {
    "name": "echo",
    "description": "Echoes back the input message. Useful for MCP gateway connectivity testing.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to echo back",
            }
        },
        "required": ["message"],
    },
}


# Phase 1 hardcoded tools list
HARDCODED_TOOLS = [ECHO_TOOL]


def get_tools_config() -> list[dict[str, Any]]:
    """Get the list of available tools for Phase 1.

    # TODO(phase-2): Read from server's tools_config in database.
    """
    return HARDCODED_TOOLS


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute a tool call.

    For Phase 1, only the "echo" tool is implemented.
    # TODO(phase-2): Look up server's base_url, build HTTP request, execute, return result.

    Args:
        tool_name: The name of the tool to execute.
        arguments: Tool arguments as a dict.

    Returns:
        MCP-formatted tool result with content list.

    Raises:
        ValidationError: If the tool is not found or arguments are invalid.
    """
    if tool_name == "echo":
        message = arguments.get("message", "")
        if not isinstance(message, str):
            raise ValidationError("Argument 'message' must be a string")

        return {
            "content": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        }

    # Tool not found
    from app.core.exceptions import NotFoundError

    raise NotFoundError(f"Tool '{tool_name}' not found")
