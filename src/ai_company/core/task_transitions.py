"""Task lifecycle state machine transitions.

Defines the valid state transitions for the task lifecycle per
DESIGN_SPEC Section 6.1.  The transition map is derived from the
state diagram::

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
    allowed = VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        msg = (
            f"Invalid task status transition: {current.value!r} -> "
            f"{target.value!r}. Allowed from {current.value!r}: "
            f"{sorted(s.value for s in allowed)}"
        )
        raise ValueError(msg)
