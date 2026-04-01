"""Sprint velocity tracking -- records and rolling averages.

Provides the ``VelocityRecord`` model and functions for recording
velocity from completed sprints and computing rolling averages.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, computed_field

if TYPE_CHECKING:
    from collections.abc import Sequence

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
    SPRINT_VELOCITY_INVALID,
    SPRINT_VELOCITY_RECORDED,
)

logger = get_logger(__name__)


class VelocityRecord(BaseModel):
    """Velocity snapshot from a completed sprint.

    Attributes:
        sprint_id: ID of the completed sprint.
        sprint_number: Sequential sprint number.
        story_points_committed: Points planned for the sprint.
        story_points_completed: Points actually delivered.
        duration_days: Sprint duration in days.
        completion_ratio: Ratio of completed to committed points
            (computed; 0.0 when nothing was committed).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    sprint_id: NotBlankStr = Field(
        description="ID of the completed sprint",
    )
    sprint_number: int = Field(
        ge=1,
        description="Sequential sprint number",
    )
    story_points_committed: float = Field(
        ge=0.0,
        description="Points planned",
    )
    story_points_completed: float = Field(
        ge=0.0,
        description="Points delivered",
    )
    duration_days: int = Field(
        ge=1,
        description="Sprint duration in days",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completion_ratio(self) -> float:
        """Ratio of completed to committed points."""
        if self.story_points_committed == 0.0:
            return 0.0
        return self.story_points_completed / self.story_points_committed


def record_velocity(sprint: Sprint) -> VelocityRecord:
    """Create a VelocityRecord from a completed sprint.

    Args:
        sprint: A sprint in COMPLETED status.

    Returns:
        A velocity record capturing the sprint's delivery metrics.

    Raises:
        ValueError: If the sprint is not COMPLETED.
    """
    if sprint.status is not SprintStatus.COMPLETED:
        msg = (
            f"Cannot record velocity for sprint {sprint.id!r} "
            f"in status {sprint.status.value!r} -- "
            f"must be 'completed'"
        )
        logger.warning(
            SPRINT_VELOCITY_INVALID,
            sprint_id=sprint.id,
            status=sprint.status.value,
            reason="not_completed",
        )
        raise ValueError(msg)
    record = VelocityRecord(
        sprint_id=sprint.id,
        sprint_number=sprint.sprint_number,
        story_points_committed=sprint.story_points_committed,
        story_points_completed=sprint.story_points_completed,
        duration_days=sprint.duration_days,
    )
    logger.info(
        SPRINT_VELOCITY_RECORDED,
        sprint_id=sprint.id,
        sprint_number=sprint.sprint_number,
        points_committed=sprint.story_points_committed,
        points_completed=sprint.story_points_completed,
        completion_ratio=record.completion_ratio,
    )
    return record


def calculate_average_velocity(
    records: Sequence[VelocityRecord],
    window: int = 3,
) -> float:
    """Compute rolling average of story_points_completed.

    Uses the last *window* records (by position, not sprint number).
    Returns 0.0 when the sequence is empty.

    Args:
        records: Ordered velocity records (oldest first).
        window: Number of recent sprints to average over.

    Returns:
        Average story points completed per sprint.

    Raises:
        ValueError: If *window* is less than 1.
    """
    if window < 1:
        msg = f"window must be >= 1, got {window}"
        logger.warning(SPRINT_VELOCITY_INVALID, window=window, reason="invalid_window")
        raise ValueError(msg)
    if not records:
        return 0.0
    recent = records[-window:]
    total = sum(r.story_points_completed for r in recent)
    return total / len(recent)
