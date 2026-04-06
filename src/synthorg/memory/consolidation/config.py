"""Memory consolidation configuration models.

Frozen Pydantic models for consolidation interval, retention,
archival, and LLM consolidation strategy settings.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.enums import ConsolidationInterval, MemoryCategory
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.consolidation.models import RetentionRule  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.config import CONFIG_VALIDATION_FAILED

logger = get_logger(__name__)


class RetentionConfig(BaseModel):
    """Per-category retention configuration (company-level defaults).

    These rules apply as the baseline for all agents.  Individual agents
    can override specific categories via
    :attr:`~synthorg.core.agent.MemoryConfig.retention_overrides`.

    Resolution order per category (highest priority first):

    1. Agent per-category override
    2. Company per-category rule (this config)
    3. Agent global default (``MemoryConfig.retention_days``)
    4. Company global default (``default_retention_days``)
    5. Keep forever (no expiry)

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
            seen: set[MemoryCategory] = set()
            dupes: set[str] = set()
            for c in categories:
                if c in seen:
                    dupes.add(c.value)
                seen.add(c)
            sorted_dupes = sorted(dupes)
            msg = f"Duplicate retention categories: {sorted_dupes}"
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                model="RetentionConfig",
                field="rules",
                duplicates=sorted_dupes,
                reason=msg,
            )
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
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                model="DualModeConfig",
                field="summarization_model",
                enabled=self.enabled,
                reason=msg,
            )
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


_MIN_LLM_GROUP_THRESHOLD = 3


class LLMConsolidationConfig(BaseModel):
    """Configuration for the LLM-based consolidation strategy.

    Encapsulates all tuning knobs previously passed as loose kwargs to
    ``LLMConsolidationStrategy.__init__`` and module-level constants.
    Aligns with the frozen Pydantic config convention used by sibling
    strategies (``DualModeConfig``, ``RetentionConfig``).

    Attributes:
        group_threshold: Minimum category group size for consolidation.
            At threshold 3, ``_select_entries`` keeps one entry and
            ``_synthesize`` receives two -- the smallest input for a
            meaningful LLM merge.
        temperature: Sampling temperature for the synthesis LLM call.
        max_summary_tokens: Maximum tokens for the synthesis response.
        include_distillation_context: When True, fetches recent
            distillation entries as trajectory context for the
            synthesis prompt.
        max_trajectory_context_entries: Maximum distillation entries
            to include as trajectory context.
        max_trajectory_chars_per_entry: Character limit per trajectory
            snippet in the synthesis prompt.
        max_entry_input_chars: Per-entry content character limit before
            being sent to the LLM.
        max_total_user_content_chars: Total character cap for the
            concatenated user prompt sent to the LLM.
        fallback_truncate_length: Per-entry truncation limit in
            concatenation-fallback summaries.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    group_threshold: int = Field(
        default=3,
        ge=_MIN_LLM_GROUP_THRESHOLD,
        description=("Minimum category group size for consolidation (must be >= 3)"),
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for the synthesis LLM call",
    )
    max_summary_tokens: int = Field(
        default=500,
        ge=50,
        description="Maximum tokens for the synthesis response",
    )
    include_distillation_context: bool = Field(
        default=True,
        description=(
            "When True, fetch recent distillation entries as "
            "trajectory context for the synthesis prompt"
        ),
    )
    max_trajectory_context_entries: int = Field(
        default=5,
        ge=1,
        description=("Maximum distillation entries to include as trajectory context"),
    )
    max_trajectory_chars_per_entry: int = Field(
        default=500,
        ge=50,
        description=("Character limit per trajectory snippet in the synthesis prompt"),
    )
    max_entry_input_chars: int = Field(
        default=2000,
        ge=100,
        description=("Per-entry content character limit before being sent to the LLM"),
    )
    max_total_user_content_chars: int = Field(
        default=20000,
        ge=1000,
        description=(
            "Total character cap for the concatenated user prompt sent to the LLM"
        ),
    )
    fallback_truncate_length: int = Field(
        default=200,
        ge=50,
        description=("Per-entry truncation limit in concatenation-fallback summaries"),
    )

    @model_validator(mode="after")
    def _validate_entry_vs_total_chars(self) -> Self:
        """Ensure per-entry cap does not exceed total prompt cap."""
        if self.max_entry_input_chars > self.max_total_user_content_chars:
            msg = (
                f"max_entry_input_chars ({self.max_entry_input_chars}) "
                f"must not exceed max_total_user_content_chars "
                f"({self.max_total_user_content_chars})"
            )
            raise ValueError(msg)
        return self
