"""AI Description Engine service — prompt templates and orchestration (F2)."""

from app.services.ai_description.prompts import (
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from app.services.ai_description.quality_scorer import QualityScorer

__all__ = [
    "FEW_SHOT_EXAMPLES",
    "QualityScorer",
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
]
