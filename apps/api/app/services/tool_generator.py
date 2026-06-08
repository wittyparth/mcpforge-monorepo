"""Converts ToolDefinition list into MCP tools_config JSON dict.

This is the third step in the OpenAPI ingestion pipeline (F1):

    openapi_fetcher -> spec_analyzer -> tool_generator -> mcp_server

The tool_generator takes a curated list of ToolDefinition objects (from
spec_analyzer) and produces the canonical JSON dict stored in
mcp_servers.tools_config (a JSONB column).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas.openapi_spec import ToolDefinition


class ToolGenerator:
    """Converts a curated list of ToolDefinition into the canonical tools_config format."""

    def build_tools_config(
        self,
        tools: list[ToolDefinition],
        customizations: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build the canonical tools_config JSON dict.

        Args:
            tools: List of ToolDefinition instances from spec_analyzer.
            customizations: Optional dict keyed by tool name with overrides.
                Keys per entry: ``name``, ``description``, ``enabled``.

        Returns:
            JSON-serializable dict matching ``mcp_servers.tools_config`` format.

        The output format (stored as JSONB):

        .. code-block:: python

            {
                "version": 1,
                "generated_at": "<ISO8601 UTC with Z suffix>",
                "generator": "spec_analyzer_v1",
                "tools": [
                    {
                        "name": "search_products",
                        "description": "...",
                        "method": "GET",
                        "path": "/products/search",
                        "tags": ["products"],
                        "inputSchema": {...},
                        "annotations": {
                            "readOnlyHint": True,
                            "destructiveHint": False,
                            "idempotentHint": True,
                            "openWorldHint": False,
                        },
                        "request_body_schema": ...,
                        "response_schemas": ...,
                        "security_requirements": [...],
                    }
                ]
            }
        """
        config: dict[str, Any] = {
            "version": 1,
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "generator": "spec_analyzer_v1",
            "tools": [],
        }

        customizations = customizations or {}

        for tool in tools:
            # Skip deselected tools.
            if not getattr(tool, "selected", True):
                continue

            name = tool.name
            description = tool.description

            # Prefer the full ToolDefinition names (``method`` / ``path``)
            # but fall back to the current schema (``http_method`` / ``http_path``).
            method: str = tool.method if hasattr(tool, "method") else tool.http_method
            path: str = tool.path if hasattr(tool, "path") else tool.http_path

            # Fields on the full ToolDefinition (F1 spec §4.4) that may not
            # yet be on the schema file.  getattr with defaults keeps us
            # compatible with either version.
            tags: list[str] = getattr(tool, "tags", [])
            parameters: list[Any] = getattr(tool, "parameters", [])
            request_body_schema_raw: dict[str, Any] | None = getattr(
                tool, "request_body_schema", None
            )
            response_schemas: dict[str, Any] = getattr(tool, "response_schemas", {})
            security_requirements: list[dict[str, Any]] = getattr(
                tool, "security_requirements", []
            )

            # Apply user customizations (rename, etc.).
            tool_name = customizations.get(name, {}).get("name", name)

            input_schema = self._build_input_schema(parameters, request_body_schema_raw)
            annotations = self._build_annotations(method)

            # Only include request_body_schema for write methods.
            body_output: dict[str, Any] | None = None
            if method in {"POST", "PUT", "PATCH"}:
                body_output = request_body_schema_raw

            config["tools"].append({
                "name": tool_name,
                "description": description,
                "method": method,
                "path": path,
                "tags": tags,
                "inputSchema": input_schema,
                "annotations": annotations,
                "request_body_schema": body_output,
                "response_schemas": response_schemas,
                "security_requirements": security_requirements,
            })

        return config

    def _build_input_schema(
        self,
        parameters: list[Any],
        request_body_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build the JSON Schema ``inputSchema`` from tool parameters and body.

        Path/query/header/cookie params become top-level properties.  Body
        parameters are prefixed with ``body_`` to avoid collisions with URL
        params of the same name.

        Always returns at least ``{"type": "object", "properties": {}, "required": []}``.
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in parameters:
            # Accept both Pydantic models (via model_dump) and plain dicts.
            p: dict[str, Any] = param if isinstance(param, dict) else param.model_dump()
            p_name: str = p.get("name", "")
            if not p_name:
                continue

            # ``schema_`` is the Python-side name (aliased from ``schema``).
            p_schema: dict[str, Any] = p.get("schema_", p.get("schema", p.get("aliased_schema", p.get("schema_alias", {}))))
            properties[p_name] = {**p_schema, "description": p.get("description", "")}

            if p.get("example") is not None:
                properties[p_name]["example"] = p["example"]

            if p.get("required", False):
                required.append(p_name)

        # Merge body parameters with ``body_`` prefix.
        if request_body_schema:
            body_props: dict[str, Any] = request_body_schema.get("properties", {})
            body_required: list[str] = request_body_schema.get("required", [])
            for prop_name, prop_schema in body_props.items():
                prefixed = f"body_{prop_name}"
                properties[prefixed] = {
                    **prop_schema,
                    "description": prop_schema.get(
                        "description", f"Body parameter: {prop_name}"
                    ),
                }
                if prop_name in body_required:
                    required.append(prefixed)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    @staticmethod
    def _build_annotations(method: str) -> dict[str, bool]:
        """Build MCP-spec annotation hints based on the HTTP method."""
        return {
            "readOnlyHint": method in {"GET", "HEAD", "OPTIONS"},
            "destructiveHint": method == "DELETE",
            "idempotentHint": method in {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"},
            "openWorldHint": False,
        }
