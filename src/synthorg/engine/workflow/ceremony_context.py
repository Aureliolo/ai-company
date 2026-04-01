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
