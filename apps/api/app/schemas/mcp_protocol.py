"""Pydantic schemas for MCP JSON-RPC protocol messages.

Defines the JSON-RPC 2.0 request/response types used by MCP (Model Context
Protocol) servers.  Every message between an MCP host and an MCP server
conforms to one of these shapes.

Reference: JSON-RPC 2.0 Specification (https://www.jsonrpc.org/specification)
and MCP Specification (https://spec.modelcontextprotocol.io).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class JSONRPCRequest(BaseModel):
    """A JSON-RPC 2.0 request object (carries an ``id`` and expects a response).

    Attributes:
        jsonrpc: Protocol version identifier (must be ``"2.0"``).
        id: Request identifier echoed back in the response.  ``str`` or ``int``.
        method: Name of the method to invoke.
        params: Optional structured parameters for the method.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
            }
        }
    )

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: str
    params: dict[str, Any] | None = None


class JSONRPCNotification(BaseModel):
    """A JSON-RPC 2.0 notification (no ``id`` — no response expected).

    Attributes:
        jsonrpc: Protocol version identifier (must be ``"2.0"``).
        method: Name of the method to invoke.
        params: Optional structured parameters for the method.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        }
    )

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: dict[str, Any] | None = None


class JSONRPCSuccessResponse(BaseModel):
    """A JSON-RPC 2.0 success response.

    Attributes:
        jsonrpc: Protocol version identifier (must be ``"2.0"``).
        id: The request identifier this response corresponds to.
        result: The result of the method invocation.  Any JSON-compatible value.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"tools": []},
            }
        }
    )

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    result: dict[str, Any] | list[Any] | str | int | float | bool | None = None


class JSONRPCError(BaseModel):
    """A JSON-RPC 2.0 error object embedded in an error response.

    Attributes:
        code: Integer error code.  Standard JSON-RPC codes are in the range
            -32700 to -32000; MCP-specific codes occupy -32001 to -32099.
        message: Short, human-readable description of the error.
        data: Optional structured payload providing additional context.
    """

    code: int
    message: str
    data: dict[str, Any] | None = None


class JSONRPCErrorResponse(BaseModel):
    """A JSON-RPC 2.0 error response.

    Attributes:
        jsonrpc: Protocol version identifier (must be ``"2.0"``).
        id: The request identifier this response corresponds to.  May be
            ``None`` if the request could not be parsed (e.g. parse error).
        error: The structured error object.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                },
            }
        }
    )

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None
    error: JSONRPCError


class MCPErrorCode:
    """JSON-RPC error codes for MCP protocol.

    Standard JSON-RPC 2.0 error codes occupy ``-32700`` to ``-32000``.
    MCP-specific server error codes occupy ``-32001`` to ``-32099``.

    Usage::

        from app.schemas.mcp_protocol import MCPErrorCode

        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": MCPErrorCode.TOOL_NOT_FOUND,
                "message": "Tool not found: echo",
            },
        }
    """

    # ── JSON-RPC 2.0 standard errors ────────────────────────────────
    PARSE_ERROR: int = -32700
    """Invalid JSON was received by the server."""

    INVALID_REQUEST: int = -32600
    """The JSON sent is not a valid Request object."""

    METHOD_NOT_FOUND: int = -32601
    """The method does not exist / is not available."""

    INVALID_PARAMS: int = -32602
    """Invalid method parameter(s)."""

    INTERNAL_ERROR: int = -32603
    """Internal JSON-RPC error."""

    # ── MCP-specific server errors (-32001 to -32099) ───────────────
    TOOL_NOT_FOUND: int = -32001
    """The requested tool is not available on this server."""

    UPSTREAM_ERROR: int = -32002
    """The upstream API returned an error."""

    RATE_LIMIT_EXCEEDED: int = -32003
    """The server or upstream rate-limited the request."""

    SERVER_DISABLED: int = -32004
    """The MCP server has been disabled by the owner or an admin."""

    SSRF_BLOCKED: int = -32005
    """The request URL was blocked by the SSRF guard."""

    CREDENTIAL_ERROR: int = -32006
    """Missing or invalid credentials for the upstream API."""

    TIMEOUT: int = -32007
    """The upstream request timed out."""
