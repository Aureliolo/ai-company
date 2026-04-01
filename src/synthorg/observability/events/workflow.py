"""Workflow event name constants for observability.

Covers both Kanban board and Agile sprint workflow types.
"""

# -- Kanban events ----------------------------------------------------------

KANBAN_COLUMN_TRANSITION: str = "workflow.kanban.column_transition"
"""Task moved between Kanban columns."""

KANBAN_WIP_LIMIT_REACHED: str = "workflow.kanban.wip_limit_reached"
"""Column WIP count equals the configured limit."""

KANBAN_WIP_LIMIT_EXCEEDED: str = "workflow.kanban.wip_limit_exceeded"
"""Column WIP count exceeds the configured limit."""

KANBAN_COLUMN_TRANSITION_INVALID: str = "workflow.kanban.column_transition_invalid"
"""Invalid Kanban column transition attempted."""

KANBAN_STATUS_PATH_MISSING: str = "workflow.kanban.status_path_missing"
"""No task status path defined for a column move."""

WORKFLOW_CONFIG_UNUSED_SUBCONFIG: str = "workflow.config.unused_subconfig"
"""Sub-config customized for an inactive workflow type (advisory)."""

KANBAN_CONFIG_VALIDATION_FAILED: str = "workflow.kanban.config_validation_failed"
"""Kanban configuration validation failed."""

KANBAN_TASK_PLACED: str = "workflow.kanban.task_placed"
"""Task placed on the Kanban board (initial column assignment)."""

# -- Sprint events ----------------------------------------------------------

SPRINT_CREATED: str = "workflow.sprint.created"
"""New sprint created."""

SPRINT_LIFECYCLE_TRANSITION: str = "workflow.sprint.lifecycle_transition"
"""Sprint transitioned between lifecycle statuses."""

SPRINT_LIFECYCLE_TRANSITION_INVALID: str = (
    "workflow.sprint.lifecycle_transition_invalid"
)
"""Invalid sprint lifecycle transition attempted."""

SPRINT_TASK_ADDED: str = "workflow.sprint.task_added"
"""Task added to sprint backlog."""

SPRINT_TASK_REMOVED: str = "workflow.sprint.task_removed"
"""Task removed from sprint backlog."""

SPRINT_TASK_COMPLETED: str = "workflow.sprint.task_completed"
"""Task marked completed within a sprint."""

SPRINT_BACKLOG_INVALID: str = "workflow.sprint.backlog_invalid"
"""Invalid sprint backlog operation attempted."""

SPRINT_VELOCITY_INVALID: str = "workflow.sprint.velocity_invalid"
"""Invalid velocity operation attempted."""

SPRINT_VELOCITY_RECORDED: str = "workflow.sprint.velocity_recorded"
"""Velocity record created from a completed sprint."""

SPRINT_CEREMONY_SCHEDULED: str = "workflow.sprint.ceremony_scheduled"
"""Sprint ceremony scheduled."""

SPRINT_CEREMONY_TRIGGERED: str = "workflow.sprint.ceremony_triggered"
"""Sprint ceremony triggered by strategy evaluation."""

SPRINT_CEREMONY_SKIPPED: str = "workflow.sprint.ceremony_skipped"
"""Ceremony evaluation returned false -- ceremony not fired."""

SPRINT_AUTO_TRANSITION: str = "workflow.sprint.auto_transition"
"""Sprint auto-transitioned by ceremony scheduling strategy."""

SPRINT_CEREMONY_SCHEDULER_STARTED: str = "workflow.sprint.ceremony_scheduler_started"
"""CeremonyScheduler activated for a sprint."""

SPRINT_CEREMONY_SCHEDULER_STOPPED: str = "workflow.sprint.ceremony_scheduler_stopped"
"""CeremonyScheduler deactivated."""

SPRINT_CEREMONY_BRIDGE_CREATED: str = "workflow.sprint.ceremony_bridge_created"
"""Sprint ceremony config bridged to meeting type config."""

SPRINT_CEREMONY_POLICY_RESOLVED: str = "workflow.sprint.ceremony_policy_resolved"
"""3-level ceremony policy resolution completed."""

SPRINT_CEREMONY_STRATEGY_CHANGED: str = "workflow.sprint.ceremony_strategy_changed"
"""Ceremony scheduling strategy changed between sprints."""
