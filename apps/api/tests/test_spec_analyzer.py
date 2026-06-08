"""Tests for SpecAnalyzer — extracts ToolDefinitions from OpenAPI specs.

15 tests covering:
  - Basic extraction, naming, selection defaults
  - Warning badges for missing operationId / description / tags
  - Name collision dedup
  - $ref resolution in parameters and responses
  - Circular $ref graceful handling
  - Edge cases: empty paths, missing paths, no requestBody

All spec fixtures are defined inline (no external files).
"""

from __future__ import annotations

import copy

from app.services.spec_analyzer import SpecAnalyzer

# ======================================================================
# Inline spec fixtures
# ======================================================================

SIMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "description": "Returns a list of all pets",
                "tags": ["pets"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "Max items",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "A list of pets",
                        "content": {
                            "application/json": {
                                "schema": {"type": "array", "items": {"type": "object"}},
                            },
                        },
                    },
                },
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "tags": ["pets"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                                "required": ["name"],
                            },
                        },
                    },
                },
                "responses": {201: {"description": "Created"}},
            },
        },
    },
}

FULL_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Full API", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List items",
                "description": "Returns all items",
                "tags": ["items"],
                "parameters": [
                    {
                        "name": "page",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "operationId": "createItem",
                "summary": "Create item",
                "tags": ["items"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                                "required": ["name"],
                            },
                        },
                    },
                },
                "responses": {"201": {"description": "Created"}},
            },
            "delete": {
                "operationId": "deleteItem",
                "summary": "Delete item",
                "tags": ["items"],
                "responses": {"204": {"description": "No content"}},
            },
        },
        "/items/{id}": {
            "get": {
                "operationId": "getItem",
                "summary": "Get item by ID",
                "description": "Returns a single item",
                "tags": ["items"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Item ID",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "An item",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Item"},
                            },
                        },
                    },
                },
            },
            "put": {
                "operationId": "updateItem",
                "summary": "Update item",
                "tags": ["items"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"200": {"description": "Updated"}},
            },
            "patch": {
                "operationId": "patchItem",
                "summary": "Patch item",
                "tags": ["items"],
                "responses": {"200": {"description": "Patched"}},
            },
        },
        "/health": {
            "get": {
                "operationId": "healthCheck",
                "summary": "Health check",
                "tags": ["system"],
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/admin/cleanup": {
            "delete": {
                "operationId": "cleanup",
                "summary": "Clean up resources",
                "tags": ["admin"],
                "responses": {"204": {"description": "Cleaned"}},
            },
        },
    },
    "components": {
        "schemas": {
            "Item": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["id", "name"],
            },
        },
    },
}

REF_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Ref API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List users",
                "tags": ["users"],
                "parameters": [
                    {"$ref": "#/components/parameters/LimitParam"},
                ],
                "responses": {
                    "200": {
                        "description": "Users list",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UserList"},
                            },
                        },
                    },
                },
            },
        },
        "/users/{id}": {
            "get": {
                "operationId": "getUser",
                "summary": "Get user",
                "tags": ["users"],
                "parameters": [
                    {"$ref": "#/components/parameters/UserIdParam"},
                ],
                "responses": {
                    "200": {
                        "description": "A user",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"},
                            },
                        },
                    },
                },
            },
        },
    },
    "components": {
        "schemas": {
            "User": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                "required": ["id"],
            },
            "UserList": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/User"},
            },
        },
        "parameters": {
            "LimitParam": {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "maximum": 100},
                "description": "Max results",
            },
            "UserIdParam": {
                "name": "id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "User ID",
            },
        },
    },
}

EDGE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Edge API", "version": "1.0.0"},
    "paths": {
        "/no-id": {
            "get": {
                # no operationId
                "summary": "No operationId here",
                "description": "This operation has no operationId",
                "tags": ["edge"],
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/no-desc": {
            "get": {
                "operationId": "noDesc",
                # no description, no summary
                "tags": ["edge"],
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/no-tags": {
            "get": {
                "operationId": "noTags",
                "summary": "Untagged operation",
                # no tags field
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}

COLLISION_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Collision API", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "fetch",
                "summary": "Get items",
                "tags": ["items"],
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/items/{id}": {
            "get": {
                "operationId": "fetch",
                "summary": "Get one item",
                "tags": ["items"],
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/other": {
            "get": {
                "operationId": "fetch",
                "summary": "Get other",
                "tags": ["items"],
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}

CIRCULAR_REF_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Circular", "version": "1.0.0"},
    "paths": {
        "/nodes": {
            "get": {
                "operationId": "listNodes",
                "summary": "List nodes",
                "tags": ["nodes"],
                "responses": {
                    "200": {
                        "description": "Nodes",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Node"},
                            },
                        },
                    },
                },
            },
        },
    },
    "components": {
        "schemas": {
            "Node": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "children": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Node"},
                    },
                },
            },
        },
    },
}

# ======================================================================
# Tests
# ======================================================================


class TestBasicExtraction:
    """Fundamental extraction behaviour."""

    def test_extracts_correct_number_of_tools(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        assert len(tools) == 2

    def test_name_uses_operation_id_when_present(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        names = {t.name for t in tools}
        assert "listPets" in names
        assert "createPet" in names

    def test_name_auto_generated_from_path_when_operation_id_missing(
        self,
    ) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(EDGE_SPEC)
        # /no-id has GET with no operationId → "get_no_id"
        no_id_tool = next(t for t in tools if t.path == "/no-id")
        assert no_id_tool.name == "get_no-id"

    def test_name_normalises_path_params(self) -> None:
        """Path parameters like {id} are stripped in auto-generated names."""
        name = SpecAnalyzer._name_from_path("get", "/users/{userId}/orders")
        assert name == "get_users_userId_orders"

    def test_method_is_capitalised(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        for tool in tools:
            assert tool.method in {"GET", "POST"}


class TestSelectionDefaults:
    """Default selected logic per method."""

    def test_get_tools_selected_by_default(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        get_tool = next(t for t in tools if t.method == "GET")
        assert get_tool.selected is True

    def test_delete_tools_not_selected_by_default(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(FULL_SPEC)
        delete_tools = [t for t in tools if t.method == "DELETE"]
        assert len(delete_tools) >= 1
        for d in delete_tools:
            assert d.selected is False

    def test_post_tools_selected_by_default(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(FULL_SPEC)
        post_tool = next(t for t in tools if t.method == "POST")
        assert post_tool.selected is True

    def test_put_tools_selected_by_default(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(FULL_SPEC)
        put_tool = next(t for t in tools if t.method == "PUT")
        assert put_tool.selected is True


class TestWarnings:
    """Warning badges on tools."""

    def test_missing_operation_id_warning(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(EDGE_SPEC)
        no_id_tool = next(t for t in tools if t.path == "/no-id")
        assert "missing_operation_id" in no_id_tool.warnings

    def test_no_description_warning(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(EDGE_SPEC)
        no_desc_tool = next(t for t in tools if t.operation_id == "noDesc")
        assert "no_description" in no_desc_tool.warnings

    def test_untagged_warning(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(EDGE_SPEC)
        no_tags_tool = next(t for t in tools if t.operation_id == "noTags")
        assert "untagged" in no_tags_tool.warnings

    def test_multiple_warnings_on_one_tool(self) -> None:
        """An operation missing both operationId and description gets both warnings."""
        spec = copy.deepcopy(SIMPLE_SPEC)
        # Remove operationId AND description from the GET /pets operation
        get_op = spec["paths"]["/pets"]["get"]
        del get_op["operationId"]
        del get_op["description"]
        del get_op["summary"]

        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(spec)
        # The only GET op with no operationId, no desc → /pets GET
        get_tool = next(t for t in tools if t.method == "GET" and t.path == "/pets")
        assert "missing_operation_id" in get_tool.warnings
        assert "no_description" in get_tool.warnings
        assert "untagged" not in get_tool.warnings  # still has tags


class TestNameCollision:
    """Duplicate tool names get suffixed."""

    def test_name_collision_appends_suffix(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(COLLISION_SPEC)
        names = [t.name for t in tools]
        # Three tools with operationId "fetch" → "fetch", "fetch_1", "fetch_2"
        assert names.count("fetch") == 1
        assert "fetch_1" in names
        assert "fetch_2" in names

    def test_name_collision_does_not_affect_unique_names(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        names = {t.name for t in tools}
        assert "listPets" in names
        assert "createPet" in names


class TestRefResolution:
    """$ref resolution in parameters and responses."""

    def test_ref_in_parameter_resolved(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(REF_SPEC)
        # /users GET has a $ref parameter → should be resolved to LimitParam
        users_tool = next(t for t in tools if t.operation_id == "listUsers")
        assert len(users_tool.parameters) == 1
        param = users_tool.parameters[0]
        assert param.name == "limit"
        assert param.in_ == "query"
        assert param.required is False
        assert param.aliased_schema.get("maximum") == 100

    def test_ref_in_path_parameter_resolved(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(REF_SPEC)
        user_tool = next(t for t in tools if t.operation_id == "getUser")
        assert len(user_tool.parameters) == 1
        param = user_tool.parameters[0]
        assert param.name == "id"
        assert param.in_ == "path"
        assert param.required is True
        assert param.aliased_schema.get("type") == "string"

    def test_ref_in_response_schema_resolved(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(REF_SPEC)
        user_tool = next(t for t in tools if t.operation_id == "getUser")
        response_schema = user_tool.response_schemas.get("200", {})
        # Should be the resolved User schema (not a $ref)
        assert response_schema.get("type") == "object"
        assert "id" in response_schema.get("properties", {})


class TestMetadataExtraction:
    """Tags, descriptions, parameters metadata."""

    def test_tags_extracted_from_operation(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(FULL_SPEC)
        health_tool = next(t for t in tools if t.operation_id == "healthCheck")
        assert "system" in health_tool.tags
        items_tool = next(t for t in tools if t.operation_id == "listItems")
        assert "items" in items_tool.tags

    def test_description_falls_back_to_summary(self) -> None:
        """When description is absent, description uses summary."""
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        post_tool = next(t for t in tools if t.operation_id == "createPet")
        # createPet has summary but no description
        assert post_tool.description == "Create a pet"

    def test_description_empty_when_neither_present(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(EDGE_SPEC)
        no_desc_tool = next(t for t in tools if t.operation_id == "noDesc")
        assert no_desc_tool.description == ""

    def test_original_operation_id_present(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        list_tool = next(t for t in tools if t.operation_id == "listPets")
        assert list_tool.original_operation_id == "listPets"

    def test_original_operation_id_none_when_missing(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(EDGE_SPEC)
        no_id_tool = next(t for t in tools if t.path == "/no-id")
        assert no_id_tool.original_operation_id is None


class TestCircularRefs:
    """Specs with circular $ref do not crash."""

    def test_circular_ref_does_not_crash(self) -> None:
        analyzer = SpecAnalyzer()
        # Should not raise; prance may handle it or fall back to raw spec
        tools = analyzer.extract_tools(CIRCULAR_REF_SPEC)
        assert len(tools) == 1
        assert tools[0].operation_id == "listNodes"
        # response_schemas may be resolved or empty depending on prance
        assert "200" in tools[0].response_schemas


class TestEmptyEdgeCases:
    """Edge cases: empty paths, no paths key, etc."""

    def test_empty_paths_returns_empty_list(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(
            {"openapi": "3.0.0", "info": {"title": "Empty"}, "paths": {}}
        )
        assert tools == []

    def test_no_paths_key_returns_empty_list(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools({"openapi": "3.0.0", "info": {"title": "No paths"}})
        assert tools == []

    def test_non_dict_path_item_skipped_gracefully(self) -> None:
        """If a path item is not a dict, it should be skipped without crash."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Bad"},
            "paths": {
                "/valid": {
                    "get": {
                        "operationId": "validOp",
                        "responses": {"200": {"description": "OK"}},
                    },
                },
                "/broken": "this is not a dict",
            },
        }
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(spec)
        assert len(tools) == 1
        assert tools[0].operation_id == "validOp"


class TestToolParameterModel:
    """ToolParameter model validation."""

    def test_parameter_required_flag(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(FULL_SPEC)
        # /items/{id} GET has a required path param "id"
        get_item_tool = next(t for t in tools if t.operation_id == "getItem")
        assert len(get_item_tool.parameters) >= 1
        id_param = next(p for p in get_item_tool.parameters if p.name == "id")
        assert id_param.required is True
        assert id_param.in_ == "path"

    def test_optional_query_parameter(self) -> None:
        analyzer = SpecAnalyzer()
        tools = analyzer.extract_tools(SIMPLE_SPEC)
        list_tool = next(t for t in tools if t.operation_id == "listPets")
        limit_param = next(p for p in list_tool.parameters if p.name == "limit")
        assert limit_param.required is False
        assert limit_param.in_ == "query"
        assert limit_param.description == "Max items"
