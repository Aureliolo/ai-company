"""Auditable decision records for the approval gate.

Immutable, append-only records of every approval gate decision. Each
record captures full context at decision time -- executing agent,
reviewer, criteria snapshot, and outcome -- for audit and analytics.

See the Review Gate section of ``docs/design/engine.md`` for the
drop-box design rationale, and the "Security and Approval System"
section of ``docs/design/operations.md`` for how decisions flow
through the approval lifecycle.
"""

from types import MappingProxyType
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
from synthorg.ontology.decorator import ontology_entity


def _freeze_recursive(value: object) -> object:
    """Recursively convert mutable containers into immutable forms.

    - ``dict`` -> ``MappingProxyType`` (read-only view of a frozen dict)
    - ``list`` -> ``tuple`` with elements recursively frozen
    - ``tuple`` -> ``tuple`` with elements recursively frozen (tuples
      are themselves immutable but their *elements* can still be
      mutable dicts/lists/sets, so we still recurse)
    - ``set``  -> ``frozenset`` with elements recursively frozen
    - anything else is returned unchanged

    The input is already a deep copy produced by ``deep_copy_mapping``,
    so nested containers can be freely transformed in place before
    being re-wrapped for the frozen Pydantic model field.
    """
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze_recursive(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_recursive(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_recursive(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_recursive(item) for item in value)
    return value


@ontology_entity
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
            AND wrapped in ``MappingProxyType`` at construction to
            block post-construction mutation of the audit record).
    """

    model_config = ConfigDict(
        frozen=True,
        allow_inf_nan=False,
        arbitrary_types_allowed=True,
    )

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
    metadata: MappingProxyType[str, Any] = Field(
        default_factory=lambda: MappingProxyType({}),
        description="Forward-compatible metadata (read-only view)",
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
    def _deep_copy_and_freeze_metadata(cls, value: object) -> object:
        """Deep-copy and recursively freeze metadata.

        Wrapping the top-level mapping in ``MappingProxyType`` blocks
        ``record.metadata["key"] = ...``; recursing into nested
        containers also blocks ``record.metadata["nested"]["key"] =
        ...`` by converting ``dict`` -> ``MappingProxyType``,
        ``list`` -> ``tuple``, and ``set`` -> ``frozenset``.  Together
        these preserve the append-only audit-record contract even for
        forward-compatible metadata payloads that carry nested
        structures.  If the input is already a ``MappingProxyType``
        (e.g. passed to ``model_copy``), we rebuild from the
        underlying dict so the deep-copy + freeze steps still run.
        """
        if isinstance(value, MappingProxyType):
            # Unwrap so deep_copy_mapping sees a dict and actually
            # produces an independent copy before we re-wrap.
            value = dict(value)
        copied = deep_copy_mapping(value)
        return _freeze_recursive(copied)

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
