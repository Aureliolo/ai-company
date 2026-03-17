"""Memory consolidation configuration models.

Frozen Pydantic models for consolidation interval, retention,
and archival settings.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.enums import ConsolidationInterval
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.consolidation.models import RetentionRule  # noqa: TC001


class RetentionConfig(BaseModel):
    """Per-category retention configuration.

    Retention rules apply uniformly across all agents.  Per-agent
    retention overrides (e.g. longer retention for senior agents) are
    not yet supported and are a known scope gap for a future iteration.

    Attributes:
        rules: Per-category retention rules (unique categories).
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

    @model_validator(mode="after")
    def _validate_unique_categories(self) -> Self:
        """Ensure each category appears at most once in rules."""
        categories = [rule.category for rule in self.rules]
        if len(categories) != len(set(categories)):
            dupes = sorted(c.value for c in categories if categories.count(c) > 1)
            msg = f"Duplicate retention categories: {dupes}"
            raise ValueError(msg)
        return self


class DualModeConfig(BaseModel):
    """Configuration for dual-mode archival.

    Controls density-aware archival: LLM abstractive summaries for
    sparse/conversational content vs extractive preservation (verbatim
    key facts + start/mid/end anchors) for dense/factual content.

    Attributes:
        enabled: Whether dual-mode density classification is active.
            When ``False``, the dual-mode strategy is not used.
        dense_threshold: Density score threshold for DENSE classification
            (0.0 = classify everything as dense, 1.0 = everything sparse).
        summarization_model: Model ID for abstractive summarization.
        max_summary_tokens: Maximum tokens for LLM summary responses.
        max_facts: Maximum number of extracted key facts for extractive
            mode.
        anchor_length: Character length for each extractive anchor
            snippet (start/mid/end).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = Field(
        default=False,
        description="Whether dual-mode density classification is active",
    )
    dense_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Density score threshold for DENSE classification",
    )
    summarization_model: NotBlankStr | None = Field(
        default=None,
        description="Model ID for abstractive summarization",
    )
    max_summary_tokens: int = Field(
        default=200,
        ge=50,
        le=1000,
        description="Maximum tokens for LLM summary responses",
    )
    max_facts: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum extracted key facts for extractive mode",
    )
    anchor_length: int = Field(
        default=150,
        ge=50,
        le=500,
        description="Character length for each extractive anchor",
    )

    @model_validator(mode="after")
    def _validate_model_when_enabled(self) -> Self:
        """Require a summarization model when dual-mode is enabled."""
        if self.enabled and self.summarization_model is None:
            msg = "summarization_model must be non-blank when dual-mode is enabled"
            raise ValueError(msg)
        return self


class ArchivalConfig(BaseModel):
    """Archival configuration.

    Attributes:
        enabled: Whether archival is enabled.
        age_threshold_days: Minimum age in days before archival.
        dual_mode: Dual-mode archival configuration.
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
    dual_mode: DualModeConfig = Field(
        default_factory=DualModeConfig,
        description="Dual-mode archival configuration",
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
