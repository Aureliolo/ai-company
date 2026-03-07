"""Delegation request, result, and audit trail models."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ai_company.core.task import Task  # noqa: TC001
from ai_company.core.types import NotBlankStr  # noqa: TC001


class DelegationRequest(BaseModel):
    """Request to delegate a task down the hierarchy.

    Attributes:
        delegator_id: Agent ID of the delegator.
        delegatee_id: Agent ID of the target agent.
        task: The task to delegate.
        refinement: Additional context from the delegator.
        constraints: Extra constraints for the delegatee.
    """

    model_config = ConfigDict(frozen=True)

    delegator_id: NotBlankStr = Field(
        description="Agent ID of the delegator",
    )
    delegatee_id: NotBlankStr = Field(
        description="Agent ID of the target agent",
    )
    task: Task = Field(description="Task to delegate")
    refinement: str = Field(
        default="",
        description="Additional context from the delegator",
    )
    constraints: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Extra constraints for the delegatee",
    )


class DelegationResult(BaseModel):
    """Outcome of a delegation attempt.

    Attributes:
        success: Whether the delegation succeeded.
        delegated_task: The sub-task created, if successful.
        rejection_reason: Reason for rejection, if unsuccessful.
        blocked_by: Mechanism name that blocked, if applicable.
    """

    model_config = ConfigDict(frozen=True)

    success: bool = Field(description="Whether delegation succeeded")
    delegated_task: Task | None = Field(
        default=None,
        description="Sub-task created on success",
    )
    rejection_reason: str | None = Field(
        default=None,
        description="Reason for rejection",
    )
    blocked_by: NotBlankStr | None = Field(
        default=None,
        description="Mechanism name that blocked delegation",
    )


class DelegationRecord(BaseModel):
    """Audit trail entry for a completed delegation.

    Attributes:
        delegation_id: Unique delegation identifier.
        delegator_id: Agent ID of the delegator.
        delegatee_id: Agent ID of the delegatee.
        original_task_id: ID of the original task.
        delegated_task_id: ID of the created sub-task.
        timestamp: When the delegation occurred.
        refinement: Context provided by the delegator.
    """

    model_config = ConfigDict(frozen=True)

    delegation_id: NotBlankStr = Field(
        description="Unique delegation identifier",
    )
    delegator_id: NotBlankStr = Field(
        description="Delegator agent ID",
    )
    delegatee_id: NotBlankStr = Field(
        description="Delegatee agent ID",
    )
    original_task_id: NotBlankStr = Field(
        description="Original task ID",
    )
    delegated_task_id: NotBlankStr = Field(
        description="Created sub-task ID",
    )
    timestamp: AwareDatetime = Field(
        description="When delegation occurred",
    )
    refinement: str = Field(
        default="",
        description="Context provided by delegator",
    )
