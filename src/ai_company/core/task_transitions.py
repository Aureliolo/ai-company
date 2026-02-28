"""Task lifecycle state machine transitions.

Defines the valid state transitions for the task lifecycle, based on
DESIGN_SPEC Section 6.1 and extended with BLOCKED and CANCELLED
transitions from IN_PROGRESS and IN_REVIEW for completeness::

    CREATED -> ASSIGNED
    ASSIGNED -> IN_PROGRESS | BLOCKED | CANCELLED
    IN_PROGRESS -> IN_REVIEW | BLOCKED | CANCELLED
    IN_REVIEW -> COMPLETED | IN_PROGRESS (rework) | BLOCKED | CANCELLED
    BLOCKED -> ASSIGNED (unblocked)

COMPLETED and CANCELLED are terminal states with no outgoing
transitions.
"""

from ai_company.core.enums import TaskStatus

VALID_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.CREATED: frozenset({TaskStatus.ASSIGNED}),
    TaskStatus.ASSIGNED: frozenset(
        {
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {
            TaskStatus.IN_REVIEW,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.IN_REVIEW: frozenset(
        {
            TaskStatus.COMPLETED,
            TaskStatus.IN_PROGRESS,  # rework
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.BLOCKED: frozenset({TaskStatus.ASSIGNED}),
    TaskStatus.COMPLETED: frozenset(),  # terminal
    TaskStatus.CANCELLED: frozenset(),  # terminal
}


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Validate that a state transition is allowed.

    Args:
        current: The current task status.
        target: The desired target status.

    Raises:
        ValueError: If the transition from *current* to *target*
            is not in :data:`VALID_TRANSITIONS`.
    """
    if current not in VALID_TRANSITIONS:
        msg = (
            f"TaskStatus {current.value!r} has no entry in VALID_TRANSITIONS. "
            f"This is a configuration error — update task_transitions.py."
        )
        raise ValueError(msg)
    allowed = VALID_TRANSITIONS[current]
    if target not in allowed:
        msg = (
            f"Invalid task status transition: {current.value!r} -> "
            f"{target.value!r}. Allowed from {current.value!r}: "
            f"{sorted(s.value for s in allowed)}"
        )
        raise ValueError(msg)
