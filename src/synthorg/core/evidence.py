"""Evidence Package schema for HITL approval.

``EvidencePackage`` is the structured payload carried by ``ApprovalItem``
and emitted as the content of ``APPROVAL_INTERRUPT`` /
``INFO_REQUEST_INTERRUPT`` SSE events.  It extends
``StructuredArtifact`` (shared base with ``HandoffArtifact`` from R2
#1262) to prevent schema drift between role-transition handoffs and
HITL approvals.

Lives in ``core`` (not ``communication``) because ``ApprovalItem``
references it as a field type, and ``core`` must not depend on
``communication`` (which triggers a circular import chain).
"""

import copy
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.enums import ApprovalRiskLevel  # noqa: TC001
from synthorg.core.structured_artifact import StructuredArtifact
from synthorg.core.types import NotBlankStr  # noqa: TC001


class RecommendedAction(BaseModel):
    """A single action option presented to the human approver.

    Attributes:
        action_type: Semantic action key (e.g. ``"approve"``, ``"reject"``).
        label: Button text shown in the UI.
        description: Explanation of what this action does.
        confirmation_required: Whether the UI should show a confirmation
            dialog before executing.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    action_type: NotBlankStr = Field(description="Semantic action key")
    label: NotBlankStr = Field(description="UI button text")
    description: NotBlankStr = Field(description="Action explanation")
    confirmation_required: bool = Field(
        default=False,
        description="Whether to show a confirmation dialog",
    )


class EvidencePackage(StructuredArtifact):
    """Structured HITL approval artifact.

    Used as the payload for ``ApprovalItem`` and emitted as the content
    of ``APPROVAL_INTERRUPT`` / ``INFO_REQUEST_INTERRUPT`` SSE events.

    Attributes:
        id: Stable UUID for the evidence package.
        title: Short human-readable summary.
        narrative: 2-5 sentence plain-English explanation.
        reasoning_trace: Compressed reasoning steps (NOT full CoT).
        recommended_actions: 1-3 action options for the approver.
        source_agent_id: Agent that produced this package.
        task_id: Related task, if any.
        risk_level: Risk classification.
        metadata: Additional key-value metadata.
    """

    id: NotBlankStr = Field(description="Stable evidence package UUID")
    title: NotBlankStr = Field(description="Short human-readable summary")
    narrative: NotBlankStr = Field(
        description="Plain-English explanation (2-5 sentences)",
    )
    reasoning_trace: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Compressed reasoning steps",
    )
    recommended_actions: tuple[RecommendedAction, ...] = Field(
        min_length=1,
        description="Action options for the approver (1-3)",
    )
    source_agent_id: NotBlankStr = Field(
        description="Producing agent identifier",
    )
    task_id: NotBlankStr | None = Field(
        default=None,
        description="Related task identifier",
    )
    risk_level: ApprovalRiskLevel = Field(
        description="Risk classification",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Additional key-value metadata",
    )

    @model_validator(mode="after")
    def _deep_copy_metadata(self) -> Self:
        """Deep-copy metadata to prevent external mutation."""
        object.__setattr__(self, "metadata", copy.deepcopy(self.metadata))
        return self
