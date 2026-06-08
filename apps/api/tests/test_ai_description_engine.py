"""Tests for AIDescriptionEngine — orchestrator for AI tool description enhancement.

4+ tests covering:
  - _parse_json_response with raw JSON
  - _parse_json_response with ```json fences
  - _format_siblings excludes the current tool
  - _normalize_parameters adds missing fields
"""

from __future__ import annotations

from app.services.ai_description_engine import AIDescriptionEngine


class TestParseJsonResponse:
    """_parse_json_response handling of various LLM output formats."""

    def test_parse_raw_json(self) -> None:
        """Raw JSON (no fences) should parse correctly."""
        text = '{"enhanced_name": "get_user", "enhanced_description": "Retrieve a user"}'
        result = AIDescriptionEngine._parse_json_response(text)
        assert result["enhanced_name"] == "get_user"
        assert result["enhanced_description"] == "Retrieve a user"

    def test_parse_json_with_code_fences(self) -> None:
        """JSON wrapped in ```json fences should parse."""
        text = (
            '```json\n'
            '{"enhanced_name": "search_items", "enhanced_description": "Search items"}\n'
            '```'
        )
        result = AIDescriptionEngine._parse_json_response(text)
        assert result["enhanced_name"] == "search_items"

    def test_parse_json_with_plain_fences(self) -> None:
        """JSON wrapped in ``` (no language) fences should parse."""
        text = (
            '```\n'
            '{"enhanced_name": "create_item", "enhanced_description": "Create an item"}\n'
            '```'
        )
        result = AIDescriptionEngine._parse_json_response(text)
        assert result["enhanced_name"] == "create_item"

    def test_parse_json_with_surrounding_text(self) -> None:
        """JSON with text before/after (no fences) should extract the JSON part."""
        text = (
            "Here is the enhanced result:\n"
            '{"enhanced_name": "delete_item", "enhanced_description": "Delete an item"}\n'
            "Please review and let me know."
        )
        result = AIDescriptionEngine._parse_json_response(text)
        assert result["enhanced_name"] == "delete_item"

    def test_parse_empty_text_raises_value_error(self) -> None:
        """Empty text should raise ValueError."""
        import pytest

        with pytest.raises(ValueError, match="Could not parse JSON"):
            AIDescriptionEngine._parse_json_response("")


class TestFormatSiblings:
    """_format_siblings filtering."""

    def test_excludes_current_tool(self) -> None:
        """Current tool should be excluded from sibling list."""
        all_tools = [
            {"name": "get_user", "description": "Get a user"},
            {"name": "search_users", "description": "Search users"},
            {"name": "delete_user", "description": "Delete a user"},
        ]
        result = AIDescriptionEngine._format_siblings(all_tools, "get_user")
        assert "get_user" not in result
        assert "search_users" in result
        assert "delete_user" in result

    def test_no_siblings_returns_message(self) -> None:
        """When no other tools exist, returns 'No sibling tools.'."""
        result = AIDescriptionEngine._format_siblings(
            [{"name": "only_tool", "description": "Sole tool"}], "only_tool"
        )
        assert result == "No sibling tools."

    def test_empty_tools_list(self) -> None:
        """Empty tools list returns 'No sibling tools.'."""
        result = AIDescriptionEngine._format_siblings([], "anything")
        assert result == "No sibling tools."


class TestNormalizeParameters:
    """_normalize_parameters canonical format."""

    def test_adds_missing_fields(self) -> None:
        """Missing fields should get default values."""
        params = [
            {"name": "user_id", "type": "string"},
            # Missing type, required, in
            {"name": "email"},
        ]
        result = AIDescriptionEngine._normalize_parameters(params)
        assert len(result) == 2

        # First param has explicit type, default required/in
        assert result[0]["name"] == "user_id"
        assert result[0]["type"] == "string"
        assert result[0]["required"] is False
        assert result[0]["in"] == "body"

        # Second param gets all defaults
        assert result[1]["name"] == "email"
        assert result[1]["type"] == "string"
        assert result[1]["required"] is False
        assert result[1]["in"] == "body"

    def test_skips_params_without_name(self) -> None:
        """Params without a name should be skipped."""
        params = [
            {"name": "valid_param", "type": "string"},
            {"type": "integer"},  # no name
            {"name": "", "type": "string"},  # empty name
        ]
        result = AIDescriptionEngine._normalize_parameters(params)
        assert len(result) == 1
        assert result[0]["name"] == "valid_param"

    def test_preserves_explicit_values(self) -> None:
        """Explicit required/in values should be preserved."""
        params = [
            {
                "name": "user_id", "description": "The user ID",
                "required": True, "type": "string", "in": "path",
            },
        ]
        result = AIDescriptionEngine._normalize_parameters(params)
        assert result[0]["required"] is True
        assert result[0]["in"] == "path"
        assert result[0]["description"] == "The user ID"
