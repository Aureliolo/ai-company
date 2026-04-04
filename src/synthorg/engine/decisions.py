"""Auditable decision records for the approval gate.

Immutable, append-only records of every approval gate decision. Each
record captures full context at decision time -- executing agent,
reviewer, criteria snapshot, and outcome -- for audit and analytics.

See the security and approval gate sections of the Operations design
page.
"""

import copy
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.enums import DecisionOutcome  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001


class DecisionRecord(BaseModel):
    """Immutable record of a review gate decision.

    Attributes:
        id: Unique decision record identifier (UUID).
        task_id: Task that was reviewed.
        approval_id: Associated ``ApprovalItem`` ID (``None`` for
            programmatic decisions without an explicit approval item).
        executing_agent_id: Agent that performed the work.
        reviewer_agent_id: Agent or human that reviewed.
        decision: The outcome of the review.
        reason: Optional rationale for the decision.
        criteria_snapshot: Acceptance criteria at decision time (empty
            tuple when the task has no acceptance criteria).
        recorded_at: When the decision was recorded.
        version: Monotonic version per task (1-indexed).
        metadata: Forward-compatible structured metadata.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(description="Unique decision record identifier")
    task_id: NotBlankStr = Field(description="Task that was reviewed")
    approval_id: NotBlankStr | None = Field(
        default=None,
        description="Associated ApprovalItem identifier",
    )
    executing_agent_id: NotBlankStr = Field(
        description="Agent that performed the work",
    )
    reviewer_agent_id: NotBlankStr = Field(
        description="Agent or human that reviewed",
    )
    decision: DecisionOutcome = Field(description="Outcome of the review")
    reason: str | None = Field(
        default=None,
        description="Optional rationale for the decision",
    )
    criteria_snapshot: tuple[str, ...] = Field(
        default=(),
        description="Acceptance criteria at decision time",
    )
    recorded_at: AwareDatetime = Field(description="When the decision was recorded")
    version: int = Field(ge=1, description="Monotonic version per task")
    metadata: dict[str, Any] = Field(description="Forward-compatible metadata")

    def __init__(self, **data: object) -> None:
        """Deep-copy metadata dict at construction boundary."""
        if "metadata" in data and isinstance(data["metadata"], dict):
            data["metadata"] = copy.deepcopy(data["metadata"])
        super().__init__(**data)
