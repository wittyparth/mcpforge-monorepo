"""Heuristic quality scorer for AI-enhanced tool descriptions.

Scores tool descriptions across 4 dimensions (functionality, accuracy,
completeness, context) using regex/pattern-based heuristics — no LLM calls.

Reference: arxiv 2602.18914 — AI-Optimized Tool Descriptions for MCP.
"""

from __future__ import annotations

import re
from typing import Any, cast

# ── Module-level regex patterns ──────────────────────────────────────────

USE_THIS_WHEN_PATTERN = re.compile(
    (
        r"(?:"
        r"use\s+this\s+(?:when|for|to|if|in)"
        r"|when\s+you\s+need"
        r"|best\s+(?:used|for|when)"
        r"|this\s+(?:tool|function|endpoint)\s+(?:is\s+)?(?:for|used|designed)"
        r")"
    ),
    re.IGNORECASE,
)

DO_NOT_USE_PATTERN = re.compile(
    (
        r"(?:"
        r"do\s+not\s+(?:use|call|invoke|apply)"
        r"|don'?t\s+(?:use|call|invoke)"
        r"|avoid\s+(?:using|this)"
        r"|(?:not|never)\s+(?:for|intended|designed|meant)\s+(?:for|to|as)"
        r"|instead\s+(?:use|consider|prefer)"
        r")"
    ),
    re.IGNORECASE,
)

ACTION_VERBS: frozenset[str] = frozenset({
    "retrieve",
    "fetch",
    "create",
    "update",
    "delete",
    "remove",
    "list",
    "search",
    "get",
    "find",
    "lookup",
    "query",
    "post",
    "submit",
    "send",
    "upload",
    "download",
    "export",
    "generate",
    "build",
    "compute",
    "calculate",
    "transform",
    "validate",
    "verify",
    "check",
    "confirm",
    "approve",
    "cancel",
    "archive",
    "restore",
    "merge",
    "sync",
    "start",
    "stop",
    "pause",
    "resume",
    "enable",
    "disable",
    "register",
    "invite",
    "join",
    "leave",
    "assign",
})

EDGE_CASE_WORDS: frozenset[str] = frozenset({
    "empty",
    "null",
    "not found",
    "missing",
    "undefined",
    "optional",
})


class QualityScorer:
    """Heuristic quality scorer for AI-enhanced tool descriptions.

    Scores across 4 dimensions using regex/pattern-based heuristics,
    returning per-dimension scores, a total (0-100), and a badge.
    """

    def score(
        self,
        enhanced_tool: dict[str, Any],
        original_tool: dict[str, Any],
        all_tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Score an enhanced tool description across 4 dimensions.

        Args:
            enhanced_tool: The AI-enhanced tool dict (may have
                ``enhanced_description`` or ``description``).
            original_tool: The original tool dict from tools_config.
            all_tools: All tools in the server (for context scoring).

        Returns:
            Dict with keys: ``functionality`` (0-30), ``accuracy`` (0-25),
            ``completeness`` (0-25), ``context`` (0-20), ``total`` (0-100),
            and ``badge`` (Excellent/Good/Fair/Poor).
        """
        functionality = self._score_functionality(enhanced_tool, all_tools)
        accuracy = self._score_accuracy(enhanced_tool, original_tool)
        completeness = self._score_completeness(enhanced_tool, original_tool)
        context = self._score_context(enhanced_tool, all_tools)

        total = functionality + accuracy + completeness + context

        if total >= 90:
            badge = "Excellent"
        elif total >= 70:
            badge = "Good"
        elif total >= 50:
            badge = "Fair"
        else:
            badge = "Poor"

        return {
            "functionality": functionality,
            "accuracy": accuracy,
            "completeness": completeness,
            "context": context,
            "total": total,
            "badge": badge,
        }

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _get_description(tool: dict[str, Any]) -> str:
        """Extract description text from a tool dict."""
        return cast(str, tool.get("enhanced_description", tool.get("description", "")))

    @staticmethod
    def _get_params(tool: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract parameters from a tool dict as a list.

        Handles both ``inputSchema`` (tools_config) and ``input_schema``
        (alternative format). Returns empty list if no params found.
        """
        schema = tool.get("inputSchema", tool.get("input_schema", {}))
        if not isinstance(schema, dict):
            return []
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return []
        required_list: list[str] = schema.get("required", []) or []
        result: list[dict[str, Any]] = []
        for name, prop in properties.items():
            if not isinstance(prop, dict):
                continue
            entry: dict[str, Any] = {
                "name": name,
                "type": prop.get("type", "string"),
                "description": prop.get("description", ""),
                "required": name in required_list,
            }
            result.append(entry)
        return result

    # ── Dimension scorers ───────────────────────────────────────────

    def _score_functionality(
        self,
        tool: dict[str, Any],
        _all_tools: list[dict[str, Any]],
    ) -> int:
        """Score functionality dimension (0-30).

        Rewards:
        - Action verb as first word (+8)
        - Description 50-300 chars (+7), 30-50 or 300-500 (+4), else (+2)
        - USE THIS WHEN or guidance phrase (+10 or +5)
        - Penalty for single-word vague descriptions (-15)
        """
        desc = self._get_description(tool)
        if not desc:
            return 0

        score = 0

        # Action verb as first word of description
        stripped = desc.strip()
        if stripped:
            first_word = stripped.split(maxsplit=1)[0].lower().rstrip(".,!?:;\"'")
            if first_word in ACTION_VERBS:
                score += 8

        # Description length scoring
        length = len(desc)
        if 50 <= length <= 300:
            score += 7
        elif 30 <= length < 50 or 300 < length <= 500:
            score += 4
        else:
            score += 2

        # Guidance / "USE THIS WHEN" phrase
        if USE_THIS_WHEN_PATTERN.search(desc):
            score += 10
        else:
            desc_lower = desc.lower()
            if any(phrase in desc_lower for phrase in ("useful for", "helpful when", "use this")):
                score += 5

        # Penalty for single-word or two-word vague descriptions
        if len(stripped.split()) <= 2:
            score -= 15

        return max(0, min(30, score))

    def _score_accuracy(
        self,
        tool: dict[str, Any],
        original: dict[str, Any],
    ) -> int:
        """Score accuracy dimension (0-25).

        Rewards:
        - All parameters have descriptions (+15 proportional)
        - Descriptions >10 chars are detailed (+5 proportional)
        - Penalty per mismatched parameter type (-3 each)
        - Penalty per mismatched required flag (-2 each)
        """
        score = 0

        enhanced_params = self._get_params(tool)
        original_params = self._get_params(original)

        # All params have descriptions (proportional)
        if enhanced_params:
            described = sum(
                1 for p in enhanced_params if bool(p.get("description", "").strip())
            )
            score += round(15 * described / len(enhanced_params))

        # Detailed descriptions >10 chars (proportional)
        if enhanced_params:
            detailed = sum(
                1 for p in enhanced_params
                if len(p.get("description", "").strip()) > 10
            )
            score += round(5 * detailed / len(enhanced_params))

        # Build name-indexed lookups for cross-referencing
        enhanced_by_name: dict[str, dict[str, Any]] = {
            p["name"]: p for p in enhanced_params if p.get("name")
        }
        original_by_name: dict[str, dict[str, Any]] = {
            p["name"]: p for p in original_params if p.get("name")
        }

        # Penalty for mismatched parameter types
        for name, ep in enhanced_by_name.items():
            op = original_by_name.get(name)
            if op is not None and ep.get("type") != op.get("type"):
                score -= 3

        # Penalty for mismatched required flags
        for name, ep in enhanced_by_name.items():
            op = original_by_name.get(name)
            if op is not None and ep.get("required") != op.get("required"):
                score -= 2

        return max(0, min(25, score))

    def _score_completeness(
        self,
        tool: dict[str, Any],
        original: dict[str, Any],
    ) -> int:
        """Score completeness dimension (0-25).

        Rewards:
        - Same number of params as original (+10 proportional)
        - Optional params have descriptions (+8 proportional)
        - Description exists with sufficient detail (+7 if >20 chars, +3 else)
        - Edge case mention in description (+3)
        """
        score = 0

        enhanced_params = self._get_params(tool)
        original_params = self._get_params(original)

        # Same number of params as original (proportional)
        if original_params:
            ratio = len(enhanced_params) / len(original_params)
            score += round(10 * min(ratio, 1.0))

        # Optional params have descriptions
        optional_params = [p for p in enhanced_params if not p.get("required", True)]
        if optional_params:
            described = sum(
                1 for p in optional_params if bool(p.get("description", "").strip())
            )
            score += round(8 * described / len(optional_params))

        # Description exists with sufficient detail
        desc = self._get_description(tool)
        if len(desc) > 20:
            score += 7
        elif desc:
            score += 3

        # Edge case mention
        desc_lower = desc.lower()
        if any(phrase in desc_lower for phrase in EDGE_CASE_WORDS):
            score += 3

        return max(0, min(25, score))

    def _score_context(
        self,
        tool: dict[str, Any],
        all_tools: list[dict[str, Any]],
    ) -> int:
        """Score context/disambiguation dimension (0-20).

        Rewards:
        - "USE THIS WHEN" or similar guidance (+7)
        - "DO NOT USE" or disambiguation phrase (+8)
        - References a sibling tool by name (+5)
        - Name has prefix/suffix category hint via underscore (+2)
        """
        desc = self._get_description(tool)
        if not desc:
            return 0

        score = 0

        # "USE THIS WHEN" or similar contextual guidance
        if USE_THIS_WHEN_PATTERN.search(desc):
            score += 7

        # "DO NOT USE" or disambiguation
        if DO_NOT_USE_PATTERN.search(desc):
            score += 8

        # References a sibling tool by name
        tool_name = tool.get("name", "")
        for other in all_tools:
            other_name = other.get("name", "")
            if other_name and other_name != tool_name and other_name.lower() in desc.lower():
                score += 5
                break  # Only one reference needed

        # Has category/tag info in the name (underscore-delimited prefix)
        if "_" in tool_name:
            score += 2

        return max(0, min(20, score))
