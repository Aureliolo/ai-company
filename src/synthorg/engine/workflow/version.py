"""Workflow definition version snapshot model.

A ``WorkflowDefinitionVersion`` is an immutable historical snapshot
of a workflow definition at a specific version number, created on
every save.
"""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.enums import WorkflowType  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.definition import (  # noqa: TC001
    WorkflowEdge,
    WorkflowNode,
)


class WorkflowDefinitionVersion(BaseModel):
    """Immutable snapshot of a workflow definition at a point in time.

    Version snapshots are never updated or re-validated after creation.
    They store the exact state of the definition when it was saved.

    Attributes:
        definition_id: ID of the parent workflow definition.
        version: Version number (matches the definition's version counter).
        name: Workflow name at this version.
        description: Description at this version.
        workflow_type: Workflow type at this version.
        nodes: Full node graph snapshot.
        edges: Full edge graph snapshot.
        created_by: Original creator of the definition.
        saved_by: User who performed this specific save.
        saved_at: Timestamp of this save.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    definition_id: NotBlankStr = Field(description="Parent definition ID")
    version: int = Field(ge=1, description="Version number")
    name: NotBlankStr = Field(description="Workflow name at this version")
    description: str = Field(default="", description="Description at this version")
    workflow_type: WorkflowType = Field(description="Workflow type at this version")
    nodes: tuple[WorkflowNode, ...] = Field(
        default=(),
        description="Node graph snapshot",
    )
    edges: tuple[WorkflowEdge, ...] = Field(
        default=(),
        description="Edge graph snapshot",
    )
    created_by: NotBlankStr = Field(description="Original definition creator")
    saved_by: NotBlankStr = Field(description="User who performed this save")
    saved_at: AwareDatetime = Field(description="Timestamp of this save")
