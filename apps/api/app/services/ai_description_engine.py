"""AI Description Engine orchestrator for MCPForge F2.

Enhances MCP tool descriptions via LLM, scores quality using heuristic
metrics (arxiv 2602.18914), and tracks concrete improvements.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, cast

from app.core.config import settings
from app.core.exceptions import AIDescriptionError
from app.core.llm_client import LLMClient
from app.core.logging import get_logger
from app.services.ai_description.prompts import (
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from app.services.ai_description.quality_scorer import (
    DO_NOT_USE_PATTERN,
    USE_THIS_WHEN_PATTERN,
    QualityScorer,
)

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE
)


class AIDescriptionEngine:
    """Orchestrator for enhancing MCP tool descriptions via AI."""

    def __init__(self) -> None:
        self.scorer = QualityScorer()

    async def enhance_tool(
        self,
        tool: dict[str, Any],
        all_tools: list[dict[str, Any]],
        spec_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Enhance a single tool description using the LLM.

        Builds a structured prompt with spec details, sibling context,
        and few-shot examples, calls the LLM, and processes the response.
        Raises AIDescriptionError on LLM or parse failure.
        """
        tool_name = tool.get("name", "")
        original_desc = tool.get("description", "")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            tool_name=tool_name,
            tool_description=original_desc,
            method=str(tool.get("method", "GET")),
            path=str(tool.get("path", "")),
            tags=", ".join(tool.get("tags", [])) or "None",
            parameters_formatted=self._format_parameters(tool),
            request_body_schema=(
                json.dumps(tool["request_body"], indent=2)
                if tool.get("request_body") else "None"
            ),
            response_schemas=(
                json.dumps(tool.get("responses", {}), indent=2) or "None"
            ),
            security_requirements=(
                json.dumps(tool.get("security", []), indent=2) or "None"
            ),
            sibling_tools_formatted=self._format_siblings(all_tools, tool_name),
            few_shot_examples=self._format_few_shot(),
        )

        messages: list[dict[str, str]] = []
        if spec_context is not None:
            messages.append({
                "role": "user",
                "content": (
                    "<spec_context>\n"
                    f"{json.dumps(spec_context, indent=2)}\n"
                    "</spec_context>"
                ),
            })
        messages.append({"role": "user", "content": user_prompt})

        response_format: dict[str, str] | None = None
        if settings.LLM_JSON_MODE:
            response_format = {"type": "json_object"}

        try:
            result = await LLMClient.chat_completion(
                messages=messages,
                system=SYSTEM_PROMPT,
                max_tokens=2000,
                temperature=0.0,
                response_format=response_format,
            )
        except Exception as exc:
            logger.error(
                "LLM call failed during tool enhancement",
                tool_name=tool_name,
                error=str(exc),
            )
            raise AIDescriptionError(
                message=f"LLM call failed for tool '{tool_name}': {exc}",
                field=tool_name,
            ) from exc

        try:
            parsed = self._parse_json_response(result["content"])
        except ValueError as exc:
            logger.error(
                "Failed to parse LLM JSON response",
                tool_name=tool_name,
                response=result["content"][:500],
                error=str(exc),
            )
            raise AIDescriptionError(
                message=f"Failed to parse response for tool '{tool_name}': {exc}",
                field=tool_name,
            ) from exc

        quality_score = self.scorer.score(parsed, tool, all_tools)
        improvements = self._compute_improvements(tool, parsed)
        cost_cents = LLMClient.calculate_cost_cents(
            result.get("usage", {}), result.get("model", "")
        )

        return {
            "name": tool_name,
            "original_description": original_desc,
            "original_parameters": self._normalize_parameters(tool.get("parameters", [])),
            "enhanced_name": parsed.get("enhanced_name"),
            "enhanced_description": parsed.get("enhanced_description", ""),
            "enhanced_parameters": self._normalize_parameters(
                parsed.get("enhanced_parameters", [])
            ),
            "enhanced_return_description": parsed.get("enhanced_return_description"),
            "quality_score": quality_score,
            "improvements": improvements,
            "cost_cents": round(cost_cents),
            "llm_usage": result.get("usage", {}),
            "model": result.get("model", ""),
            "provider": result.get("provider", ""),
            "enhanced_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

    @staticmethod
    def _parse_json_response(text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling code fences and surrounding text."""
        stripped = text.strip()
        match = _JSON_FENCE_RE.search(stripped)
        if match:
            try:
                return dict(json.loads(match.group(1).strip()))
            except json.JSONDecodeError:
                pass
        first, last = stripped.find("{"), stripped.rfind("}")
        if first != -1 and last > first:
            try:
                return dict(json.loads(stripped[first: last + 1]))
            except json.JSONDecodeError:
                pass
        try:
            return dict(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse JSON: {exc}. Preview: {stripped[:200]}") from exc

    @staticmethod
    def _format_siblings(all_tools: list[dict[str, Any]], exclude: str) -> str:
        """Format up to 20 sibling tools as markdown bullets."""
        siblings = [t for t in all_tools if t.get("name", "") != exclude][:20]
        if not siblings:
            return "No sibling tools."
        return "\n".join(
            f"- {t.get('name', 'unknown')}: {(t.get('description', '') or '')[:100]}"
            for t in siblings
        )

    @staticmethod
    def _format_parameters(tool: dict[str, Any]) -> str:
        """Format params as ``- name (type, required|optional): desc``
        from inputSchema, input_schema, or a direct parameters list."""
        params: list[dict[str, Any]] = []

        schema = tool.get("inputSchema") or tool.get("input_schema")
        if isinstance(schema, dict):
            props = schema.get("properties")
            if isinstance(props, dict):
                required: list[str] = schema.get("required", []) or []
                for n, p in props.items():
                    if isinstance(p, dict):
                        params.append({"name": n, "type": p.get("type", "string"),
                                       "required": n in required,
                                       "description": p.get("description", "")})

        if not params:
            raw = tool.get("parameters")
            if isinstance(raw, list):
                for p in raw:
                    if isinstance(p, dict) and p.get("name"):
                        params.append({"name": p["name"], "type": p.get("type", "string"),
                                       "required": bool(p.get("required", False)),
                                       "description": p.get("description", "")})

        if not params:
            return "No parameters."
        lines = (
            f"- {p['name']} ({p['type']}, "
            f"{'required' if p['required'] else 'optional'}): "
            f"{p['description'] or ''}"
            for p in params
        )
        return "\n".join(lines)

    @staticmethod
    def _format_few_shot() -> str:
        """Format FEW_SHOT_EXAMPLES into readable text for the prompt."""
        sections: list[str] = []
        for i, ex in enumerate(FEW_SHOT_EXAMPLES[:3], 1):
            example: dict[str, Any] = cast(dict[str, Any], ex)
            inp, out = example.get("input", {}), example.get("output", {})
            lines = [
                f"Example {i}:",
                f"  Original name: {inp.get('tool_name', '')}",
                f"  Original description: {inp.get('tool_description', '')}",
                f"  Enhanced name: {out.get('enhanced_name', '')}",
                f"  Enhanced description: {out.get('enhanced_description', '')}",
            ]
            for ep in (out.get("enhanced_parameters", []) or [])[:5]:
                ename = ep.get("name", "")
                edesc = (ep.get("description", "") or "")[:80]
                lines.append(f"    - {ename}: {edesc}")
            if out.get("enhanced_return_description"):
                lines.append(f"  Return description: {out['enhanced_return_description']}")
            qs = out.get("quality_score", {})
            lines.append(f"  Quality score: {qs.get('total', '')}/100 ({qs.get('badge', '')})")
            for imp in (out.get("improvements", []) or [])[:3]:
                lines.append(f"    - {imp}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    @staticmethod
    def _compute_improvements(
        original: dict[str, Any],
        enhanced: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Compute improvements across 6 dimensions using regex patterns."""
        improvements: list[dict[str, str]] = []
        on, en = original.get("name", ""), enhanced.get("enhanced_name")
        od, ed = original.get("description", ""), enhanced.get("enhanced_description", "")

        if en and en != on:
            improvements.append({"field": "renamed_tool", "current": on, "proposed": en,
                                 "rationale": f"Renamed '{on}' to '{en}'"})
        if ed and ed != od:
            improvements.append({
                "field": "rewrote_description",
                "current": "Original spec description",
                "proposed": "Enhanced description with guidance",
                "rationale": "Description rewritten with action verbs and disambiguation",
            })
        if not bool(USE_THIS_WHEN_PATTERN.search(od)) and bool(
            USE_THIS_WHEN_PATTERN.search(ed)
        ):
            improvements.append({
                "field": "added_when_to_use",
                "current": "No usage guidance",
                "proposed": "Added 'Use this when...' guidance",
                "rationale": "Helps LLM decide when to invoke this tool vs alternatives",
            })
        if not bool(DO_NOT_USE_PATTERN.search(od)) and bool(
            DO_NOT_USE_PATTERN.search(ed)
        ):
            improvements.append({
                "field": "added_when_not_to_use",
                "current": "No negative guidance",
                "proposed": "Added 'Do not use...' disambiguation",
                "rationale": "Prevents LLM from selecting this tool for wrong use cases",
            })
        ret = enhanced.get("enhanced_return_description")
        if ret and ret.strip():
            truncated = (ret[:100] + "...") if len(ret) > 100 else ret
            improvements.append({
                "field": "added_return_description",
                "current": "No return value description",
                "proposed": f"Added return description: {truncated}",
                "rationale": "Return descriptions reduce LLM uncertainty about tool output",
            })
        ep = enhanced.get("enhanced_parameters", [])
        if isinstance(ep, list) and any(p.get("description", "").strip() for p in ep):
            improvements.append({
                "field": "rewrote_parameters",
                "current": "Original parameters without enhanced descriptions",
                "proposed": f"{len(ep)} parameters with detailed descriptions",
                "rationale": "Enhanced parameter descriptions improve LLM accuracy",
            })
        return improvements

    @staticmethod
    def _normalize_parameters(
        parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Normalize params to canonical format: name, description, required, type, in."""
        result: list[dict[str, Any]] = []
        for param in parameters:
            name = param.get("name")
            if not name:
                continue
            result.append({
                "name": str(name),
                "description": str(param.get("description", "")),
                "required": bool(param.get("required", False)),
                "type": str(param.get("type", "string")),
                "in": str(param.get("in", "body")),
            })
        return result
