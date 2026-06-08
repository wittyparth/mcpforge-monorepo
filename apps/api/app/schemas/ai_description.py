"""Pydantic schemas for the AI Description Engine (F2).

Quality dimensions based on arxiv 2602.18914 research:
- Functionality (0-30): Does the description accurately convey what the tool does?
- Accuracy (0-25): Are parameter names and types correctly described?
- Completeness (0-25): Are all parameters described, including optionals?
- Context (0-20): Does it help an LLM decide when to use this vs alternatives?
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Enhancement pipeline ──────────────────────────────────────────────


class AIEnhancementRequest(BaseModel):
    """POST /api/v1/servers/{id}/tools/enhance body."""

    tool_names: list[str] | None = Field(
        default=None,
        description="If None, enhances all tools. Otherwise, only the named ones.",
    )
    force: bool = Field(
        default=False,
        description="If True, re-run even on tools that were already enhanced.",
    )


class AIEnhancementResponse(BaseModel):
    """Response returned immediately after submitting an enhancement job."""

    job_id: str = Field(..., description="Celery task ID for the enhancement job")
    estimated_cost_cents: int = Field(
        ..., description="Estimated cost in cents for the full enhancement run"
    )
    estimated_duration_seconds: int = Field(
        ..., description="Estimated duration in seconds for the full run"
    )
    remaining_credits: int | None = Field(
        default=None,
        description="AI enhancement credits remaining. None = unlimited (Pro tier).",
    )


class AIToolEnhancement(BaseModel):
    """The enhancement result for a single tool."""

    name: str = Field(..., description="Original tool name")
    original_description: str = Field(..., description="Original description from the spec")
    original_parameters: list[dict[str, object]] = Field(
        default_factory=list,
        description="Original parameter definitions as a list of dicts",
    )
    enhanced_name: str | None = Field(
        default=None,
        description="AI-suggested new tool name, or None if unchanged",
    )
    enhanced_description: str = Field(
        ..., description="AI-enhanced tool description"
    )
    enhanced_parameters: list[dict[str, object]] = Field(
        default_factory=list,
        description="AI-enhanced parameter definitions as a list of dicts",
    )
    enhanced_return_description: str | None = Field(
        default=None,
        description="AI-authored description of the return value / response",
    )
    quality_score: dict[str, object] = Field(
        default_factory=dict,
        description="Dict with keys: functionality, accuracy, completeness, context, total, badge",
    )
    improvements: list[dict[str, object]] = Field(
        default_factory=list,
        description="List of improvement descriptions with field, current, proposed, rationale",
    )
    cost_cents: int = Field(default=0, description="Cost of enhancing this single tool, in cents")
    model: str = Field(default="", description="LLM model used (e.g., 'deepseek-v4-flash')")
    enhanced_at: str = Field(default="", description="ISO 8601 timestamp of when this was enhanced")


class ToolAcceptRequest(BaseModel):
    """POST /api/v1/servers/{id}/tools/accept — accept/reject AI suggestions."""

    accepted_tools: list[str] = Field(
        ..., description="Tool names whose AI enhancements to accept"
    )
    rejected_tools: list[str] = Field(
        default_factory=list,
        description="Tool names whose AI enhancements to reject (keep original)",
    )
    custom_edits: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Manual overrides keyed by tool name, value is a dict of fields to set",
    )


# ── Build pipeline (SSE events) ───────────────────────────────────────


class BuildEvent(BaseModel):
    """A single event in the build SSE stream (F2)."""

    event: Literal[
        "connected",
        "start",
        "ai_progress",
        "tool_enhanced",
        "tool_failed",
        "ai_complete",
        "done",
        "error",
    ]
    server_id: str = Field(..., description="Server ID (UUID as string)")
    tool_name: str | None = Field(
        default=None,
        description="Tool name for tool_enhanced / tool_failed events",
    )
    progress: int = Field(
        default=0, description="Number of tools completed so far"
    )
    total: int = Field(
        default=0, description="Total number of tools to process"
    )
    quality_score: int | None = Field(
        default=None,
        description="Overall quality score (0-100) for ai_complete event",
    )
    cost_cents: int = Field(
        default=0, description="Cumulative cost in cents so far"
    )
    error: str | None = Field(
        default=None,
        description="Error message for error events",
    )
    timestamp: str = Field(
        default="", description="ISO 8601 timestamp of the event"
    )
