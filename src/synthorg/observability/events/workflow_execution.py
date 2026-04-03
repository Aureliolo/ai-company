"""Workflow execution event name constants for observability.

Covers activation, task creation, condition evaluation, and
lifecycle transitions of workflow execution instances.
"""

from typing import Final

# -- Activation events --------------------------------------------------------

WORKFLOW_EXEC_ACTIVATED: Final[str] = "workflow.execution.activated"
"""Workflow definition activated -- execution instance created."""

WORKFLOW_EXEC_INVALID_DEFINITION: Final[str] = "workflow.execution.invalid_definition"
"""Activation rejected -- workflow definition failed validation."""

WORKFLOW_EXEC_NOT_FOUND: Final[str] = "workflow.execution.not_found"
"""Workflow execution instance not found."""

# -- Node processing events ---------------------------------------------------

WORKFLOW_EXEC_TASK_CREATED: Final[str] = "workflow.execution.task_created"
"""Concrete task created from a TASK node."""

WORKFLOW_EXEC_NODE_SKIPPED: Final[str] = "workflow.execution.node_skipped"
"""Node skipped (conditional branch not taken)."""

WORKFLOW_EXEC_NODE_COMPLETED: Final[str] = "workflow.execution.node_completed"
"""Control node processed (START, END, SPLIT, JOIN, etc.)."""

WORKFLOW_EXEC_CONDITION_EVALUATED: Final[str] = "workflow.execution.condition_evaluated"
"""Conditional node expression evaluated."""

WORKFLOW_EXEC_CONDITION_EVAL_FAILED: Final[str] = (
    "workflow.execution.condition_eval_failed"
)
"""Conditional node expression evaluation failed."""

# -- Lifecycle events ---------------------------------------------------------

WORKFLOW_EXEC_COMPLETED: Final[str] = "workflow.execution.completed"
"""Workflow execution completed -- all tasks finished."""

WORKFLOW_EXEC_FAILED: Final[str] = "workflow.execution.failed"
"""Workflow execution failed."""

WORKFLOW_EXEC_CANCELLED: Final[str] = "workflow.execution.cancelled"
"""Workflow execution cancelled by user."""

WORKFLOW_EXEC_PERSISTENCE_FAILED: Final[str] = "workflow.execution.persistence_failed"
"""Persistence operation failed during workflow execution."""
