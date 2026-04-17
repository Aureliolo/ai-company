"""Escalation queue domain models (#1418)."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from synthorg.communication.conflict_resolution.models import Conflict  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001


class EscalationStatus(StrEnum):
    """Lifecycle state of an escalation row.

    Members:
        PENDING: Awaiting a human decision.
        DECIDED: A decision has been applied.
        EXPIRED: Timed out without a decision.
        CANCELLED: Operator explicitly abandoned the escalation.
    """

    PENDING = "pending"
    DECIDED = "decided"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class WinnerDecision(BaseModel):
    """Operator picks a winning position from the conflict.

    Attributes:
        type: Discriminator (``"winner"``).
        winning_agent_id: ID of the agent whose position wins.  Must
            match one of the agents in the conflict's positions.
        reasoning: Operator's explanation, captured in the resulting
            :class:`ConflictResolution.reasoning` field.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    type: Literal["winner"] = "winner"
    winning_agent_id: NotBlankStr
    reasoning: NotBlankStr = Field(max_length=4096)


class RejectDecision(BaseModel):
    """Operator rejects all positions; conflict remains unresolved.

    Attributes:
        type: Discriminator (``"reject"``).
        reasoning: Operator's explanation.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    type: Literal["reject"] = "reject"
    reasoning: NotBlankStr = Field(max_length=4096)


EscalationDecision = Annotated[
    WinnerDecision | RejectDecision,
    Field(discriminator="type"),
]
"""Human decision payload -- tagged union discriminated on ``type``.

Additional decision shapes (e.g. a free-form custom resolution) can be
added in the future without a model version bump because the
discriminator makes the union forwards-extensible.
"""


class Escalation(BaseModel):
    """A conflict waiting on a human decision.

    Attributes:
        id: Unique escalation identifier (e.g. ``"escalation-a1b2"``).
        conflict: Snapshot of the conflict at escalation time.  Frozen
            so decisions are applied against the exact positions the
            operator reviewed.
        status: Lifecycle state.  ``PENDING`` at creation; transitions
            to ``DECIDED``, ``EXPIRED``, or ``CANCELLED`` exactly once.
        created_at: When the escalation was enqueued.
        expires_at: Deadline for a human decision (``None`` = wait
            forever).  When exceeded, the sweeper transitions the row
            to ``EXPIRED``.
        decided_at: Timestamp of the decision (``None`` while pending).
        decided_by: Operator identifier that submitted the decision.
            Format: ``"human:<operator_id>"``.
        decision: The decision payload (``None`` while pending).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr
    conflict: Conflict
    status: EscalationStatus = EscalationStatus.PENDING
    created_at: AwareDatetime
    expires_at: AwareDatetime | None = None
    decided_at: AwareDatetime | None = None
    decided_by: NotBlankStr | None = None
    decision: EscalationDecision | None = None

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> Self:
        """Enforce invariants between ``status`` and decision fields."""
        if self.status == EscalationStatus.PENDING:
            if self.decision is not None or self.decided_at is not None:
                msg = "PENDING escalations must have decision=None and decided_at=None"
                raise ValueError(msg)
        elif self.status == EscalationStatus.DECIDED:
            if self.decision is None:
                msg = "DECIDED escalations require a decision"
                raise ValueError(msg)
            if self.decided_at is None:
                msg = "DECIDED escalations require decided_at"
                raise ValueError(msg)
            if self.decided_by is None:
                msg = "DECIDED escalations require decided_by"
                raise ValueError(msg)
        # EXPIRED / CANCELLED have no decision payload but may carry a
        # decided_at to record the terminal transition timestamp; both
        # are permissive in this validator.
        if self.status == EscalationStatus.DECIDED and isinstance(
            self.decision,
            WinnerDecision,
        ):
            agent_ids = {p.agent_id for p in self.conflict.positions}
            if self.decision.winning_agent_id not in agent_ids:
                msg = (
                    f"winning_agent_id {self.decision.winning_agent_id!r} "
                    "must reference a position in the escalated conflict"
                )
                raise ValueError(msg)
        return self
