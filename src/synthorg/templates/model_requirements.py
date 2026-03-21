"""Structured model requirements and personality-based model affinity.

Provides :class:`ModelRequirement` for expressing what kind of LLM an
agent needs (tier, priority, context window, capabilities) and a
preset-keyed affinity mapping that supplies soft defaults when the
template does not specify full requirements.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.observability import get_logger
from synthorg.observability.events.template import (
    TEMPLATE_MODEL_REQUIREMENT_PARSED,
    TEMPLATE_MODEL_REQUIREMENT_RESOLVED,
)

logger = get_logger(__name__)

# Valid tier and priority literals.
ModelTier = Literal["large", "medium", "small"]
ModelPriority = Literal["quality", "balanced", "speed", "cost"]

_VALID_TIERS: frozenset[str] = frozenset({"large", "medium", "small"})


class ModelRequirement(BaseModel):
    """Structured model requirement for a template agent.

    Describes *what* an agent needs from an LLM without referencing a
    specific provider or model.  Used by the matching engine to select
    the best available model.

    Attributes:
        tier: Cost/capability tier (large = most capable, small = cheapest).
        priority: Optimization axis when multiple models match a tier.
        min_context: Minimum context window in tokens (0 = no minimum).
        capabilities: Future-use capability tags (e.g. ``"reasoning"``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tier: ModelTier = Field(default="medium", description="Cost/capability tier")
    priority: ModelPriority = Field(
        default="balanced",
        description="Optimization axis for model selection",
    )
    min_context: int = Field(
        default=0,
        ge=0,
        description="Minimum context window in tokens",
    )
    capabilities: tuple[str, ...] = Field(
        default=(),
        description="Future-use capability tags",
    )


def parse_model_requirement(raw: str | dict[str, Any]) -> ModelRequirement:
    """Parse a model requirement from a string tier or dict.

    Backward-compatible: accepts the legacy ``"medium"`` string format
    used by existing template YAML files as well as the new dict format.

    Args:
        raw: Either a tier string (``"large"``, ``"medium"``, ``"small"``)
            or a dict with ``ModelRequirement`` fields.

    Returns:
        Parsed ``ModelRequirement``.

    Raises:
        ValueError: If *raw* is a string not in the valid tier set.
        ValidationError: If *raw* is a dict with invalid fields.
    """
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key not in _VALID_TIERS:
            msg = f"Invalid model tier {raw!r}. Valid tiers: {sorted(_VALID_TIERS)}"
            raise ValueError(msg)
        result = ModelRequirement(tier=key)  # type: ignore[arg-type]
    else:
        result = ModelRequirement(**raw)

    logger.debug(
        TEMPLATE_MODEL_REQUIREMENT_PARSED,
        tier=result.tier,
        priority=result.priority,
    )
    return result


# ── Model affinity per personality preset ────────────────────
#
# Separated from the preset dicts because PersonalityConfig has
# extra="forbid".  These are soft defaults: template-level fields
# override them when both are specified.

_RAW_AFFINITY: dict[str, dict[str, Any]] = {
    # Leaders and strategists benefit from stronger reasoning.
    "visionary_leader": {"priority": "quality", "min_context": 100_000},
    "strategic_planner": {"priority": "quality"},
    "systems_thinker": {"priority": "quality"},
    # Analysts and guardians need precision.
    "methodical_analyst": {"priority": "quality"},
    "quality_guardian": {"priority": "quality"},
    "security_sentinel": {"priority": "quality"},
    "data_driven_optimizer": {"priority": "quality"},
    # Fast movers prefer speed.
    "eager_learner": {"priority": "speed"},
    "rapid_prototyper": {"priority": "speed"},
    "growth_hacker": {"priority": "speed"},
    # Cost-conscious executors.
    "disciplined_executor": {"priority": "cost"},
    # Balanced defaults for everyone else.
    "pragmatic_builder": {"priority": "balanced"},
    "creative_innovator": {"priority": "balanced"},
    "team_diplomat": {"priority": "balanced"},
    "independent_researcher": {"priority": "balanced"},
    "empathetic_mentor": {"priority": "balanced"},
    "communication_bridge": {"priority": "balanced"},
    "user_advocate": {"priority": "balanced"},
    "process_optimizer": {"priority": "balanced"},
    "technical_communicator": {"priority": "balanced"},
}

# Immutable at runtime.
MODEL_AFFINITY: dict[str, dict[str, Any]] = _RAW_AFFINITY
del _RAW_AFFINITY


def resolve_model_requirement(
    tier_str: str,
    preset_name: str | None = None,
) -> ModelRequirement:
    """Merge a template tier alias with personality-preset affinity.

    The template's tier always wins.  Affinity fills in ``priority``
    and ``min_context`` when the template only specifies a bare tier.

    Args:
        tier_str: Tier alias from the template agent config.
        preset_name: Optional personality preset name for affinity lookup.

    Returns:
        Resolved ``ModelRequirement``.
    """
    affinity = MODEL_AFFINITY.get((preset_name or "").strip().lower(), {})

    merged: dict[str, Any] = {"tier": tier_str.strip().lower()}
    # Affinity provides defaults; explicit template values override.
    if "priority" in affinity:
        merged["priority"] = affinity["priority"]
    if "min_context" in affinity:
        merged["min_context"] = affinity["min_context"]

    result = parse_model_requirement(merged)
    logger.debug(
        TEMPLATE_MODEL_REQUIREMENT_RESOLVED,
        tier=result.tier,
        priority=result.priority,
        min_context=result.min_context,
        preset=preset_name,
    )
    return result
