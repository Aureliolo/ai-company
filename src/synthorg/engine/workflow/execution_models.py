"""Workflow execution models.

A ``WorkflowExecution`` is a runtime instance of a
``WorkflowDefinition``.  It tracks per-node execution state
and maps TASK nodes to concrete ``Task`` instances created
via the ``TaskEngine``.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.enums import (
    WorkflowExecutionStatus,
    WorkflowNodeExecutionStatus,
    WorkflowNodeType,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001


class WorkflowNodeExecution(BaseModel):
    """Per-node execution state within a workflow execution.

    Attributes:
        node_id: ID of the node in the source ``WorkflowDefinition``.
        node_type: Type of the node (task, conditional, etc.).
        status: Current processing status.
        task_id: Concrete task ID when a TASK node has been
            instantiated (``None`` for control nodes and pending nodes).
        skipped_reason: Explanation when the node was skipped
            (e.g. conditional branch not taken).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    node_id: NotBlankStr = Field(description="Source node ID")
    node_type: WorkflowNodeType = Field(description="Node type")
    status: WorkflowNodeExecutionStatus = Field(
        default=WorkflowNodeExecutionStatus.PENDING,
        description="Processing status",
    )
    task_id: NotBlankStr | None = Field(
        default=None,
        description="Concrete task ID (TASK nodes only)",
    )
    skipped_reason: str | None = Field(
        default=None,
        description="Reason when status is SKIPPED",
    )


class WorkflowExecution(BaseModel):
    """Runtime instance of an activated workflow definition.

    Created when a user activates a ``WorkflowDefinition``.
    Tracks the overall execution lifecycle and per-node
    processing state.

    Attributes:
        id: Unique execution identifier (``"wfexec-{uuid12}"``).
        definition_id: Source ``WorkflowDefinition`` ID.
        definition_version: Snapshot of the definition's version
            at activation time.
        status: Overall execution lifecycle status.
        node_executions: Per-node execution state.
        activated_by: Identity of the user who triggered activation.
        project: Project ID for all created tasks.
        created_at: Creation timestamp (UTC).
        updated_at: Last update timestamp (UTC).
        completed_at: Completion timestamp (``None`` until terminal).
        error: Error message when status is ``FAILED``.
        version: Optimistic concurrency version counter.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(description="Unique execution ID")
    definition_id: NotBlankStr = Field(description="Source definition ID")
    definition_version: int = Field(
        ge=1,
        description="Definition version at activation time",
    )
    status: WorkflowExecutionStatus = Field(
        default=WorkflowExecutionStatus.PENDING,
        description="Overall execution status",
    )
    node_executions: tuple[WorkflowNodeExecution, ...] = Field(
        default=(),
        description="Per-node execution state",
    )
    activated_by: NotBlankStr = Field(
        description="User who triggered activation",
    )
    project: NotBlankStr = Field(
        description="Project ID for created tasks",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp (UTC)",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Completion timestamp",
    )
    error: str | None = Field(
        default=None,
        description="Error message when FAILED",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Optimistic concurrency version",
    )
