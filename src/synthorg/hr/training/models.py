"""Training mode domain models.

Frozen Pydantic models for training plans, items, guard decisions,
and results.  All models use ``ConfigDict(frozen=True, allow_inf_nan=False)``.
"""

from enum import StrEnum
from typing import Self
from uuid import uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from synthorg.core.enums import SeniorityLevel  # noqa: TC001
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger

logger = get_logger(__name__)


class ContentType(StrEnum):
    """Content types available for training extraction."""

    PROCEDURAL = "procedural"
    SEMANTIC = "semantic"
    TOOL_PATTERNS = "tool_patterns"


class TrainingPlanStatus(StrEnum):
    """Lifecycle status of a training plan."""

    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"


class TrainingItem(BaseModel):
    """A single knowledge item extracted from a senior agent.

    Carries content, provenance, and a relevance score set by the
    curation strategy.

    Attributes:
        id: Unique identifier (UUID).
        source_agent_id: Senior agent that produced this knowledge.
        content_type: Procedural, semantic, or tool pattern.
        content: The knowledge text.
        source_memory_id: Original memory entry ID for tracing.
        relevance_score: Score from curation (0.0 to 1.0).
        metadata_tags: Tags preserved from the source entry.
        created_at: When the item was created.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(
        default_factory=lambda: NotBlankStr(str(uuid4())),
        description="Unique identifier",
    )
    source_agent_id: NotBlankStr = Field(
        description="Senior agent that produced this knowledge",
    )
    content_type: ContentType = Field(
        description="Content type category",
    )
    content: NotBlankStr = Field(
        description="The knowledge text",
    )
    source_memory_id: NotBlankStr | None = Field(
        default=None,
        description="Original memory entry ID for tracing",
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Score from curation strategy",
    )
    metadata_tags: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Tags preserved from source entry",
    )
    created_at: AwareDatetime = Field(
        description="When the item was created",
    )


class TrainingGuardDecision(BaseModel):
    """Result of a single guard evaluation.

    Attributes:
        approved_items: Items that passed the guard.
        rejected_count: Number of items rejected.
        guard_name: Name of the guard that produced this decision.
        rejection_reasons: Per-item rejection reasons.
        approval_item_id: ApprovalStore item ID (ReviewGateGuard only).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    approved_items: tuple[TrainingItem, ...] = Field(
        description="Items that passed the guard",
    )
    rejected_count: int = Field(
        ge=0,
        description="Number of items rejected",
    )
    guard_name: NotBlankStr = Field(
        description="Name of the guard",
    )
    rejection_reasons: tuple[str, ...] = Field(
        default=(),
        description="Per-item rejection reasons",
    )
    approval_item_id: NotBlankStr | None = Field(
        default=None,
        description="ApprovalStore item ID (ReviewGateGuard only)",
    )


class TrainingPlan(BaseModel):
    """Configuration for a training session.

    Encapsulates the target agent, source selection strategy,
    content types, curation approach, volume caps, and overrides.
    The ``status`` field tracks execution for idempotency.

    Attributes:
        id: Unique identifier (UUID), also the idempotency key.
        new_agent_id: Target agent being trained.
        new_agent_role: Role of the new hire.
        new_agent_level: Seniority level of the new hire.
        source_selector_type: Source selector strategy name.
        enabled_content_types: Which extractors to run.
        curation_strategy_type: Curation strategy name.
        volume_caps: Per-content-type hard limits.
        override_sources: Explicit agent IDs (bypasses selector).
        skip_training: Hard off-switch.
        require_review: Whether ReviewGateGuard is enabled.
        status: Lifecycle status for idempotency.
        created_at: Plan creation timestamp.
        executed_at: Execution completion timestamp.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(
        default_factory=lambda: NotBlankStr(str(uuid4())),
        description="Unique identifier and idempotency key",
    )
    new_agent_id: NotBlankStr = Field(
        description="Target agent being trained",
    )
    new_agent_role: NotBlankStr = Field(
        description="Role of the new hire",
    )
    new_agent_level: SeniorityLevel = Field(
        description="Seniority level of the new hire",
    )
    source_selector_type: NotBlankStr = Field(
        default="role_top_performers",
        description="Source selector strategy name",
    )
    enabled_content_types: frozenset[ContentType] = Field(
        default_factory=lambda: frozenset(ContentType),
        description="Which extractors to run",
    )
    curation_strategy_type: NotBlankStr = Field(
        default="relevance",
        description="Curation strategy name",
    )
    volume_caps: tuple[tuple[ContentType, int], ...] = Field(
        default=(
            (ContentType.PROCEDURAL, 50),
            (ContentType.SEMANTIC, 10),
            (ContentType.TOOL_PATTERNS, 20),
        ),
        description="Per-content-type hard limits",
    )
    override_sources: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Explicit agent IDs (bypasses selector)",
    )
    skip_training: bool = Field(
        default=False,
        description="Hard off-switch for training",
    )
    require_review: bool = Field(
        default=True,
        description="Whether ReviewGateGuard is enabled",
    )
    status: TrainingPlanStatus = Field(
        default=TrainingPlanStatus.PENDING,
        description="Lifecycle status for idempotency",
    )
    created_at: AwareDatetime = Field(
        description="Plan creation timestamp",
    )
    executed_at: AwareDatetime | None = Field(
        default=None,
        description="Execution completion timestamp",
    )

    @model_validator(mode="after")
    def _validate_volume_caps(self) -> Self:
        """Ensure all volume cap values are positive."""
        for content_type, cap in self.volume_caps:
            if cap <= 0:
                msg = f"Volume cap for {content_type.value} must be positive, got {cap}"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_content_types_when_active(self) -> Self:
        """Ensure at least one content type is enabled when not skipping."""
        if not self.skip_training and not self.enabled_content_types:
            msg = (
                "At least one content type must be enabled when skip_training is False"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_executed_at(self) -> Self:
        """Ensure executed_at is set only when status is EXECUTED."""
        if self.status == TrainingPlanStatus.EXECUTED and self.executed_at is None:
            msg = "executed_at must be set when status is EXECUTED"
            raise ValueError(msg)
        if self.status == TrainingPlanStatus.PENDING and self.executed_at is not None:
            msg = "executed_at must be None when status is PENDING"
            raise ValueError(msg)
        return self


class TrainingResult(BaseModel):
    """Outcome of a training plan execution.

    Tracks item counts at each pipeline stage for auditing.

    Attributes:
        id: Unique result identifier.
        plan_id: Links to the executed TrainingPlan.
        new_agent_id: Agent that was trained.
        source_agents_used: Senior agents selected as sources.
        items_extracted: Per-content-type extracted counts.
        items_after_curation: Per-content-type post-curation counts.
        items_after_guards: Per-content-type post-guard counts.
        items_stored: Per-content-type stored counts.
        approval_item_id: ApprovalStore item ID if review gate triggered.
        errors: Guard rejections, store failures, etc.
        started_at: Pipeline start timestamp.
        completed_at: Pipeline completion timestamp.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(
        default_factory=lambda: NotBlankStr(str(uuid4())),
        description="Unique result identifier",
    )
    plan_id: NotBlankStr = Field(
        description="Links to the executed TrainingPlan",
    )
    new_agent_id: NotBlankStr = Field(
        description="Agent that was trained",
    )
    source_agents_used: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Senior agents selected as sources",
    )
    items_extracted: tuple[tuple[ContentType, int], ...] = Field(
        default=(),
        description="Per-content-type extracted counts",
    )
    items_after_curation: tuple[tuple[ContentType, int], ...] = Field(
        default=(),
        description="Per-content-type post-curation counts",
    )
    items_after_guards: tuple[tuple[ContentType, int], ...] = Field(
        default=(),
        description="Per-content-type post-guard counts",
    )
    items_stored: tuple[tuple[ContentType, int], ...] = Field(
        default=(),
        description="Per-content-type stored counts",
    )
    approval_item_id: NotBlankStr | None = Field(
        default=None,
        description="ApprovalStore item ID if review gate triggered",
    )
    errors: tuple[str, ...] = Field(
        default=(),
        description="Guard rejections, store failures, etc.",
    )
    started_at: AwareDatetime = Field(
        description="Pipeline start timestamp",
    )
    completed_at: AwareDatetime = Field(
        description="Pipeline completion timestamp",
    )

    @model_validator(mode="after")
    def _validate_timestamps(self) -> Self:
        """Ensure completed_at >= started_at."""
        if self.completed_at < self.started_at:
            msg = (
                f"completed_at ({self.completed_at}) must be "
                f">= started_at ({self.started_at})"
            )
            raise ValueError(msg)
        return self
