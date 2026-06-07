"""OpenAPI Spec Analyzer — extracts MCP tool definitions from a parsed spec.

Implements the core extraction logic described in §4.6 of
planning/features/02-FEATURE-OPENAPI-INGESTION.md.
"""

from __future__ import annotations

from typing import Any, Literal

from app.core.logging import get_logger
from app.schemas.openapi_spec import ToolDefinition, ToolParameter

MethodLiteral = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

# ── Shared method type helpers ─────────────────────────────────────
# Maps lowercase method names to their uppercase Literal equivalents.
# This is the only place where the literal values are enumerated.
_METHOD_UPPER: dict[str, MethodLiteral] = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "head": "HEAD",
    "options": "OPTIONS",
}

logger = get_logger(__name__)

# HTTP methods we recognise in an OpenAPI Path Item (ordered for determinism).
_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


class SpecAnalyzer:
    """Extracts MCP tool definitions from a parsed OpenAPI 3.x spec.

    Stateless — call ``extract_tools(spec_dict)`` with a raw or
    partially-resolved spec.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_tools(self, spec: dict[str, Any]) -> list[ToolDefinition]:
        """Extract all tool definitions from ``paths → operation``.

        Returns a list of :class:`ToolDefinition` with names, descriptions,
        parameters, warnings and default-selection already computed.
        """
        resolved = self._resolve_refs(spec)
        paths = resolved.get("paths", {})
        if not isinstance(paths, dict):
            logger.warning("spec_has_no_paths")
            return []

        tools: list[ToolDefinition] = []
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in _HTTP_METHODS:
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue
                tool = self._build_tool(path, method, operation, resolved)
                tools.append(tool)

        tools = self._assign_unique_names(tools)

        for tool in tools:
            tool.selected = self._default_selected(tool)

        logger.info("tools_extracted", total=len(tools))
        return tools

    # ------------------------------------------------------------------
    # Tool building
    # ------------------------------------------------------------------

    def _build_tool(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
        spec: dict[str, Any],
    ) -> ToolDefinition:
        """Turn a single OpenAPI operation into a ToolDefinition."""
        op_id = operation.get("operationId")
        name = op_id or self._name_from_path(method, path)

        params = self._extract_parameters(operation.get("parameters", []), spec)
        body_schema = self._extract_request_body_schema(operation.get("requestBody"), spec)
        response_schemas = self._extract_responses(operation.get("responses", {}), spec)

        warnings: list[str] = []
        if not op_id:
            warnings.append("missing_operation_id")
        if not (operation.get("description") or operation.get("summary")):
            warnings.append("no_description")
        if not operation.get("tags"):
            warnings.append("untagged")

        description = (operation.get("description") or operation.get("summary") or "").strip()

        return ToolDefinition(
            name=name,
            operation_id=op_id,
            original_operation_id=op_id,
            method=_METHOD_UPPER[method.lower()],
            path=path,
            summary=operation.get("summary"),
            description=description,
            input_schema={},
            tags=operation.get("tags", []),
            parameters=params,
            request_body_schema=body_schema,
            response_schemas=response_schemas,
            security_requirements=operation.get("security", []),
            selected=False,  # *computed* later in extract_tools
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Parameter / body / response extraction
    # ------------------------------------------------------------------

    def _extract_parameters(
        self,
        params: list[dict[str, Any]],
        spec: dict[str, Any],
    ) -> list[ToolParameter]:
        """Build ToolParameter list from an operation's ``parameters`` array.

        Skips parameters that cannot be resolved (broken ``$ref``).
        """
        result: list[ToolParameter] = []
        for param in params:
            if "$ref" in param:
                resolved = self._resolve_ref_obj(param, spec)
                if resolved is None:
                    logger.warning("parameter_ref_unresolvable", ref=param.get("$ref"))
                    continue
                param = resolved

            raw_in = param.get("in", "query")
            if raw_in not in ("path", "query", "header", "cookie"):
                raw_in = "query"

            try:
                tool_param = ToolParameter.model_construct(
                    name=param.get("name", ""),
                    in_=raw_in,
                    required=param.get("required", False),
                    description=param.get("description", ""),
                    schema_=param.get("schema", {}),
                    example=param.get("example") if "example" in param else None,
                )
            except Exception:
                logger.warning("parameter_skipped_invalid", name=param.get("name"))
                continue

            result.append(tool_param)

        return result

    def _extract_request_body_schema(
        self,
        request_body: Any,
        spec: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Extract the ``requestBody.content.application/json.schema`` dict."""
        if not isinstance(request_body, dict):
            return None
        content = request_body.get("content", {})
        if not isinstance(content, dict):
            return None
        json_content = content.get("application/json")
        if not isinstance(json_content, dict):
            return None
        schema = json_content.get("schema")
        if not isinstance(schema, dict):
            return None
        if "$ref" in schema:
            resolved = self._resolve_ref_obj(schema, spec)
            if resolved is not None:
                schema = resolved
        return schema if isinstance(schema, dict) else None

    def _extract_responses(
        self,
        responses: dict[str, Any],
        spec: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Extract JSON response schemas keyed by HTTP status code."""
        result: dict[str, dict[str, Any]] = {}

        for status_code, response in responses.items():
            if not isinstance(response, dict):
                continue
            if "$ref" in response:
                resolved = self._resolve_ref_obj(response, spec)
                if resolved is not None:
                    response = resolved
            if not isinstance(response, dict):
                continue

            content = response.get("content", {})
            if not isinstance(content, dict):
                continue
            json_content = content.get("application/json")
            if not isinstance(json_content, dict):
                result[str(status_code)] = {}
                continue
            schema = json_content.get("schema")
            if isinstance(schema, dict) and "$ref" in schema:
                resolved = self._resolve_ref_obj(schema, spec)
                if resolved is not None:
                    schema = resolved
            result[str(status_code)] = schema if isinstance(schema, dict) else {}

        return result

    # ------------------------------------------------------------------
    # Name helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _name_from_path(method: str, path: str) -> str:
        """Auto-generate a tool name from method + path.

        ``"GET /users/{id}/orders"`` → ``"get_users_id_orders"``
        """
        parts = [p.strip("{}") for p in path.split("/") if p]
        return f"{method.lower()}_{'_'.join(parts)}"

    @staticmethod
    def _assign_unique_names(tools: list[ToolDefinition]) -> list[ToolDefinition]:
        """Append ``_2``, ``_3``, … to duplicate tool names."""
        seen: dict[str, int] = {}
        for tool in tools:
            base = tool.name
            if base not in seen:
                seen[base] = 0
            else:
                seen[base] += 1
                tool.name = f"{base}_{seen[base]}"
        return tools

    @staticmethod
    def _default_selected(tool: ToolDefinition) -> bool:
        """Default selection: GET → ``True``, DELETE → ``False``, others ``True``."""
        return tool.method != "DELETE"

    # ------------------------------------------------------------------
    # $ref resolution
    # ------------------------------------------------------------------

    def _resolve_refs(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Resolve all ``$ref`` pointers in the spec.

        Tries ``prance.ResolvingParser`` first (fast, handles nested refs).
        Falls back to returning the raw spec with a warning.
        """
        try:
            from prance import ResolvingParser
            from prance.util import PranceError

            parser = ResolvingParser(
                spec_dict=spec,
                backend="openapi-spec-validator",
                strict=False,
                recursion_limit=256,
            )
            resolved: dict[str, Any] = parser.specification
            return resolved
        except ImportError:
            logger.warning("prance_not_available_using_raw_spec")
            return spec
        except PranceError as e:
            logger.warning("ref_resolution_prance_error", error=str(e))
            return spec
        except Exception as e:
            logger.warning("ref_resolution_failed", error=str(e))
            return spec

    def _resolve_ref_obj(
        self,
        obj: dict[str, Any],
        spec: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Resolve a single ``$ref`` dict against *spec*.

        Handles JSON Pointer notation: ``#/components/schemas/Pet``.
        Returns ``None`` when the pointer cannot be resolved.
        """
        ref = obj.get("$ref")
        if not ref or not isinstance(ref, str):
            return obj

        if not ref.startswith("#/"):
            logger.warning("ref_not_local_pointer", ref=ref)
            return None

        parts = ref[2:].split("/")
        current: Any = spec
        for part in parts:
            # JSON Pointer escape sequences: ~0 → ~, ~1 → /
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    logger.warning("ref_pointer_index_error", ref=ref, part=part)
                    return None
            else:
                return None
            if current is None:
                logger.warning("ref_pointer_not_found", ref=ref, part=part)
                return None

        # Resolve nested refs
        if isinstance(current, dict) and "$ref" in current:
            return self._resolve_ref_obj(current, spec)

        return current if isinstance(current, dict) else None
