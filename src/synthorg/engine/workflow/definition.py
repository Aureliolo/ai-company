"""Visual workflow definition models.

A ``WorkflowDefinition`` is a design-time blueprint -- a saveable
directed graph of workflow nodes and edges that can be validated and
exported as YAML for the engine's coordination/decomposition system.

This is distinct from ``WorkflowConfig`` (runtime operational config
for Kanban/Sprint settings).
"""

from collections import Counter
from collections.abc import Mapping  # noqa: TC003
from datetime import UTC, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.enums import WorkflowEdgeType, WorkflowNodeType, WorkflowType
from synthorg.core.types import NotBlankStr  # noqa: TC001


class WorkflowNode(BaseModel):
    """A single node in a visual workflow graph.

    Attributes:
        id: Unique identifier within the workflow definition.
        type: Node type (task, conditional, parallel split/join, etc.).
        label: Display label for the node.
        position_x: Horizontal position on the visual canvas.
        position_y: Vertical position on the visual canvas.
        config: Type-specific configuration (task type, priority,
            agent role, condition expression, etc.).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(description="Unique node identifier")
    type: WorkflowNodeType = Field(description="Node type")
    label: NotBlankStr = Field(description="Display label")
    position_x: float = Field(default=0.0, description="Canvas X position")
    position_y: float = Field(default=0.0, description="Canvas Y position")
    config: Mapping[str, object] = Field(
        default_factory=dict,
        description="Type-specific configuration",
    )


class WorkflowEdge(BaseModel):
    """A directed edge connecting two workflow nodes.

    Attributes:
        id: Unique identifier within the workflow definition.
        source_node_id: ID of the source node.
        target_node_id: ID of the target node.
        type: Edge type (sequential, conditional branch, parallel).
        label: Optional display label (e.g. condition text).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(description="Unique edge identifier")
    source_node_id: NotBlankStr = Field(description="Source node ID")
    target_node_id: NotBlankStr = Field(description="Target node ID")
    type: WorkflowEdgeType = Field(
        default=WorkflowEdgeType.SEQUENTIAL,
        description="Edge type",
    )
    label: NotBlankStr | None = Field(
        default=None,
        description="Optional display label",
    )


class WorkflowDefinition(BaseModel):
    """A complete visual workflow definition.

    Contains the full graph (nodes + edges) plus metadata for
    persistence and concurrency control.

    Attributes:
        id: Server-generated unique identifier.
        name: Human-readable workflow name.
        description: Optional detailed description.
        workflow_type: The execution topology this workflow targets.
        nodes: All nodes in the workflow graph.
        edges: All edges connecting the nodes.
        created_by: Identity of the creator.
        created_at: Creation timestamp (UTC).
        updated_at: Last update timestamp (UTC).
        version: Optimistic concurrency version counter.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(description="Unique workflow definition ID")
    name: NotBlankStr = Field(description="Workflow name")
    description: str = Field(default="", description="Detailed description")
    workflow_type: WorkflowType = Field(
        default=WorkflowType.SEQUENTIAL_PIPELINE,
        description="Target execution topology",
    )
    nodes: tuple[WorkflowNode, ...] = Field(
        default=(),
        description="Nodes in the workflow graph",
    )
    edges: tuple[WorkflowEdge, ...] = Field(
        default=(),
        description="Edges connecting nodes",
    )
    created_by: NotBlankStr = Field(description="Creator identity")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp (UTC)",
    )
    version: int = Field(default=1, ge=1, description="Optimistic concurrency version")

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> Self:
        """Reject duplicate node or edge IDs."""
        node_ids = tuple(n.id for n in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            dupes = sorted(v for v, c in Counter(node_ids).items() if c > 1)
            msg = f"Duplicate node IDs: {dupes}"
            raise ValueError(msg)

        edge_ids = tuple(e.id for e in self.edges)
        if len(edge_ids) != len(set(edge_ids)):
            dupes = sorted(v for v, c in Counter(edge_ids).items() if c > 1)
            msg = f"Duplicate edge IDs: {dupes}"
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def _validate_edge_references(self) -> Self:
        """Ensure all edges reference existing nodes and no self-loops."""
        node_id_set = frozenset(n.id for n in self.nodes)
        for edge in self.edges:
            if edge.source_node_id == edge.target_node_id:
                msg = f"Self-referencing edge: {edge.id!r}"
                raise ValueError(msg)
            if edge.source_node_id not in node_id_set:
                msg = (
                    f"Edge {edge.id!r} references non-existent "
                    f"source node {edge.source_node_id!r}"
                )
                raise ValueError(msg)
            if edge.target_node_id not in node_id_set:
                msg = (
                    f"Edge {edge.id!r} references non-existent "
                    f"target node {edge.target_node_id!r}"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_terminal_nodes(self) -> Self:
        """Require exactly one START and one END node."""
        start_count = sum(1 for n in self.nodes if n.type == WorkflowNodeType.START)
        end_count = sum(1 for n in self.nodes if n.type == WorkflowNodeType.END)

        if start_count != 1:
            msg = f"Expected exactly 1 START node, found {start_count}"
            raise ValueError(msg)
        if end_count != 1:
            msg = f"Expected exactly 1 END node, found {end_count}"
            raise ValueError(msg)

        return self
