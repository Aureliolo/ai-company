"""Ceremony evaluation context -- rich context passed to strategies.

Provides the ``CeremonyEvalContext`` frozen dataclass that bundles all
information a ``CeremonySchedulingStrategy`` might need to evaluate
whether a ceremony should fire or a sprint should auto-transition.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthorg.engine.workflow.sprint_velocity import VelocityRecord


@dataclass(frozen=True, slots=True)
class CeremonyEvalContext:
    """Rich context passed to ceremony scheduling strategies.

    All fields represent the state at evaluation time (after the event
    that triggered the evaluation).

    Attributes:
        completions_since_last_trigger: Task completions since this
            ceremony's trigger last fired.
        total_completions_this_sprint: Total task completions in the
            current sprint.
        total_tasks_in_sprint: Total tasks in the sprint backlog.
        elapsed_seconds: Wall-clock seconds since sprint activation.
        budget_consumed_fraction: Budget consumed as a fraction of
            total (0.0--1.0).  ``0.0`` when budget tracking is not
            active.
        budget_remaining: Remaining budget in base currency.  ``0.0``
            when budget tracking is not active.
        velocity_history: Recent velocity records for rolling average
            calculations (oldest first).
        external_events: Pending external event names that have been
            received but not yet processed.
        sprint_percentage_complete: Fraction of tasks complete by
            task count (0.0--1.0).
        story_points_completed: Story points delivered so far.
        story_points_committed: Story points planned for the sprint.
    """

    completions_since_last_trigger: int
    total_completions_this_sprint: int
    total_tasks_in_sprint: int
    elapsed_seconds: float
    budget_consumed_fraction: float
    budget_remaining: float
    velocity_history: tuple[VelocityRecord, ...]
    external_events: tuple[str, ...]
    sprint_percentage_complete: float
    story_points_completed: float
    story_points_committed: float

    def __post_init__(self) -> None:
        """Validate field constraints."""
        if self.completions_since_last_trigger < 0:
            msg = "completions_since_last_trigger must be >= 0"
            raise ValueError(msg)
        if self.total_completions_this_sprint < 0:
            msg = "total_completions_this_sprint must be >= 0"
            raise ValueError(msg)
        if self.total_tasks_in_sprint < 0:
            msg = "total_tasks_in_sprint must be >= 0"
            raise ValueError(msg)
        if self.elapsed_seconds < 0.0:
            msg = "elapsed_seconds must be >= 0.0"
            raise ValueError(msg)
        if not 0.0 <= self.budget_consumed_fraction <= 1.0:
            msg = "budget_consumed_fraction must be in [0.0, 1.0]"
            raise ValueError(msg)
        if self.budget_remaining < 0.0:
            msg = "budget_remaining must be >= 0.0"
            raise ValueError(msg)
        if not 0.0 <= self.sprint_percentage_complete <= 1.0:
            msg = "sprint_percentage_complete must be in [0.0, 1.0]"
            raise ValueError(msg)
        if self.story_points_completed < 0.0:
            msg = "story_points_completed must be >= 0.0"
            raise ValueError(msg)
        if self.story_points_committed < 0.0:
            msg = "story_points_committed must be >= 0.0"
            raise ValueError(msg)
