"""Pydantic schemas for the AI Description Engine (F2)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Quality scoring ────────────────────────────────────────────────────────


class AIQualityScore(BaseModel):
    """4-dimension quality score for a single tool description (0-100 each)."""

    clarity: int = Field(..., ge=0, le=100)
    specificity: int = Field(..., ge=0, le=100)
    correctness: int = Field(..., ge=0, le=100)
    actionability: int = Field(..., ge=0, le=100)
    overall: int = Field(..., ge=0, le=100)

    @classmethod
    def from_components(
        cls, clarity: int, specificity: int, correctness: int, actionability: int
    ) -> AIQualityScore:
        overall = round((clarity + specificity + correctness + actionability) / 4)
        return cls(
            clarity=clarity,
            specificity=specificity,
            correctness=correctness,
            actionability=actionability,
            overall=overall,
        )


class AIImprovementItem(BaseModel):
    """A single concrete improvement the AI proposes for a description."""

    field: Literal["description", "input_schema", "name"]
    current: str
    proposed: str
    rationale: str


class AIEnhancedTool(BaseModel):
    """The AI's enhanced version of a single tool."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    original_description: str
    enhanced_description: str
    quality_score: AIQualityScore
    improvements: list[AIImprovementItem] = Field(default_factory=list)
    cost_cents: int = Field(..., description="Cost of enhancing this single tool, in cents")
    model: str = Field(..., description="LLM model used (e.g., 'deepseek-v4-flash')")


# ── Build pipeline ────────────────────────────────────────────────────────


class AIEnhancementRequest(BaseModel):
    """POST /api/v1/servers/{id}/tools/enhance body."""

    tool_names: list[str] | None = Field(
        default=None,
        description="If omitted, enhances all tools. Otherwise, only the named ones.",
    )
    force: bool = Field(
        default=False,
        description="If True, re-run even on tools that were already enhanced.",
    )


class BuildEvent(BaseModel):
    """A single event in the build SSE stream (F2)."""

    type: Literal[
        "build_started",
        "tool_enhancing",
        "tool_enhanced",
        "tool_failed",
        "build_completed",
        "error",
    ]
    server_id: UUID
    tool_name: str | None = None
    enhanced_tool: AIEnhancedTool | None = None
    error: str | None = None
    total_tools: int = 0
    completed_tools: int = 0
    failed_tools: int = 0
    cost_cents: int = 0
    timestamp: str
