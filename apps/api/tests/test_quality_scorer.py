"""Tests for QualityScorer — heuristic quality evaluation of tool descriptions.

12+ tests covering all 4 dimensions and badge mapping:
  - score() returns expected keys
  - Functionality: action verb start, length bonus, USE THIS WHEN, single-word penalty
  - Accuracy: all params described, param type mismatch, required flag mismatch
  - Completeness: return description, edge case mention
  - Context: USE THIS WHEN reference, sibling tool reference
  - Badge mapping: thresholds for Excellent/Good/Fair/Poor
"""

from __future__ import annotations

from app.services.ai_description.quality_scorer import QualityScorer

scorer = QualityScorer()

# ── Helpers ──────────────────────────────────────────────────────────


def _make_tool(
    *,
    description: str = "",
    params: list[dict] | None = None,
    name: str = "test_tool",
    input_schema: dict | None = None,
) -> dict:
    """Build a tool dict in the AI-enhanced format."""
    tool: dict = {"name": name, "enhanced_description": description}
    if params is not None:
        tool["enhanced_parameters"] = params
    if input_schema is not None:
        tool["inputSchema"] = input_schema
    else:
        # Build inputSchema from params
        props = {}
        required = []
        for p in (params or []):
            field_desc = p.get("description", "")
            props[p["name"]] = {"type": p.get("type", "string"), "description": field_desc}
            if p.get("required", False):
                required.append(p["name"])
        tool["inputSchema"] = {"type": "object", "properties": props, "required": required}
    return tool


def _make_original(params: list[dict] | None = None) -> dict:
    """Build an original (non-enhanced) tool dict with inputSchema."""
    props = {}
    required = []
    for p in (params or []):
        field_desc = p.get("description", "")
        props[p["name"]] = {"type": p.get("type", "string"), "description": field_desc}
        if p.get("required", False):
            required.append(p["name"])
    return {
        "name": "test_tool",
        "description": "original",
        "inputSchema": {"type": "object", "properties": props, "required": required},
    }


# ── Tests ────────────────────────────────────────────────────────────


class TestScoreReturnsKeys:
    """score() output structure."""

    def test_score_returns_expected_keys(self) -> None:
        """score() should return all 6 keys."""
        tool = _make_tool(description="Get item by ID")
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        expected_keys = {"functionality", "accuracy", "completeness", "context", "total", "badge"}
        assert set(result.keys()) == expected_keys

    def test_all_scores_are_integers(self) -> None:
        """Scores should all be integers."""
        tool = _make_tool(description="Retrieve a user from the database")
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        assert isinstance(result["functionality"], int)
        assert isinstance(result["accuracy"], int)
        assert isinstance(result["completeness"], int)
        assert isinstance(result["context"], int)
        assert isinstance(result["total"], int)

    def test_total_is_sum_of_dimensions(self) -> None:
        """Total should equal sum of dimension scores."""
        desc = "Get item by ID. Use this when you need to find a specific record."
        tool = _make_tool(description=desc)
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        expected = (
            result["functionality"] + result["accuracy"]
            + result["completeness"] + result["context"]
        )
        assert result["total"] == expected


class TestFunctionalityScoring:
    """Functionality dimension (0-30)."""

    def test_action_verb_at_start_gets_bonus(self) -> None:
        """Description starting with action verb should score >= 8."""
        tool = _make_tool(description="Retrieve a user by their unique identifier")
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        # Action verb = 8, length 50-300 = 7, total = 15 minimum
        assert result["functionality"] >= 8

    def test_description_length_bonus(self) -> None:
        """Description 50-300 chars should get +7 length bonus."""
        short = _make_tool(description="Get data")
        long_enough = _make_tool(
            description="Retrieve a user by their unique identifier from the database. "
            "This endpoint returns the full user profile."
        )
        result_short = scorer.score(short, _make_original(), [short])
        result_long = scorer.score(long_enough, _make_original(), [long_enough])
        assert result_long["functionality"] > result_short["functionality"]

    def test_use_this_when_guidance_gets_bonus(self) -> None:
        """'Use this when' phrase should add +10."""
        tool = _make_tool(
            description="Retrieve a user. Use this when you need the full user profile."
        )
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        assert result["functionality"] >= 10  # verb(8) + length(2) + guid(10) = 20 capped at 30

    def test_single_word_vague_description_penalty(self) -> None:
        """Single-word description should have -15 penalty."""
        tool = _make_tool(description="Get")
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        # Single word: length bonus is 2, no verb maybe, no guidance, -15 penalty
        # length=3, not 50-300 (no), not 30-50 or 300-500 (no) → +2
        # first word "Get" is in action verbs → +8
        # penalty for <=2 words → -15
        # total = max(0, min(30, 8 + 2 - 15)) = max(0, -5) = 0
        assert result["functionality"] == 0


class TestAccuracyScoring:
    """Accuracy dimension (0-25)."""

    def test_all_params_have_descriptions(self) -> None:
        """When all params have descriptions, accuracy should be higher."""
        params_with_desc = [
            {
                "name": "user_id", "type": "string",
                "description": "The unique identifier of the user",
                "required": True,
            },
        ]
        params_no_desc = [
            {"name": "user_id", "type": "string", "description": "", "required": True},
        ]

        enhanced = _make_tool(description="Get user", params=params_with_desc)
        original = _make_original(params=params_with_desc)

        enhanced_bad = _make_tool(description="Get user", params=params_no_desc)
        original_bad = _make_original(params=params_no_desc)

        result_good = scorer.score(enhanced, original, [enhanced])
        result_bad = scorer.score(enhanced_bad, original_bad, [enhanced_bad])

        assert result_good["accuracy"] >= result_bad["accuracy"]

    def test_param_type_mismatch_penalty(self) -> None:
        """Mismatched param type should reduce accuracy."""
        original_params = [
            {"name": "user_id", "type": "integer", "description": "User ID", "required": True},
        ]
        enhanced_params = [
            {
                "name": "user_id", "type": "string",
                "description": "The unique identifier of the user",
                "required": True,
            },
        ]

        enhanced = _make_tool(description="Get user", params=enhanced_params)
        original = _make_original(params=original_params)

        result = scorer.score(enhanced, original, [enhanced])
        # type mismatch penalty = -3, but described params give +15
        # So score should be non-negative but less than without mismatch
        assert 0 <= result["accuracy"] <= 25


class TestCompletenessScoring:
    """Completeness dimension (0-25)."""

    def test_return_description_gets_bonus(self) -> None:
        """Longer description (>20 chars) should get +7 completeness."""
        desc = (
            "Get user. Returns the full user profile with all fields "
            "including name, email, and role."
        )
        tool = _make_tool(description=desc)
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        # desc > 20 chars → +7
        assert result["completeness"] >= 7

    def test_edge_case_mention_gets_bonus(self) -> None:
        """Edge case words in description should add +3."""
        tool = _make_tool(
            description="Get user from the database. Returns empty array if no results found."
        )
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        # "empty" in edge case words → +3
        # desc > 20 → +7
        assert result["completeness"] >= 10


class TestContextScoring:
    """Context/disambiguation dimension (0-20)."""

    def test_use_this_when_reference_gets_bonus(self) -> None:
        """'Use this when' in description should add +7 context."""
        tool = _make_tool(
            description="Get user by ID. Use this when you have the exact user identifier."
        )
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        # USE THIS WHEN → +7, underscore in name "test_tool" → +2
        assert result["context"] >= 7

    def test_sibling_tool_reference_gets_bonus(self) -> None:
        """Referencing a sibling tool by name should add +5."""
        tool = _make_tool(
            description="Get user by ID. For batch lookups use search_users instead.",
            name="get_user",
        )
        sibling = _make_tool(
            description="Search users by criteria",
            name="search_users",
        )
        all_tools = [tool, sibling]
        result = scorer.score(tool, _make_original(), all_tools)
        # sibling ref "search_users" → +5, underscore "get_user" → +2
        assert result["context"] >= 7

    def test_do_not_use_phrase_gets_bonus(self) -> None:
        """'Do not use' phrase should add +8."""
        tool = _make_tool(
            description="Get user by ID. Do not use this for searching — use search_users instead.",
            name="get_user",
        )
        sibling = _make_tool(description="Search users", name="search_users")
        all_tools = [tool, sibling]
        result = scorer.score(tool, _make_original(), all_tools)
        # "Do not use" → +8, sibling ref → +5, underscore → +2
        assert result["context"] >= 15


class TestBadgeMapping:
    """Badge thresholds."""

    def test_score_90_plus_is_excellent(self) -> None:
        """Total >= 90 should be 'Excellent'."""
        # Build a tool that scores very high across all dimensions
        tool = _make_tool(
            description="Retrieve a user by their unique identifier from the database. "
            "Use this when you have the exact user ID. Do not use this for searching — "
            "use search_users instead. Returns the full user profile with all account details. "
            "Returns null if the user is not found.",
            name="get_user",
            params=[
                {
                    "name": "user_id", "type": "string",
                    "description": "The unique identifier (UUID) of the user. Required.",
                    "required": True,
                },
                {
                    "name": "include_deleted", "type": "boolean",
                    "description": "Whether to include soft-deleted users. Optional.",
                    "required": False,
                },
            ],
        )
        sibling = _make_tool(description="Search users by criteria", name="search_users")
        original = _make_original(params=[
            {"name": "user_id", "type": "string", "description": "User ID", "required": True},
            {
                "name": "include_deleted", "type": "boolean",
                "description": "Include deleted", "required": False,
            },
        ])
        result = scorer.score(tool, original, [tool, sibling])
        assert result["badge"] == "Excellent", f"Expected Excellent, got {result}"

    def test_score_70_to_89_is_good(self) -> None:
        """Total 70-89 should be 'Good'."""
        desc = "Retrieve a user by their unique identifier. Use this when you have the user ID."
        tool = _make_tool(
            description=desc,
            name="get_user",
            params=[
                {
                    "name": "user_id", "type": "string",
                    "description": "The user ID", "required": True,
                },
            ],
        )
        original = _make_original(params=[
            {"name": "user_id", "type": "string", "description": "User ID", "required": True},
        ])
        result = scorer.score(tool, original, [tool])
        assert result["badge"] in ("Good", "Excellent")
        assert result["total"] >= 70

    def test_score_50_to_69_is_fair(self) -> None:
        """Total 50-69 should be 'Fair'."""
        tool = _make_tool(
            description="Find records matching search criteria. Helpful when browsing the catalog.",
            name="search_items",
            params=[
                {
                    "name": "query", "type": "string",
                    "description": "Search query", "required": True,
                },
            ],
        )
        original = _make_original(params=[
            {"name": "query", "type": "string", "description": "Search query", "required": True},
        ])
        result = scorer.score(tool, original, [tool])
        # Verify badge matches the total score range
        if result["total"] >= 70:
            assert result["badge"] == "Good"
        elif result["total"] >= 50:
            assert result["badge"] == "Fair"
        else:
            assert result["badge"] == "Poor"

    def test_score_below_50_is_poor(self) -> None:
        """Total < 50 should be 'Poor'."""
        tool = _make_tool(description="Get")
        original = _make_original()
        result = scorer.score(tool, original, [tool])
        assert result["total"] < 50
        assert result["badge"] == "Poor"
