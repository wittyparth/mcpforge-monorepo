"""JSON-RPC error response helpers for the MCP Gateway.

Every function in this module returns a *complete* JSON-RPC 2.0 error
response dictionary — ready to be serialised and sent over the wire.
They do **not** raise exceptions; the caller decides whether to raise,
return, or log.

Import pattern::

    from app.gateway.errors import tool_not_found_error, upstream_error

    # In a handler:
    return JSONResponse(
        content=tool_not_found_error(request_id, tool_name),
        status_code=404,
    )
"""

from __future__ import annotations

from typing import Any

from app.schemas.mcp_protocol import MCPErrorCode


def _error_dict(
    request_id: str | int | None,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard JSON-RPC 2.0 error response dict.

    This is a private helper shared by all public error functions below.
    """
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if data is not None:
        error["data"] = data

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error,
    }


def tool_not_found_error(
    request_id: str | int | None,
    tool_name: str,
) -> dict[str, Any]:
    """The requested tool is not available on this server.

    Returns a JSON-RPC error with code ``-32001``.
    """
    return _error_dict(
        request_id,
        MCPErrorCode.TOOL_NOT_FOUND,
        f"Tool not found: {tool_name}",
    )


def upstream_error(
    request_id: str | int | None,
    exc_or_message: Exception | str,
) -> dict[str, Any]:
    """The upstream API returned an error.

    Accepts either an ``Exception`` (whose ``str()`` is used as the
    message) or a plain string.  Returns code ``-32002``.

    The upstream URL or internal details are intentionally **not**
    echoed in the message to avoid leaking internal infrastructure.
    """
    message = str(exc_or_message) if isinstance(exc_or_message, Exception) else exc_or_message
    return _error_dict(
        request_id,
        MCPErrorCode.UPSTREAM_ERROR,
        message,
    )


def rate_limit_error(
    request_id: str | int | None,
    retry_after: int,
) -> dict[str, Any]:
    """The server or upstream rate-limited the request.

    Includes ``retry_after_seconds`` in the error ``data`` field so
    clients can implement back-off.  Returns code ``-32003``.
    """
    return _error_dict(
        request_id,
        MCPErrorCode.RATE_LIMIT_EXCEEDED,
        "Rate limit exceeded",
        data={"retry_after_seconds": retry_after},
    )


def server_disabled_error(
    request_id: str | int | None,
) -> dict[str, Any]:
    """The MCP server has been disabled by the owner or an admin.

    Returns code ``-32004``.
    """
    return _error_dict(
        request_id,
        MCPErrorCode.SERVER_DISABLED,
        "Server is disabled",
    )


def ssrf_error(
    request_id: str | int | None,
    url: str,  # noqa: ARG001  — accepted for interface consistency, not echoed
) -> dict[str, Any]:
    """The request URL was blocked by the SSRF guard.

    The URL is **not** echoed in the error message to avoid leaking
    internal or malicious URLs back to the client.  Returns code
    ``-32005``.
    """
    return _error_dict(
        request_id,
        MCPErrorCode.SSRF_BLOCKED,
        "URL blocked by SSRF guard",
    )


def credential_error(
    request_id: str | int | None,
) -> dict[str, Any]:
    """Missing or invalid credentials for the upstream API.

    Returns code ``-32006``.
    """
    return _error_dict(
        request_id,
        MCPErrorCode.CREDENTIAL_ERROR,
        "Missing or invalid credentials",
    )


def timeout_error(
    request_id: str | int | None,
) -> dict[str, Any]:
    """The upstream request timed out.

    Returns code ``-32007``.
    """
    return _error_dict(
        request_id,
        MCPErrorCode.TIMEOUT,
        "Upstream request timed out",
    )


def method_not_found_error(
    request_id: str | int | None,
    method: str,
) -> dict[str, Any]:
    """The requested JSON-RPC method does not exist.

    Returns code ``-32601`` (standard JSON-RPC Method Not Found).
    """
    return _error_dict(
        request_id,
        MCPErrorCode.METHOD_NOT_FOUND,
        f"Method not found: {method}",
    )


def invalid_params_error(
    request_id: str | int | None,
    message: str,
) -> dict[str, Any]:
    """Invalid method parameter(s).

    Returns code ``-32602`` (standard JSON-RPC Invalid Params).
    """
    return _error_dict(
        request_id,
        MCPErrorCode.INVALID_PARAMS,
        message,
    )


def internal_error(
    request_id: str | int | None,
    message: str,
) -> dict[str, Any]:
    """Internal JSON-RPC error.

    Returns code ``-32603`` (standard JSON-RPC Internal Error).
    """
    return _error_dict(
        request_id,
        MCPErrorCode.INTERNAL_ERROR,
        message,
    )
