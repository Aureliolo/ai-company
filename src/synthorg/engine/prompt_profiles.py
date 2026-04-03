"""Prompt rendering profiles for model tier adaptation.

Maps each :data:`~synthorg.templates.model_requirements.ModelTier` to a
:class:`PromptProfile` that controls how verbose and detailed the system
prompt is.  Smaller/cheaper models receive simpler prompts they can
follow more reliably; larger models receive the full prompt.

Three built-in profiles:

* **full** (large) -- all sections, full personality, full criteria.
* **standard** (medium) -- condensed personality, summary autonomy.
* **basic** (small) -- minimal personality, no org policies,
  simplified acceptance criteria.

Authority and security sections are **never** stripped regardless of
profile.
"""

from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import ModelTier  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.prompt import (
    PROMPT_PROFILE_DEFAULT,
    PROMPT_PROFILE_SELECTED,
)

logger = get_logger(__name__)


class PromptProfile(BaseModel):
    """Prompt rendering profile tuned for a specific model tier.

    Controls how verbose and detailed the system prompt is, allowing
    smaller/cheaper models to receive simpler prompts that they can
    follow more reliably.

    Attributes:
        tier: The model tier this profile targets.
        max_personality_tokens: Soft limit on personality section length
            (reserved for future token-based trimming).
        include_org_policies: Whether to include the org policies section.
        simplify_acceptance_criteria: Whether to render acceptance
            criteria as a flat comma-separated line instead of a nested
            list.
        autonomy_detail_level: Level of detail for autonomy instructions
            (``"full"`` | ``"summary"`` | ``"minimal"``).
        personality_mode: How much personality detail to include
            (``"full"`` | ``"condensed"`` | ``"minimal"``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    tier: ModelTier = Field(description="Target model tier")
    max_personality_tokens: int = Field(
        gt=0,
        description="Soft limit on personality section token count",
    )
    include_org_policies: bool = Field(
        default=True,
        description="Whether to include org policies in prompt",
    )
    simplify_acceptance_criteria: bool = Field(
        default=False,
        description="Simplify acceptance criteria to flat list",
    )
    autonomy_detail_level: Literal["full", "summary", "minimal"] = Field(
        default="full",
        description="Level of autonomy instruction detail",
    )
    personality_mode: Literal["full", "condensed", "minimal"] = Field(
        default="full",
        description="Personality section verbosity",
    )


# ── Built-in profiles ──────────────────────────────────────────

_FULL_PROFILE = PromptProfile(
    tier="large",
    max_personality_tokens=500,
    include_org_policies=True,
    simplify_acceptance_criteria=False,
    autonomy_detail_level="full",
    personality_mode="full",
)

_STANDARD_PROFILE = PromptProfile(
    tier="medium",
    max_personality_tokens=200,
    include_org_policies=True,
    simplify_acceptance_criteria=False,
    autonomy_detail_level="summary",
    personality_mode="condensed",
)

_BASIC_PROFILE = PromptProfile(
    tier="small",
    max_personality_tokens=80,
    include_org_policies=False,
    simplify_acceptance_criteria=True,
    autonomy_detail_level="minimal",
    personality_mode="minimal",
)

PROMPT_PROFILE_REGISTRY: MappingProxyType[ModelTier, PromptProfile] = MappingProxyType(
    {
        "large": _FULL_PROFILE,
        "medium": _STANDARD_PROFILE,
        "small": _BASIC_PROFILE,
    },
)
"""Read-only mapping from model tier to prompt profile."""


def get_prompt_profile(tier: ModelTier | None) -> PromptProfile:
    """Return the built-in prompt profile for a model tier.

    When *tier* is ``None``, returns the full (large) profile as a
    safe default -- if the tier is unknown, assume full capability.

    Args:
        tier: Model tier, or ``None`` for the default (full) profile.

    Returns:
        The matching ``PromptProfile``.
    """
    if tier is None:
        logger.debug(PROMPT_PROFILE_DEFAULT)
        return _FULL_PROFILE

    profile = PROMPT_PROFILE_REGISTRY[tier]
    logger.debug(
        PROMPT_PROFILE_SELECTED,
        tier=tier,
        personality_mode=profile.personality_mode,
        autonomy_detail_level=profile.autonomy_detail_level,
    )
    return profile
