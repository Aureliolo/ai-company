"""Evolver cycle report model.

Contains the results of a single evolution cycle for R3 eval loop
consumption and audit.
"""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.approval import ApprovalItem  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.procedural.supersession import (  # noqa: TC001
    SupersessionResult,
)


class EvolverReport(BaseModel):
    """Summary of a single skill evolution cycle.

    Consumed by the R3 ``EvalLoopCoordinator`` for org learning
    metrics and audit.

    Attributes:
        cycle_id: Unique cycle identifier.
        window_start: Beginning of the analysis window.
        window_end: End of the analysis window.
        trajectories_analyzed: Total trajectories examined.
        patterns_found: Patterns identified by the aggregator.
        proposals_emitted: ApprovalItems emitted for human review.
        conflicts: Supersession conflicts detected.
        supersessions: Full supersessions detected.
        skipped_low_confidence: Proposals skipped due to low
            confidence.
        skipped_below_agent_threshold: Proposals skipped because
            too few agents exhibited the pattern.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    cycle_id: NotBlankStr = Field(description="Unique cycle identifier")
    window_start: AwareDatetime = Field(
        description="Analysis window start",
    )
    window_end: AwareDatetime = Field(
        description="Analysis window end",
    )
    trajectories_analyzed: int = Field(
        ge=0,
        description="Total trajectories examined",
    )
    patterns_found: int = Field(
        ge=0,
        description="Patterns identified",
    )
    proposals_emitted: tuple[ApprovalItem, ...] = Field(
        default=(),
        description="ApprovalItems emitted for human review",
    )
    conflicts: tuple[SupersessionResult, ...] = Field(
        default=(),
        description="Supersession conflicts detected",
    )
    supersessions: tuple[SupersessionResult, ...] = Field(
        default=(),
        description="Full supersessions detected",
    )
    skipped_low_confidence: int = Field(
        default=0,
        ge=0,
        description="Proposals skipped (low confidence)",
    )
    skipped_below_agent_threshold: int = Field(
        default=0,
        ge=0,
        description="Proposals skipped (few agents)",
    )
