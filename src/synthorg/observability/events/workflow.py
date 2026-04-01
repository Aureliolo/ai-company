"""Workflow event name constants for observability.

Covers both Kanban board and Agile sprint workflow types.
"""

# -- Kanban events ----------------------------------------------------------

KANBAN_COLUMN_TRANSITION: str = "workflow.kanban.column_transition"
"""Task moved between Kanban columns."""

KANBAN_WIP_LIMIT_REACHED: str = "workflow.kanban.wip_limit_reached"
"""Column WIP count equals the configured limit."""

KANBAN_WIP_LIMIT_EXCEEDED: str = "workflow.kanban.wip_limit_exceeded"
"""Column WIP count exceeds the configured limit (advisory mode)."""

KANBAN_TASK_PLACED: str = "workflow.kanban.task_placed"
"""Task placed on the Kanban board (initial column assignment)."""

# -- Sprint events ----------------------------------------------------------

SPRINT_CREATED: str = "workflow.sprint.created"
"""New sprint created."""

SPRINT_LIFECYCLE_TRANSITION: str = "workflow.sprint.lifecycle_transition"
"""Sprint transitioned between lifecycle statuses."""

SPRINT_TASK_ADDED: str = "workflow.sprint.task_added"
"""Task added to sprint backlog."""

SPRINT_TASK_REMOVED: str = "workflow.sprint.task_removed"
"""Task removed from sprint backlog."""

SPRINT_VELOCITY_RECORDED: str = "workflow.sprint.velocity_recorded"
"""Velocity record created from a completed sprint."""

SPRINT_CEREMONY_SCHEDULED: str = "workflow.sprint.ceremony_scheduled"
"""Sprint ceremony scheduled."""
