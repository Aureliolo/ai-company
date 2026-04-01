"""Umbrella workflow configuration model.

Aggregates the per-workflow-type configs (Kanban, Sprint) under a
single ``WorkflowConfig`` that plugs into the root configuration.
"""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.enums import WorkflowType
from synthorg.engine.workflow.kanban_board import KanbanConfig
from synthorg.engine.workflow.sprint_config import SprintConfig


class WorkflowConfig(BaseModel):
    """Top-level workflow configuration.

    Attributes:
        workflow_type: Active workflow type.
        kanban: Kanban board settings (used when workflow_type
            is ``KANBAN`` or ``AGILE_KANBAN``).
        sprint: Agile sprint settings (used when workflow_type
            is ``AGILE_KANBAN``).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    workflow_type: WorkflowType = Field(
        default=WorkflowType.AGILE_KANBAN,
        description="Active workflow type",
    )
    kanban: KanbanConfig = Field(
        default_factory=KanbanConfig,
        description="Kanban board settings",
    )
    sprint: SprintConfig = Field(
        default_factory=SprintConfig,
        description="Agile sprint settings",
    )
