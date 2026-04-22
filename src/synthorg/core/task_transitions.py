"""Task lifecycle state machine transitions.

Defines the valid state transitions for the task lifecycle, based on
the Engine design page, extended with BLOCKED, CANCELLED,
FAILED, INTERRUPTED, SUSPENDED, REJECTED, and AUTH_REQUIRED
transitions for completeness::

    CREATED -> ASSIGNED | REJECTED
    ASSIGNED -> IN_PROGRESS | AUTH_REQUIRED | BLOCKED | CANCELLED
               | FAILED | INTERRUPTED | SUSPENDED
    IN_PROGRESS -> IN_REVIEW | AUTH_REQUIRED | BLOCKED | CANCELLED
                   | FAILED | INTERRUPTED | SUSPENDED
    IN_REVIEW -> COMPLETED | IN_PROGRESS (rework) | BLOCKED | CANCELLED
    AUTH_REQUIRED -> ASSIGNED (approved) | CANCELLED (denied/timeout)
    BLOCKED -> ASSIGNED (unblocked)
    FAILED -> ASSIGNED (reassignment for retry)
    INTERRUPTED -> ASSIGNED (reassignment on restart)
    SUSPENDED -> ASSIGNED (resume from checkpoint)

COMPLETED, CANCELLED, and REJECTED are terminal states with no
outgoing transitions.  FAILED, INTERRUPTED, and SUSPENDED are
non-terminal (can be reassigned).  AUTH_REQUIRED is non-terminal
(waiting for authorization).
"""

from typing import Final

from synthorg.core.enums import TaskStatus
from synthorg.core.state_machine import StateMachine
from synthorg.observability.events.task import (
    TASK_TRANSITION_CONFIG_ERROR,
    TASK_TRANSITION_INVALID,
)

VALID_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.CREATED: frozenset({TaskStatus.ASSIGNED, TaskStatus.REJECTED}),
    TaskStatus.ASSIGNED: frozenset(
        {
            TaskStatus.IN_PROGRESS,
            TaskStatus.AUTH_REQUIRED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
            TaskStatus.INTERRUPTED,
            TaskStatus.SUSPENDED,
        }
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {
            TaskStatus.IN_REVIEW,
            TaskStatus.AUTH_REQUIRED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
            TaskStatus.INTERRUPTED,
            TaskStatus.SUSPENDED,
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
    TaskStatus.AUTH_REQUIRED: frozenset({TaskStatus.ASSIGNED, TaskStatus.CANCELLED}),
    TaskStatus.BLOCKED: frozenset({TaskStatus.ASSIGNED}),
    TaskStatus.FAILED: frozenset({TaskStatus.ASSIGNED}),  # reassignment
    TaskStatus.INTERRUPTED: frozenset({TaskStatus.ASSIGNED}),  # reassignment on restart
    TaskStatus.SUSPENDED: frozenset({TaskStatus.ASSIGNED}),  # resume from checkpoint
    TaskStatus.COMPLETED: frozenset(),  # terminal
    TaskStatus.CANCELLED: frozenset(),  # terminal
    TaskStatus.REJECTED: frozenset(),  # terminal
}

_MACHINE: Final[StateMachine[TaskStatus]] = StateMachine(
    VALID_TRANSITIONS,
    name="task_status",
    display_label="task status",
    invalid_event=TASK_TRANSITION_INVALID,
    config_event=TASK_TRANSITION_CONFIG_ERROR,
    all_states=TaskStatus,
)


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Validate that a state transition is allowed.

    Args:
        current: The current task status.
        target: The desired target status.

    Raises:
        ValueError: If the transition from *current* to *target*
            is not in :data:`VALID_TRANSITIONS`.
    """
    _MACHINE.validate(current, target)
