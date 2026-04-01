"""Kanban board column definitions, transitions, and task status bridge.

Defines the five Kanban columns from the Engine design page and their
relationship to the task lifecycle state machine.  Column transitions
are validated independently of (and mapped onto) task status transitions.
"""

from enum import StrEnum
from types import MappingProxyType

from synthorg.core.enums import TaskStatus
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import KANBAN_COLUMN_TRANSITION

logger = get_logger(__name__)


class KanbanColumn(StrEnum):
    """Kanban board columns matching the Engine design page.

    Members:
        BACKLOG: Tasks waiting to be prioritized.
        READY: Prioritized and ready for assignment.
        IN_PROGRESS: Actively being worked on.
        REVIEW: Work complete, awaiting review.
        DONE: Finished and accepted.
    """

    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


# -- Column <-> TaskStatus bridge -------------------------------------------

COLUMN_TO_STATUSES: MappingProxyType[KanbanColumn, frozenset[TaskStatus]] = (
    MappingProxyType(
        {
            KanbanColumn.BACKLOG: frozenset({TaskStatus.CREATED}),
            KanbanColumn.READY: frozenset({TaskStatus.ASSIGNED}),
            KanbanColumn.IN_PROGRESS: frozenset({TaskStatus.IN_PROGRESS}),
            KanbanColumn.REVIEW: frozenset({TaskStatus.IN_REVIEW}),
            KanbanColumn.DONE: frozenset({TaskStatus.COMPLETED}),
        }
    )
)

# Off-board statuses (BLOCKED, FAILED, INTERRUPTED, CANCELLED) map to
# None -- temporarily or permanently removed from the board.
STATUS_TO_COLUMN: MappingProxyType[TaskStatus, KanbanColumn | None] = MappingProxyType(
    {
        TaskStatus.CREATED: KanbanColumn.BACKLOG,
        TaskStatus.ASSIGNED: KanbanColumn.READY,
        TaskStatus.IN_PROGRESS: KanbanColumn.IN_PROGRESS,
        TaskStatus.IN_REVIEW: KanbanColumn.REVIEW,
        TaskStatus.COMPLETED: KanbanColumn.DONE,
        TaskStatus.BLOCKED: None,
        TaskStatus.FAILED: None,
        TaskStatus.INTERRUPTED: None,
        TaskStatus.CANCELLED: None,
    }
)

# -- Module-level guards ----------------------------------------------------

_missing_columns = set(KanbanColumn) - set(COLUMN_TO_STATUSES)
if _missing_columns:
    _msg = (
        f"Missing COLUMN_TO_STATUSES entries for: "
        f"{sorted(c.value for c in _missing_columns)}"
    )
    raise ValueError(_msg)

_missing_statuses = set(TaskStatus) - set(STATUS_TO_COLUMN)
if _missing_statuses:
    _msg = (
        f"Missing STATUS_TO_COLUMN entries for: "
        f"{sorted(s.value for s in _missing_statuses)}"
    )
    raise ValueError(_msg)

# Verify that on-board statuses in STATUS_TO_COLUMN are consistent with
# COLUMN_TO_STATUSES (every status that maps to a column must appear in
# that column's status set).
for _status, _column in STATUS_TO_COLUMN.items():
    if _column is not None and _status not in COLUMN_TO_STATUSES[_column]:
        _msg = (
            f"STATUS_TO_COLUMN maps {_status.value!r} to "
            f"{_column.value!r}, but COLUMN_TO_STATUSES[{_column.value!r}] "
            f"does not include {_status.value!r}"
        )
        raise ValueError(_msg)


# -- Column transitions -----------------------------------------------------

VALID_COLUMN_TRANSITIONS: dict[KanbanColumn, frozenset[KanbanColumn]] = {
    KanbanColumn.BACKLOG: frozenset({KanbanColumn.READY, KanbanColumn.DONE}),
    KanbanColumn.READY: frozenset({KanbanColumn.IN_PROGRESS, KanbanColumn.BACKLOG}),
    KanbanColumn.IN_PROGRESS: frozenset(
        {
            KanbanColumn.REVIEW,
            KanbanColumn.BACKLOG,
            KanbanColumn.READY,
        }
    ),
    KanbanColumn.REVIEW: frozenset({KanbanColumn.DONE, KanbanColumn.IN_PROGRESS}),
    KanbanColumn.DONE: frozenset(),  # terminal
}

_missing_col_transitions = set(KanbanColumn) - set(VALID_COLUMN_TRANSITIONS)
if _missing_col_transitions:
    _msg = (
        f"Missing VALID_COLUMN_TRANSITIONS entries for: "
        f"{sorted(c.value for c in _missing_col_transitions)}"
    )
    raise ValueError(_msg)


# -- Task status transition paths per column move ---------------------------
# Maps (from_column, to_column) to the sequence of TaskStatus values
# the task must pass through.  Multi-step when columns are not adjacent
# in the task state machine (e.g. BACKLOG->DONE skips intermediate
# statuses).

_COLUMN_MOVE_STATUS_PATH: dict[
    tuple[KanbanColumn, KanbanColumn], tuple[TaskStatus, ...]
] = {
    # BACKLOG -> ...
    (KanbanColumn.BACKLOG, KanbanColumn.READY): (TaskStatus.ASSIGNED,),
    (KanbanColumn.BACKLOG, KanbanColumn.DONE): (
        TaskStatus.ASSIGNED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.IN_REVIEW,
        TaskStatus.COMPLETED,
    ),
    # READY -> ...
    (KanbanColumn.READY, KanbanColumn.IN_PROGRESS): (TaskStatus.IN_PROGRESS,),
    (KanbanColumn.READY, KanbanColumn.BACKLOG): (
        TaskStatus.BLOCKED,
        TaskStatus.ASSIGNED,
        TaskStatus.BLOCKED,
    ),
    # IN_PROGRESS -> ...
    (KanbanColumn.IN_PROGRESS, KanbanColumn.REVIEW): (TaskStatus.IN_REVIEW,),
    (KanbanColumn.IN_PROGRESS, KanbanColumn.BACKLOG): (
        TaskStatus.BLOCKED,
        TaskStatus.ASSIGNED,
        TaskStatus.BLOCKED,
    ),
    (KanbanColumn.IN_PROGRESS, KanbanColumn.READY): (
        TaskStatus.BLOCKED,
        TaskStatus.ASSIGNED,
    ),
    # REVIEW -> ...
    (KanbanColumn.REVIEW, KanbanColumn.DONE): (TaskStatus.COMPLETED,),
    (KanbanColumn.REVIEW, KanbanColumn.IN_PROGRESS): (TaskStatus.IN_PROGRESS,),
}


def validate_column_transition(
    current: KanbanColumn,
    target: KanbanColumn,
) -> None:
    """Validate that a Kanban column transition is allowed.

    Args:
        current: The current column.
        target: The desired target column.

    Raises:
        ValueError: If the transition is not allowed.
    """
    if current not in VALID_COLUMN_TRANSITIONS:
        msg = (
            f"KanbanColumn {current.value!r} has no entry in VALID_COLUMN_TRANSITIONS."
        )
        raise ValueError(msg)
    allowed = VALID_COLUMN_TRANSITIONS[current]
    if target not in allowed:
        msg = (
            f"Invalid Kanban column transition: "
            f"{current.value!r} -> {target.value!r}. "
            f"Allowed from {current.value!r}: "
            f"{sorted(c.value for c in allowed)}"
        )
        raise ValueError(msg)
    logger.info(
        KANBAN_COLUMN_TRANSITION,
        from_column=current.value,
        to_column=target.value,
    )


def resolve_task_transitions(
    from_column: KanbanColumn,
    to_column: KanbanColumn,
) -> tuple[TaskStatus, ...]:
    """Return the TaskStatus path for a Kanban column move.

    The caller must apply these transitions sequentially to the task
    via the TaskEngine.  Does NOT validate the column transition itself
    -- call :func:`validate_column_transition` first.

    Args:
        from_column: Source column.
        to_column: Target column.

    Returns:
        Ordered tuple of TaskStatus values the task must pass through.

    Raises:
        ValueError: If no status path is defined for this column pair.
    """
    key = (from_column, to_column)
    path = _COLUMN_MOVE_STATUS_PATH.get(key)
    if path is None:
        msg = (
            f"No task status path defined for column move "
            f"{from_column.value!r} -> {to_column.value!r}"
        )
        raise ValueError(msg)
    return path
