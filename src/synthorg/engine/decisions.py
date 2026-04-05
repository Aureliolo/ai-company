"""Auditable decision records for the approval gate.

Immutable, append-only records of every approval gate decision. Each
record captures full context at decision time -- executing agent,
reviewer, criteria snapshot, and outcome -- for audit and analytics.

See the Review Gate section of ``docs/design/engine.md`` for the
drop-box design rationale, and the "Security and Approval System"
section of ``docs/design/operations.md`` for how decisions flow
through the approval lifecycle.
"""

from typing import Any, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from synthorg.core.enums import DecisionOutcome  # noqa: TC001
from synthorg.core.types import NotBlankStr, validate_unique_strings
from synthorg.engine.immutable import deep_copy_mapping


class DecisionRecord(BaseModel):
    """Immutable record of a review gate decision.

    Attributes:
        id: Unique decision record identifier (UUID).
        task_id: Task that was reviewed.
        approval_id: Associated ``ApprovalItem`` ID (``None`` for
            programmatic decisions without an explicit approval item).
        executing_agent_id: Agent that performed the work.
        reviewer_agent_id: Agent or human that reviewed.  Must differ
            from ``executing_agent_id`` -- no-self-review is a type
            invariant, not just a service-layer policy.
        decision: The outcome of the review.
        reason: Optional rationale for the decision.  Empty or
            whitespace-only strings are coerced to ``None`` at
            construction so the model never carries a tri-state
            ("", None, populated).
        criteria_snapshot: Acceptance criteria at decision time (empty
            tuple when the task has no acceptance criteria).  Each
            element must be non-blank.
        recorded_at: When the decision was recorded.
        version: Monotonic version per task (1-indexed).  Server-
            assigned by the persistence layer; the service never picks
            the value itself to avoid TOCTOU races.
        metadata: Forward-compatible structured metadata (deep-copied
            at construction).
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
    reason: NotBlankStr | None = Field(
        default=None,
        description=(
            "Optional rationale for the decision; empty or whitespace-only "
            "strings are coerced to None at construction."
        ),
    )
    criteria_snapshot: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Acceptance criteria at decision time (unique)",
    )
    recorded_at: AwareDatetime = Field(description="When the decision was recorded")
    version: int = Field(ge=1, description="Monotonic version per task")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Forward-compatible metadata",
    )

    @field_validator("reason", mode="before")
    @classmethod
    def _coerce_empty_reason_to_none(cls, value: object) -> object:
        """Normalize empty / whitespace-only reasons to ``None``."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("metadata", mode="before")
    @classmethod
    def _deep_copy_metadata(cls, value: object) -> object:
        """Deep-copy metadata at construction boundary."""
        return deep_copy_mapping(value)

    @field_validator("criteria_snapshot", mode="after")
    @classmethod
    def _validate_criteria_snapshot_unique(
        cls,
        value: tuple[NotBlankStr, ...],
    ) -> tuple[NotBlankStr, ...]:
        """Reject duplicate criteria -- they represent unique rules."""
        validate_unique_strings(value, "criteria_snapshot")
        return value

    @model_validator(mode="after")
    def _forbid_self_review(self) -> Self:
        """Enforce no-self-review as a type-level invariant."""
        if self.executing_agent_id == self.reviewer_agent_id:
            msg = (
                f"executing_agent_id and reviewer_agent_id must differ "
                f"(got {self.executing_agent_id!r} for both)"
            )
            raise ValueError(msg)
        return self
