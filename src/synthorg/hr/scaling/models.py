"""Scaling domain models.

Frozen Pydantic models for scaling signals, context, decisions,
and action records.
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

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.enums import (
    ScalingActionType,
    ScalingOutcome,
    ScalingStrategyName,
)


class ScalingSignal(BaseModel):
    """A named signal value collected from a subsystem.

    Attributes:
        name: Signal identifier (e.g. ``avg_utilization``).
        value: Current signal value.
        threshold: Configured threshold for this signal.
        source: Which signal source produced this.
        timestamp: When the signal was collected.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr = Field(description="Signal identifier")
    value: float = Field(description="Current signal value")
    threshold: float | None = Field(
        default=None,
        description="Configured threshold for this signal",
    )
    source: NotBlankStr = Field(description="Signal source name")
    timestamp: AwareDatetime = Field(description="Collection timestamp")


class ScalingContext(BaseModel):
    """Aggregated snapshot of company state for strategy evaluation.

    Attributes:
        active_agent_count: Number of currently active agents.
        agent_ids: IDs of all active agents.
        workload_signals: Workload-related signals.
        budget_signals: Budget-related signals.
        performance_signals: Performance-related signals.
        skill_signals: Skill coverage signals.
        evaluated_at: When the context was built.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    active_agent_count: int = Field(ge=0, description="Active agent count")
    agent_ids: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="IDs of all active agents",
    )
    workload_signals: tuple[ScalingSignal, ...] = Field(
        default=(),
        description="Workload-related signals",
    )
    budget_signals: tuple[ScalingSignal, ...] = Field(
        default=(),
        description="Budget-related signals",
    )
    performance_signals: tuple[ScalingSignal, ...] = Field(
        default=(),
        description="Performance-related signals",
    )
    skill_signals: tuple[ScalingSignal, ...] = Field(
        default=(),
        description="Skill coverage signals",
    )
    evaluated_at: AwareDatetime = Field(
        description="When the context was built",
    )


class ScalingDecision(BaseModel):
    """A scaling action proposed by a strategy.

    Attributes:
        id: Unique decision identifier.
        action_type: Type of scaling action.
        source_strategy: Which strategy proposed this.
        target_agent_id: Agent targeted for pruning (None for hires).
        target_role: Role to hire for (None for prunes).
        target_skills: Skills required for hire target.
        target_department: Department for hire target.
        rationale: Human-readable explanation.
        confidence: Strategy confidence in this decision (0.0--1.0).
        signals: Signals that informed this decision.
        created_at: When the decision was created.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(
        default_factory=lambda: NotBlankStr(str(uuid4())),
        description="Unique decision identifier",
    )
    action_type: ScalingActionType = Field(
        description="Type of scaling action",
    )
    source_strategy: ScalingStrategyName = Field(
        description="Which strategy proposed this",
    )
    target_agent_id: NotBlankStr | None = Field(
        default=None,
        description="Agent targeted for pruning",
    )
    target_role: NotBlankStr | None = Field(
        default=None,
        description="Role to hire for",
    )
    target_skills: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Skills required for hire target",
    )
    target_department: NotBlankStr | None = Field(
        default=None,
        description="Department for hire target",
    )
    rationale: NotBlankStr = Field(
        description="Human-readable explanation",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Strategy confidence (0.0--1.0)",
    )
    signals: tuple[ScalingSignal, ...] = Field(
        default=(),
        description="Signals that informed this decision",
    )
    created_at: AwareDatetime = Field(
        description="When the decision was created",
    )

    @model_validator(mode="after")
    def _validate_target_fields(self) -> Self:
        """Validate target fields match the action type.

        HIRE decisions must have a target_role.
        PRUNE decisions must have a target_agent_id.
        HOLD and NO_OP require neither.
        """
        if self.action_type == ScalingActionType.HIRE and self.target_role is None:
            msg = "HIRE decisions must specify target_role"
            raise ValueError(msg)
        if self.action_type == ScalingActionType.PRUNE and self.target_agent_id is None:
            msg = "PRUNE decisions must specify target_agent_id"
            raise ValueError(msg)
        return self


class ScalingActionRecord(BaseModel):
    """Record of an executed (or attempted) scaling decision.

    Attributes:
        id: Unique record identifier.
        decision_id: The decision that was executed.
        outcome: Execution outcome.
        result_id: ID of the created entity (hire request ID,
            offboarding record ID, or approval item ID).
        reason: Additional context (e.g. failure message).
        executed_at: When execution occurred.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(
        default_factory=lambda: NotBlankStr(str(uuid4())),
        description="Unique record identifier",
    )
    decision_id: NotBlankStr = Field(
        description="Decision that was executed",
    )
    outcome: ScalingOutcome = Field(description="Execution outcome")
    result_id: NotBlankStr | None = Field(
        default=None,
        description="ID of created entity",
    )
    reason: NotBlankStr | None = Field(
        default=None,
        description="Additional context",
    )
    executed_at: AwareDatetime = Field(description="When execution occurred")
