"""Tests for AI description prompt templates (F2).

4+ tests covering:
  - SYSTEM_PROMPT is non-empty
  - USER_PROMPT_TEMPLATE has all expected placeholders
  - FEW_SHOT_EXAMPLES structure validation
  - Template formatting with sample data
"""

from __future__ import annotations

from app.services.ai_description.prompts import (
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)


class TestSystemPrompt:
    """SYSTEM_PROMPT shape and content."""

    def test_system_prompt_is_non_empty_string(self) -> None:
        """SYSTEM_PROMPT should be a non-empty string."""
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_contains_quality_dimensions(self) -> None:
        """SYSTEM_PROMPT should reference the four quality dimensions."""
        assert "FUNCTIONALITY" in SYSTEM_PROMPT
        assert "ACCURACY" in SYSTEM_PROMPT
        assert "COMPLETENESS" in SYSTEM_PROMPT
        assert "CONTEXT" in SYSTEM_PROMPT

    def test_system_prompt_mentions_json_output(self) -> None:
        """SYSTEM_PROMPT should instruct the LLM to output JSON."""
        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT


class TestUserPromptTemplate:
    """USER_PROMPT_TEMPLATE placeholders."""

    EXPECTED_PLACEHOLDERS = [
        "{tool_name}",
        "{tool_description}",
        "{method}",
        "{path}",
        "{tags}",
        "{parameters_formatted}",
        "{request_body_schema}",
        "{response_schemas}",
        "{security_requirements}",
        "{sibling_tools_formatted}",
        "{few_shot_examples}",
    ]

    def test_has_all_expected_placeholders(self) -> None:
        """USER_PROMPT_TEMPLATE should contain all expected placeholders."""
        for placeholder in self.EXPECTED_PLACEHOLDERS:
            assert placeholder in USER_PROMPT_TEMPLATE, (
                f"Missing placeholder: {placeholder}"
            )

    def test_format_with_sample_data(self) -> None:
        """USER_PROMPT_TEMPLATE.format() should work with sample data."""
        result = USER_PROMPT_TEMPLATE.format(
            tool_name="test_tool",
            tool_description="A test tool",
            method="GET",
            path="/test",
            tags="test,example",
            parameters_formatted="- param1 (string, required): desc",
            request_body_schema="None",
            response_schemas='{"200": {"description": "OK"}}',
            security_requirements="[]",
            sibling_tools_formatted="No sibling tools.",
            few_shot_examples="Example 1: ...",
        )
        assert isinstance(result, str)
        assert len(result) > 200
        assert "test_tool" in result
        assert "GET" in result
        assert "/test" in result

    def test_contains_quality_scoring_instructions(self) -> None:
        """Template should include instructions for quality scoring."""
        assert "quality_score" in USER_PROMPT_TEMPLATE
        assert "total" in USER_PROMPT_TEMPLATE
        assert "badge" in USER_PROMPT_TEMPLATE


class TestFewShotExamples:
    """FEW_SHOT_EXAMPLES shape and structure."""

    def test_is_list_of_three_dicts(self) -> None:
        """FEW_SHOT_EXAMPLES should be a list of 3 dicts."""
        assert isinstance(FEW_SHOT_EXAMPLES, list)
        assert len(FEW_SHOT_EXAMPLES) == 3

    def test_each_example_has_input_and_output_keys(self) -> None:
        """Each example should have ``input`` and ``output`` keys."""
        for i, example in enumerate(FEW_SHOT_EXAMPLES):
            assert isinstance(example, dict), f"Example {i} is not a dict"
            assert "input" in example, f"Example {i} missing 'input'"
            assert "output" in example, f"Example {i} missing 'output'"

    def test_input_has_tool_name_and_description(self) -> None:
        """Each example's input should have tool_name and tool_description."""
        for i, example in enumerate(FEW_SHOT_EXAMPLES):
            inp = example["input"]
            assert isinstance(inp, dict)
            assert "tool_name" in inp, f"Example {i} input missing tool_name"
            assert "tool_description" in inp, (
                f"Example {i} input missing tool_description"
            )

    def test_output_has_enhanced_fields(self) -> None:
        """Each example's output should have enhanced_* fields."""
        for i, example in enumerate(FEW_SHOT_EXAMPLES):
            out = example["output"]
            assert isinstance(out, dict)
            assert "enhanced_name" in out, f"Example {i} output missing enhanced_name"
            assert "enhanced_description" in out, (
                f"Example {i} output missing enhanced_description"
            )
            assert "quality_score" in out, f"Example {i} output missing quality_score"
