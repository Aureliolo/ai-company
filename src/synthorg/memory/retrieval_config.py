"""Memory retrieval pipeline configuration.

Frozen Pydantic config for the retrieval pipeline -- weights,
thresholds, and strategy selection.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.memory.injection import InjectionPoint, InjectionStrategy
from synthorg.memory.ranking import FusionStrategy
from synthorg.observability import get_logger
from synthorg.observability.events.config import CONFIG_VALIDATION_FAILED

logger = get_logger(__name__)

_WEIGHT_SUM_TOLERANCE = 1e-6
_DEFAULT_RRF_K = 60


class MemoryRetrievalConfig(BaseModel):
    """Configuration for the memory retrieval and ranking pipeline.

    Attributes:
        strategy: Which injection strategy to use.
        relevance_weight: Weight for backend relevance score (0.0-1.0).
        recency_weight: Weight for recency decay score (0.0-1.0).
        recency_decay_rate: Exponential decay rate per hour.
        personal_boost: Boost applied to personal over shared (0.0-1.0).
        min_relevance: Minimum combined (relevance + recency) score to include.
        max_memories: Maximum candidates to retrieve (1-100).
        include_shared: Whether to query SharedKnowledgeStore.
        default_relevance: Score for entries missing relevance_score.
        injection_point: Message role for context injection.
        non_inferable_only: When True, auto-creates a ``TagBasedMemoryFilter``
            in ``ContextInjectionStrategy`` if no explicit filter is provided.
        fusion_strategy: Ranking fusion strategy -- LINEAR for single-source
            relevance+recency, RRF for multi-source ranked list merging.
        rrf_k: RRF smoothing constant (1-1000, only used with RRF strategy).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    strategy: InjectionStrategy = Field(
        default=InjectionStrategy.CONTEXT,
        description="Which injection strategy to use",
    )
    relevance_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for backend relevance score",
    )
    recency_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for recency decay score",
    )
    recency_decay_rate: float = Field(
        default=0.01,
        ge=0.0,
        description="Exponential decay rate per hour",
    )
    personal_boost: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Boost applied to personal over shared memories",
    )
    min_relevance: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum combined (relevance + recency) score to include",
    )
    max_memories: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum candidates to retrieve",
    )
    include_shared: bool = Field(
        default=True,
        description="Whether to query SharedKnowledgeStore",
    )
    default_relevance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Score for entries missing relevance_score",
    )
    injection_point: InjectionPoint = Field(
        default=InjectionPoint.SYSTEM,
        description="Message role for context injection",
    )
    non_inferable_only: bool = Field(
        default=False,
        description="When True, only inject memories tagged as non-inferable",
    )
    fusion_strategy: FusionStrategy = Field(
        default=FusionStrategy.LINEAR,
        description=(
            "Ranking fusion strategy: linear for single-source "
            "relevance+recency, rrf for multi-source ranked list merging"
        ),
    )
    rrf_k: int = Field(
        default=_DEFAULT_RRF_K,
        ge=1,
        le=1000,
        description="RRF smoothing constant k (only used with RRF strategy)",
    )
    query_reformulation_enabled: bool = Field(
        default=False,
        description=(
            "Reserved for future query reformulation support in the "
            "TOOL_BASED strategy. Not yet wired into the retrieval "
            "pipeline -- must remain False until implemented."
        ),
    )
    max_reformulation_rounds: int = Field(
        default=2,
        ge=1,
        le=5,
        description=(
            "Reserved for future query reformulation support (1-5). "
            "Currently unused until reformulation is wired."
        ),
    )

    @model_validator(mode="after")
    def _validate_weight_sum(self) -> Self:
        """Ensure relevance_weight + recency_weight == 1.0 for LINEAR fusion."""
        if self.fusion_strategy != FusionStrategy.LINEAR:
            return self
        total = self.relevance_weight + self.recency_weight
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            msg = (
                f"relevance_weight ({self.relevance_weight}) + "
                f"recency_weight ({self.recency_weight}) must equal 1.0, "
                f"got {total}"
            )
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                field="relevance_weight+recency_weight",
                value=total,
                reason=msg,
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_rrf_k_strategy_consistency(self) -> Self:
        """Warn when rrf_k is customized but fusion strategy is LINEAR."""
        if (
            self.fusion_strategy == FusionStrategy.LINEAR
            and self.rrf_k != _DEFAULT_RRF_K
        ):
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                field="rrf_k",
                value=self.rrf_k,
                reason="rrf_k is ignored when fusion_strategy is LINEAR",
            )
        return self

    @model_validator(mode="after")
    def _validate_reformulation_not_supported(self) -> Self:
        """Reject query_reformulation_enabled until wiring is complete."""
        if not self.query_reformulation_enabled:
            return self
        msg = (
            "query_reformulation_enabled is not yet supported: "
            "the retrieval pipeline does not consume this option"
        )
        logger.warning(
            CONFIG_VALIDATION_FAILED,
            field="query_reformulation_enabled",
            value=self.query_reformulation_enabled,
            reason=msg,
        )
        raise ValueError(msg)

    @model_validator(mode="after")
    def _validate_personal_boost_rrf_consistency(self) -> Self:
        """Warn when personal_boost is explicitly set with RRF fusion."""
        if (
            self.fusion_strategy == FusionStrategy.RRF
            and self.personal_boost > 0.0
            and "personal_boost" in self.model_fields_set
        ):
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                field="personal_boost",
                value=self.personal_boost,
                reason=(
                    "personal_boost may not be applied when pure RRF "
                    "is used; fallback to rank_memories (when sparse "
                    "is empty) does apply personal_boost"
                ),
            )
        return self

    @model_validator(mode="after")
    def _validate_supported_strategy(self) -> Self:
        """Reject strategies that are not yet implemented."""
        _supported = {InjectionStrategy.CONTEXT, InjectionStrategy.TOOL_BASED}
        if self.strategy not in _supported:
            msg = (
                f"Strategy {self.strategy.value!r} is not yet implemented; "
                f"supported: {sorted(s.value for s in _supported)}"
            )
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                field="strategy",
                value=self.strategy.value,
                reason=msg,
            )
            raise ValueError(msg)
        return self
