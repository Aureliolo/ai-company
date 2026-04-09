"""Pruning domain models.

Frozen Pydantic models for pruning evaluations, requests, records,
and service configuration.
"""

from typing import Self
from uuid import uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from synthorg.core.enums import ApprovalStatus
from synthorg.core.types import NotBlankStr
from synthorg.hr.performance.models import AgentPerformanceSnapshot  # noqa: TC001


class PruningEvaluation(BaseModel):
    """Result of a pruning policy evaluation.

    Attributes:
        agent_id: Agent being evaluated.
        eligible: Whether agent should be pruned.
        reasons: Human-readable justifications.
        scores: Debug scores from evaluation criteria.
        policy_name: Which policy produced this evaluation.
        snapshot: Performance snapshot used for evaluation.
        evaluated_at: When evaluation occurred.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr = Field(description="Agent being evaluated")
    eligible: bool = Field(description="Whether agent should be pruned")
    reasons: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Human-readable justifications",
    )
    scores: dict[str, float] = Field(
        default_factory=dict,
        description="Debug scores from evaluation criteria",
    )
    policy_name: NotBlankStr = Field(
        description="Which policy produced this evaluation",
    )
    snapshot: AgentPerformanceSnapshot = Field(
        description="Performance snapshot used for evaluation",
    )
    evaluated_at: AwareDatetime = Field(description="When evaluation occurred")


class PruningRequest(BaseModel):
    """Request to prune an agent pending human approval.

    Attributes:
        id: Unique request identifier.
        agent_id: Agent to be pruned.
        agent_name: Agent's display name.
        evaluation: The evaluation result.
        approval_id: Associated approval item ID.
        status: Current approval status.
        created_at: When request was created.
        decided_at: When approval decision was made.
        decided_by: Who made the approval decision.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(
        default_factory=lambda: NotBlankStr(str(uuid4())),
        description="Unique request identifier",
    )
    agent_id: NotBlankStr = Field(description="Agent to be pruned")
    agent_name: NotBlankStr = Field(description="Agent display name")
    evaluation: PruningEvaluation = Field(description="Evaluation result")
    approval_id: NotBlankStr = Field(description="Associated approval item ID")
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        description="Current approval status",
    )
    created_at: AwareDatetime = Field(description="When request was created")
    decided_at: AwareDatetime | None = Field(
        default=None,
        description="When approval decision was made",
    )
    decided_by: NotBlankStr | None = Field(
        default=None,
        description="Who made the approval decision",
    )

    @model_validator(mode="after")
    def _validate_temporal_order(self) -> Self:
        """Ensure decided_at >= created_at when both are present."""
        if self.decided_at is not None and self.decided_at < self.created_at:
            msg = (
                f"decided_at ({self.decided_at}) must be >= "
                f"created_at ({self.created_at})"
            )
            raise ValueError(msg)
        return self


class PruningRecord(BaseModel):
    """Record of a completed pruning process.

    Attributes:
        agent_id: Agent who was pruned.
        agent_name: Agent's display name.
        pruning_request_id: Associated pruning request.
        offboarding_record_id: Link to offboarding record.
        reason: Why agent was pruned.
        approval_id: Which approval authorized it.
        initiated_by: System or human who initiated.
        created_at: When process started.
        completed_at: When process finished.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr = Field(description="Agent who was pruned")
    agent_name: NotBlankStr = Field(description="Agent display name")
    pruning_request_id: NotBlankStr = Field(
        description="Associated pruning request",
    )
    offboarding_record_id: NotBlankStr = Field(
        description="Link to offboarding record",
    )
    reason: NotBlankStr = Field(description="Why agent was pruned")
    approval_id: NotBlankStr = Field(description="Approval that authorized it")
    initiated_by: NotBlankStr = Field(description="Who initiated the pruning")
    created_at: AwareDatetime = Field(description="When process started")
    completed_at: AwareDatetime = Field(description="When process finished")

    @model_validator(mode="after")
    def _validate_temporal_order(self) -> Self:
        """Ensure completed_at >= created_at."""
        if self.completed_at < self.created_at:
            msg = (
                f"completed_at ({self.completed_at}) must be >= "
                f"created_at ({self.created_at})"
            )
            raise ValueError(msg)
        return self


class PruningJobRun(BaseModel):
    """Metadata about a single pruning scheduler cycle.

    Attributes:
        job_id: Unique cycle identifier.
        run_at: When the cycle started.
        agents_evaluated: Count of agents checked.
        agents_eligible: Count found eligible for pruning.
        approval_requests_created: Count of new approvals.
        elapsed_seconds: How long the cycle took.
        errors: Non-fatal errors encountered.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    job_id: NotBlankStr = Field(description="Unique cycle identifier")
    run_at: AwareDatetime = Field(description="When the cycle started")
    agents_evaluated: int = Field(ge=0, description="Agents checked")
    agents_eligible: int = Field(ge=0, description="Agents eligible for pruning")
    approval_requests_created: int = Field(
        ge=0,
        description="New approvals created",
    )
    elapsed_seconds: float = Field(ge=0.0, description="Cycle duration")
    errors: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Non-fatal errors encountered",
    )


class PruningServiceConfig(BaseModel):
    """Configuration for the pruning service.

    Attributes:
        evaluation_interval_seconds: How often to run pruning cycles.
        max_approvals_per_cycle: Limit on approvals created per cycle.
        approval_expiry_days: Days until pending approval expires.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    evaluation_interval_seconds: float = Field(
        default=3600.0,
        ge=60.0,
        description="How often to run pruning cycles",
    )
    max_approvals_per_cycle: int = Field(
        default=5,
        ge=1,
        description="Limit on approvals created per cycle",
    )
    approval_expiry_days: int = Field(
        default=7,
        ge=1,
        description="Days until pending approval expires",
    )
