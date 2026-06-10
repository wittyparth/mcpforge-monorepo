"""Tool Dispatcher — builds HTTP requests from tool configs and executes them.

The ``ToolDispatcher`` orchestrates the full lifecycle of an MCP tool call:
credential decryption → auth header building → HTTP request construction →
SSRF check → HTTP execution (with retry) → response handling →
MCP response formatting.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.core.exceptions import InvalidParamsError, UpstreamError
from app.core.logging import get_logger
from app.gateway.auth_header_builder import AuthHeaderBuilder
from app.gateway.response_handler import ResponseHandler
from app.gateway.ssrf_guard import SSRFGuard

logger = get_logger(__name__)


class ToolDispatcher:
    """Orchestrates MCP tool call execution against upstream APIs.

    Builds HTTP requests from tool/server configs, validates them against
    SSRF rules, executes with retry logic, and formats results as MCP
    tool call response dicts.
    """

    def __init__(self) -> None:
        """Create a new ToolDispatcher with default component instances."""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0),
        )
        self.ssrf_guard = SSRFGuard()
        self.auth_builder = AuthHeaderBuilder()
        self.response_handler = ResponseHandler()

    async def dispatch(
        self,
        server_config: dict[str, Any],
        tool_config: dict[str, Any],
        arguments: dict[str, object],
        credential_value: str | None = None,
    ) -> dict[str, Any]:
        """Execute a tool call against the upstream API.

        Args:
            server_config: The server configuration dict (must include
                ``base_url`` and optionally ``auth_scheme`` /
                ``auth_header_name``).
            tool_config: The tool definition dict (must include ``name``,
                ``method``, ``path``, and optionally ``parameters``).
            arguments: The tool arguments from the MCP tool call.
            credential_value: Optional credential value for auth header
                construction.

        Returns:
            An MCP-formatted tool result dict with ``content`` list and
            ``isError`` flag.

        Raises:
            InvalidParamsError: If required inputs are missing.
            UpstreamError: If the upstream returns 5xx or a network error
                occurs.
            SSRFBlockedError: If the request URL is blocked by the SSRF
                guard.
        """
        tool_name = tool_config.get("name")
        if not tool_name:
            raise InvalidParamsError("Tool config missing 'name'")

        auth_headers: dict[str, str] = {}
        if credential_value is not None:
            auth_scheme = server_config.get("auth_scheme", "none")
            auth_header_name = server_config.get("auth_header_name")
            auth_headers = self.auth_builder.build(
                auth_scheme,
                credential_value,
                auth_header_name,
            )

        request = self._build_request(
            server_config,
            tool_config,
            arguments,
            auth_headers,
        )

        await self.ssrf_guard.assert_safe(str(request.url))

        response = await self._execute_with_retry(request)

        result = await self.response_handler.handle(response)

        status_code = result.status_code

        if result.type == "json":
            content_text = json.dumps(result.content, indent=2)
        elif result.type == "binary":
            content_text = (
                f"[Binary data: {result.mime_type}, "
                f"{result.response_size_bytes} bytes]\n"
                f"{result.content}"
            )
        else:
            content_text = str(result.content)

        if result.truncated:
            content_text = (
                f"[Response truncated to {result.response_size_bytes} bytes]\n"
                f"{content_text}"
            )

        mcp_result: dict[str, Any] = {
            "content": [
                {
                    "type": "text",
                    "text": content_text,
                },
            ],
            "isError": status_code >= 400,
        }

        if status_code >= 400:
            mcp_result["content"].append(
                {
                    "type": "text",
                    "text": f"Upstream returned HTTP {status_code}",
                },
            )

        return mcp_result

    def _build_request(
        self,
        server_config: dict[str, Any],
        tool_config: dict[str, Any],
        arguments: dict[str, object],
        auth_headers: dict[str, str],
    ) -> httpx.Request:
        """Build an ``httpx.Request`` from tool config and arguments.

        Args:
            server_config: Server configuration with ``base_url``.
            tool_config: Tool definition with ``method``, ``path``,
                and optional ``parameters``.
            arguments: The tool arguments to map to params / body.
            auth_headers: Authentication headers to include.

        Returns:
            A fully constructed ``httpx.Request`` ready to send.
        """
        base_url = server_config["base_url"].strip().rstrip("/")

        path: str = tool_config.get("path", "/")
        method: str = tool_config.get("method", "GET").upper()

        parameters: list[dict[str, Any]] = tool_config.get("parameters", [])
        enhanced_params: list[dict[str, Any]] = tool_config.get("enhanced_parameters", [])

        path_param_names: set[str] = set()
        query_param_names: set[str] = set()
        header_param_names: set[str] = set()

        # Infer path params from the URL template (e.g. {petId})
        import re as _re
        for match in _re.finditer(r"\{(\w+)\}", path):
            path_param_names.add(match.group(1))

        # Also check explicit parameters list for in=path/query/header
        for param_list in (parameters, enhanced_params):
            for param in param_list:
                param_name = param.get("name", "")
                param_in = param.get("in", "")
                if param_in == "path":
                    path_param_names.add(param_name)
                elif param_in == "query":
                    query_param_names.add(param_name)
                elif param_in == "header":
                    header_param_names.add(param_name)

        for param_name in path_param_names:
            if param_name in arguments:
                placeholder = f"{{{param_name}}}"
                path = path.replace(placeholder, str(arguments[param_name]))

        # For GET/HEAD/DELETE, everything non-path goes to query
        # For POST/PUT/PATCH, non-path params go to body
        is_query_method = method in ("GET", "HEAD", "DELETE")
        query_params: dict[str, str | int | float | bool] = {}
        body_params: dict[str, object] = {}
        for arg_name, arg_value in arguments.items():
            if arg_name in path_param_names or arg_name in header_param_names:
                continue
            if arg_name in query_param_names or is_query_method:
                if isinstance(arg_value, str | int | float | bool):
                    query_params[arg_name] = arg_value
                else:
                    query_params[arg_name] = str(arg_value)
            else:
                body_params[arg_name] = arg_value

        body_json: bytes | None = None
        if method in ("POST", "PUT", "PATCH") and body_params:
            body_json = json.dumps(body_params).encode()

        headers: dict[str, str] = {
            "User-Agent": "MCPForge-Gateway/1.0",
            "Accept": "application/json",
        }
        headers.update(auth_headers)
        if body_json is not None:
            headers["Content-Type"] = "application/json"

        full_url = f"{base_url}{path}"
        return httpx.Request(
            method=method,
            url=full_url,
            params=query_params or None,
            headers=headers,
            content=body_json,
        )

    async def _execute_with_retry(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        """Send the request with retry logic for rate-limited responses.

        Args:
            request: The ``httpx.Request`` to send.

        Returns:
            The ``httpx.Response`` from the upstream (first attempt or
            retry).

        Raises:
            UpstreamError: On timeout or network errors.
        """
        try:
            response = await self.client.send(request)
        except httpx.TimeoutException:
            logger.warning("upstream request timed out")
            raise UpstreamError("Request timed out after 5 seconds") from None
        except httpx.RequestError as e:
            logger.warning("upstream network error", error_type=type(e).__name__)
            raise UpstreamError(f"Network error: {type(e).__name__}") from None

        if response.status_code == 429:
            logger.warning(
                "rate limited by upstream, retrying after 1s",
            )
            await asyncio.sleep(1)
            response = await self.client.send(request)

        return response
