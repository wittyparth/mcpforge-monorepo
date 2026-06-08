"""Tests for the ToolGenerator service (F1 OpenAPI ingestion pipeline)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.services.tool_generator import ToolGenerator

# ── Inline models matching the full ToolDefinition from F1 spec §4.4 ──────────


class _ToolParam(BaseModel):
    """Matches spec doc's ToolParameter."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    in_: str = Field(default="query", alias="in")
    required: bool = False
    description: str = ""
    schema_alias: dict[str, Any] = Field(default_factory=dict, alias="schema")
    example: Any = None


class _ToolDef(BaseModel):
    """Matches spec doc's ToolDefinition (full version with all fields)."""

    name: str
    description: str = ""
    method: str = "GET"
    path: str = "/"
    tags: list[str] = []
    parameters: list[_ToolParam] = []
    request_body_schema: dict[str, Any] | None = None
    response_schemas: dict[str, Any] = {}
    security_requirements: list[dict[str, Any]] = []
    selected: bool = True


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestToolGenerator:
    """Suite for ToolGenerator.build_tools_config."""

    def test_empty_tools_returns_valid_config(self) -> None:
        """Empty input returns valid config with empty tools list."""
        gen = ToolGenerator()
        result = gen.build_tools_config([])
        assert result["version"] == 1
        assert result["generator"] == "spec_analyzer_v1"
        assert "generated_at" in result
        assert result["generated_at"].endswith("Z")
        assert result["tools"] == []

    def test_single_selected_get_tool(self) -> None:
        """Single selected GET tool produces correct config shape."""
        gen = ToolGenerator()
        tool = _ToolDef(
            name="list_users",
            description="List all users",
            method="GET",
            path="/users",
            tags=["users"],
        )
        result = gen.build_tools_config([tool])
        assert len(result["tools"]) == 1

        t = result["tools"][0]
        assert t["name"] == "list_users"
        assert t["description"] == "List all users"
        assert t["method"] == "GET"
        assert t["path"] == "/users"
        assert t["tags"] == ["users"]
        assert t["inputSchema"] == {"type": "object", "properties": {}, "required": []}
        assert t["request_body_schema"] is None
        assert t["response_schemas"] == {}
        assert t["security_requirements"] == []

    def test_deselected_tool_excluded(self) -> None:
        """Single deselected tool is excluded from output."""
        gen = ToolGenerator()
        tool = _ToolDef(
            name="delete_user",
            description="Delete a user",
            method="DELETE",
            path="/users/{id}",
            selected=False,
        )
        result = gen.build_tools_config([tool])
        assert len(result["tools"]) == 0

    def test_params_combined_in_input_schema(self) -> None:
        """Path, query, and header params are combined into inputSchema."""
        gen = ToolGenerator()
        tool = _ToolDef(
            name="get_user",
            method="GET",
            path="/users/{id}",
            parameters=[
                _ToolParam(
                    name="id",
                    in_="path",
                    required=True,
                    schema_={"type": "string"},
                    description="User ID",
                ),
                _ToolParam(
                    name="fields",
                    in_="query",
                    required=False,
                    schema_={"type": "string"},
                    description="Fields to return",
                ),
                _ToolParam(
                    name="X-Custom",
                    in_="header",
                    required=False,
                    schema_={"type": "string"},
                    description="Custom header",
                ),
            ],
        )
        result = gen.build_tools_config([tool])
        t = result["tools"][0]
        schema = t["inputSchema"]

        assert "id" in schema["properties"]
        assert schema["properties"]["id"]["type"] == "string"
        assert schema["properties"]["id"]["description"] == "User ID"

        assert "fields" in schema["properties"]
        assert "X-Custom" in schema["properties"]

        assert schema["required"] == ["id"]

    def test_body_params_prefixed(self) -> None:
        """Body params are prefixed with ``body_`` and merged into required."""
        gen = ToolGenerator()
        tool = _ToolDef(
            name="create_user",
            method="POST",
            path="/users",
            parameters=[],
            request_body_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "User's name"},
                    "email": {"type": "string", "description": "User's email"},
                },
                "required": ["name"],
            },
        )
        result = gen.build_tools_config([tool])
        t = result["tools"][0]
        schema = t["inputSchema"]

        assert "body_name" in schema["properties"]
        assert schema["properties"]["body_name"]["type"] == "string"
        assert schema["properties"]["body_name"]["description"] == "User's name"

        assert "body_email" in schema["properties"]

        assert "body_name" in schema["required"]
        assert "body_email" not in schema["required"]

    def test_customizations_rename_tool(self) -> None:
        """Tool renamed via customizations appears with the new name."""
        gen = ToolGenerator()
        tool = _ToolDef(name="get_users", method="GET", path="/users", selected=True)
        customizations = {"get_users": {"name": "list_all_users"}}
        result = gen.build_tools_config([tool], customizations)
        assert result["tools"][0]["name"] == "list_all_users"

    @pytest.mark.parametrize(
        ("method", "read_only", "destructive", "idempotent"),
        [
            ("GET", True, False, True),
            ("HEAD", True, False, True),
            ("OPTIONS", True, False, True),
            ("DELETE", False, True, True),
            ("PUT", False, False, True),
            ("POST", False, False, False),
            ("PATCH", False, False, False),
        ],
    )
    def test_annotations_per_method(
        self,
        method: str,
        read_only: bool,
        destructive: bool,
        idempotent: bool,
    ) -> None:
        """Annotations are correctly set per HTTP method."""
        gen = ToolGenerator()
        tool = _ToolDef(name=f"test_{method.lower()}", method=method, path="/test")
        result = gen.build_tools_config([tool])
        ann = result["tools"][0]["annotations"]
        assert ann["readOnlyHint"] == read_only, f"readOnlyHint for {method}"
        assert ann["destructiveHint"] == destructive, f"destructiveHint for {method}"
        assert ann["idempotentHint"] == idempotent, f"idempotentHint for {method}"
        assert ann["openWorldHint"] is False

    def test_request_body_schema_only_for_write_methods(self) -> None:
        """request_body_schema is present for POST, None for GET."""
        gen = ToolGenerator()
        body = {"type": "object", "properties": {"name": {"type": "string"}}}

        post_tool = _ToolDef(
            name="create", method="POST", path="/items", request_body_schema=body
        )
        get_tool = _ToolDef(
            name="list", method="GET", path="/items", request_body_schema=body
        )
        put_tool = _ToolDef(
            name="update", method="PUT", path="/items/{id}", request_body_schema=body
        )
        patch_tool = _ToolDef(
            name="partial", method="PATCH", path="/items/{id}", request_body_schema=body
        )
        delete_tool = _ToolDef(
            name="remove", method="DELETE", path="/items/{id}", request_body_schema=body
        )

        result = gen.build_tools_config([
            post_tool, get_tool, put_tool, patch_tool, delete_tool,
        ])
        assert result["tools"][0]["request_body_schema"] == body  # POST
        assert result["tools"][1]["request_body_schema"] is None  # GET
        assert result["tools"][2]["request_body_schema"] == body  # PUT
        assert result["tools"][3]["request_body_schema"] == body  # PATCH
        assert result["tools"][4]["request_body_schema"] is None  # DELETE

    def test_output_json_serializable(self) -> None:
        """The result dict is JSON-serializable without custom encoders."""
        gen = ToolGenerator()
        tool = _ToolDef(name="test", method="GET", path="/test")
        result = gen.build_tools_config([tool])
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["tools"][0]["name"] == "test"
