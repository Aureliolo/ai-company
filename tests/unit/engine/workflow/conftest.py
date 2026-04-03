"""Shared fixtures and helpers for workflow tests."""

import pytest

from synthorg.core.enums import WorkflowEdgeType, WorkflowNodeType
from synthorg.engine.workflow.definition import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from synthorg.engine.workflow.kanban_board import KanbanConfig, KanbanWipLimit
from synthorg.engine.workflow.kanban_columns import KanbanColumn

# ── Workflow graph helpers ────────────────────────────────────────


def make_node(
    node_id: str,
    node_type: WorkflowNodeType,
    label: str = "Node",
    **config: object,
) -> WorkflowNode:
    """Build a workflow node with optional config kwargs."""
    return WorkflowNode(id=node_id, type=node_type, label=label, config=config)


def make_start_node(node_id: str = "start-1") -> WorkflowNode:
    """Build a START node."""
    return WorkflowNode(id=node_id, type=WorkflowNodeType.START, label="Start")


def make_end_node(node_id: str = "end-1") -> WorkflowNode:
    """Build an END node."""
    return WorkflowNode(id=node_id, type=WorkflowNodeType.END, label="End")


def make_task_node(
    node_id: str = "task-1",
    label: str = "Do work",
) -> WorkflowNode:
    """Build a TASK node with default position and config."""
    return WorkflowNode(
        id=node_id,
        type=WorkflowNodeType.TASK,
        label=label,
        position_x=100.0,
        position_y=200.0,
        config={"task_type": "development", "priority": "high"},
    )


def make_edge(
    edge_id: str,
    source: str,
    target: str,
    edge_type: WorkflowEdgeType = WorkflowEdgeType.SEQUENTIAL,
) -> WorkflowEdge:
    """Build a workflow edge."""
    return WorkflowEdge(
        id=edge_id,
        source_node_id=source,
        target_node_id=target,
        type=edge_type,
    )


def make_workflow(
    nodes: tuple[WorkflowNode, ...],
    edges: tuple[WorkflowEdge, ...],
    **kwargs: object,
) -> WorkflowDefinition:
    """Build a WorkflowDefinition with sensible defaults.

    Any keyword argument overrides the defaults (id, name, created_by).
    """
    defaults: dict[str, object] = {
        "id": "wf-test",
        "name": "Test Workflow",
        "created_by": "test",
    }
    defaults.update(kwargs)
    return WorkflowDefinition.model_validate(
        {"nodes": nodes, "edges": edges, **defaults},
    )


def make_minimal_definition(**overrides: object) -> WorkflowDefinition:
    """Build a minimal valid definition (start -> task -> end)."""
    defaults: dict[str, object] = {
        "id": "wf-1",
        "name": "Test Workflow",
        "created_by": "test-user",
        "nodes": (make_start_node(), make_task_node(), make_end_node()),
        "edges": (
            make_edge("e1", "start-1", "task-1"),
            make_edge("e2", "task-1", "end-1"),
        ),
    }
    defaults.update(overrides)
    return WorkflowDefinition.model_validate(defaults)


# ── Kanban fixtures ──────────────────────────────────────────────


@pytest.fixture
def strict_kanban_config() -> KanbanConfig:
    """KanbanConfig with tight WIP limits for testing."""
    return KanbanConfig(
        wip_limits=(
            KanbanWipLimit(column=KanbanColumn.IN_PROGRESS, limit=2),
            KanbanWipLimit(column=KanbanColumn.REVIEW, limit=1),
        ),
        enforce_wip=True,
    )


@pytest.fixture
def advisory_kanban_config() -> KanbanConfig:
    """KanbanConfig with advisory (non-enforcing) WIP limits."""
    return KanbanConfig(
        wip_limits=(
            KanbanWipLimit(column=KanbanColumn.IN_PROGRESS, limit=2),
            KanbanWipLimit(column=KanbanColumn.REVIEW, limit=1),
        ),
        enforce_wip=False,
    )
