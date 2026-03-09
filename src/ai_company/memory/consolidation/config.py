"""Memory consolidation configuration models.

Frozen Pydantic models for consolidation interval, retention,
and archival settings.
"""

from pydantic import BaseModel, ConfigDict, Field

from ai_company.core.enums import ConsolidationInterval
from ai_company.memory.consolidation.models import RetentionRule  # noqa: TC001


class RetentionConfig(BaseModel):
    """Per-category retention configuration.

    Attributes:
        rules: Per-category retention rules.
        default_retention_days: Default retention in days
            (``None`` = keep forever).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    rules: tuple[RetentionRule, ...] = Field(
        default=(),
        description="Per-category retention rules",
    )
    default_retention_days: int | None = Field(
        default=None,
        ge=1,
        description="Default retention in days (None = forever)",
    )


class ArchivalConfig(BaseModel):
    """Archival configuration.

    Attributes:
        enabled: Whether archival is enabled.
        age_threshold_days: Minimum age in days before archival.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = Field(
        default=False,
        description="Whether archival is enabled",
    )
    age_threshold_days: int = Field(
        default=90,
        ge=1,
        description="Minimum age in days before archival",
    )


class ConsolidationConfig(BaseModel):
    """Top-level memory consolidation configuration.

    Attributes:
        interval: How often to run consolidation.
        max_memories_per_agent: Upper bound on memories per agent.
        retention: Per-category retention settings.
        archival: Archival settings.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    interval: ConsolidationInterval = Field(
        default=ConsolidationInterval.DAILY,
        description="How often to run consolidation",
    )
    max_memories_per_agent: int = Field(
        default=10_000,
        ge=1,
        description="Upper bound on memories per agent",
    )
    retention: RetentionConfig = Field(
        default_factory=RetentionConfig,
        description="Per-category retention settings",
    )
    archival: ArchivalConfig = Field(
        default_factory=ArchivalConfig,
        description="Archival settings",
    )
