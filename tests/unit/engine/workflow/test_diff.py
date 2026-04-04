"""Tests for workflow definition diff computation."""

from datetime import UTC, datetime

import pytest

from synthorg.core.enums import (
    WorkflowEdgeType,
    WorkflowNodeType,
    WorkflowType,
)
from synthorg.engine.workflow.definition import WorkflowEdge, WorkflowNode
from synthorg.engine.workflow.diff import (
    POSITION_CHANGE_THRESHOLD,
    compute_diff,
)
from synthorg.engine.workflow.version import WorkflowDefinitionVersion

# ── Helpers ──────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 1, tzinfo=UTC)

_START = WorkflowNode(id="start", type=WorkflowNodeType.START, label="Start")
_END = WorkflowNode(id="end", type=WorkflowNodeType.END, label="End", position_x=200.0)
_TASK_A = WorkflowNode(
    id="task-a",
    type=WorkflowNodeType.TASK,
    label="Task A",
    position_x=100.0,
    position_y=100.0,
    config={"title": "Do A", "priority": "high"},
)
_EDGE_1 = WorkflowEdge(id="e1", source_node_id="start", target_node_id="end")


def _ver(version: int = 1, **overrides: object) -> WorkflowDefinitionVersion:
    defaults: dict[str, object] = {
        "definition_id": "wfdef-test",
        "version": version,
        "name": "Test",
        "description": "",
        "workflow_type": WorkflowType.SEQUENTIAL_PIPELINE,
        "nodes": (_START, _END),
        "edges": (_EDGE_1,),
        "created_by": "user",
        "saved_by": "user",
        "saved_at": _NOW,
    }
    defaults.update(overrides)
    return WorkflowDefinitionVersion.model_validate(defaults)


# ── Identical versions ──────────────────────────────────────────


class TestIdenticalVersions:
    """Diffing identical content across versions produces empty diff."""

    @pytest.mark.unit
    def test_empty_diff(self) -> None:
        v1 = _ver(1)
        v2 = _ver(2)
        diff = compute_diff(v1, v2)
        assert diff.node_changes == ()
        assert diff.edge_changes == ()
        assert diff.metadata_changes == ()
        assert diff.summary == "No changes"


# ── Node changes ─────────────────────────────────────────────────


class TestNodeChanges:
    """Node-level diff detection."""

    @pytest.mark.unit
    def test_added_node(self) -> None:
        old = _ver(1)
        new = _ver(2, nodes=(_START, _END, _TASK_A))
        diff = compute_diff(old, new)

        added = [c for c in diff.node_changes if c.change_type == "added"]
        assert len(added) == 1
        assert added[0].node_id == "task-a"
        assert added[0].new_value is not None

    @pytest.mark.unit
    def test_removed_node(self) -> None:
        old = _ver(1, nodes=(_START, _END, _TASK_A))
        new = _ver(2, nodes=(_START, _END))
        diff = compute_diff(old, new)

        removed = [c for c in diff.node_changes if c.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].node_id == "task-a"
        assert removed[0].old_value is not None

    @pytest.mark.unit
    def test_moved_node(self) -> None:
        moved_task = WorkflowNode(
            id="task-a",
            type=WorkflowNodeType.TASK,
            label="Task A",
            position_x=200.0,
            position_y=300.0,
            config={"title": "Do A", "priority": "high"},
        )
        old = _ver(1, nodes=(_START, _END, _TASK_A))
        new = _ver(2, nodes=(_START, _END, moved_task))
        diff = compute_diff(old, new)

        moved = [c for c in diff.node_changes if c.change_type == "moved"]
        assert len(moved) == 1
        assert moved[0].node_id == "task-a"

    @pytest.mark.unit
    def test_move_below_threshold_ignored(self) -> None:
        tiny_move = WorkflowNode(
            id="task-a",
            type=WorkflowNodeType.TASK,
            label="Task A",
            position_x=100.0 + POSITION_CHANGE_THRESHOLD * 0.5,
            position_y=100.0 + POSITION_CHANGE_THRESHOLD * 0.5,
            config={"title": "Do A", "priority": "high"},
        )
        old = _ver(1, nodes=(_START, _END, _TASK_A))
        new = _ver(2, nodes=(_START, _END, tiny_move))
        diff = compute_diff(old, new)

        moved = [c for c in diff.node_changes if c.change_type == "moved"]
        assert len(moved) == 0

    @pytest.mark.unit
    def test_config_changed(self) -> None:
        changed = WorkflowNode(
            id="task-a",
            type=WorkflowNodeType.TASK,
            label="Task A",
            position_x=100.0,
            position_y=100.0,
            config={"title": "Do A (updated)", "priority": "low"},
        )
        old = _ver(1, nodes=(_START, _END, _TASK_A))
        new = _ver(2, nodes=(_START, _END, changed))
        diff = compute_diff(old, new)

        cfg = [c for c in diff.node_changes if c.change_type == "config_changed"]
        assert len(cfg) == 1
        assert cfg[0].node_id == "task-a"

    @pytest.mark.unit
    def test_label_changed(self) -> None:
        relabeled = WorkflowNode(
            id="task-a",
            type=WorkflowNodeType.TASK,
            label="Renamed Task",
            position_x=100.0,
            position_y=100.0,
            config={"title": "Do A", "priority": "high"},
        )
        old = _ver(1, nodes=(_START, _END, _TASK_A))
        new = _ver(2, nodes=(_START, _END, relabeled))
        diff = compute_diff(old, new)

        labels = [c for c in diff.node_changes if c.change_type == "label_changed"]
        assert len(labels) == 1

    @pytest.mark.unit
    def test_type_changed(self) -> None:
        retyped = WorkflowNode(
            id="task-a",
            type=WorkflowNodeType.CONDITIONAL,
            label="Task A",
            position_x=100.0,
            position_y=100.0,
            config={"title": "Do A", "priority": "high"},
        )
        old = _ver(1, nodes=(_START, _END, _TASK_A))
        new = _ver(2, nodes=(_START, _END, retyped))
        diff = compute_diff(old, new)

        types = [c for c in diff.node_changes if c.change_type == "type_changed"]
        assert len(types) == 1


# ── Edge changes ─────────────────────────────────────────────────


class TestEdgeChanges:
    """Edge-level diff detection."""

    @pytest.mark.unit
    def test_added_edge(self) -> None:
        new_edge = WorkflowEdge(id="e2", source_node_id="start", target_node_id="end")
        old = _ver(1)
        new = _ver(2, edges=(_EDGE_1, new_edge))
        diff = compute_diff(old, new)

        added = [c for c in diff.edge_changes if c.change_type == "added"]
        assert len(added) == 1
        assert added[0].edge_id == "e2"

    @pytest.mark.unit
    def test_removed_edge(self) -> None:
        old = _ver(1)
        new = _ver(2, edges=())
        diff = compute_diff(old, new)

        removed = [c for c in diff.edge_changes if c.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].edge_id == "e1"

    @pytest.mark.unit
    def test_reconnected_edge(self) -> None:
        reconnected = WorkflowEdge(
            id="e1", source_node_id="end", target_node_id="start"
        )
        nodes = (_START, _END)
        old = _ver(1, nodes=nodes)
        new = _ver(2, nodes=nodes, edges=(reconnected,))
        diff = compute_diff(old, new)

        recon = [c for c in diff.edge_changes if c.change_type == "reconnected"]
        assert len(recon) == 1

    @pytest.mark.unit
    def test_edge_label_changed(self) -> None:
        """Detect edge label changes."""
        old_edge = WorkflowEdge(
            id="e1",
            source_node_id="start",
            target_node_id="end",
            label="Old Label",
        )
        new_edge = WorkflowEdge(
            id="e1",
            source_node_id="start",
            target_node_id="end",
            label="New Label",
        )
        old = _ver(1, edges=(old_edge,))
        new = _ver(2, edges=(new_edge,))
        diff = compute_diff(old, new)

        label_changes = [
            c for c in diff.edge_changes if c.change_type == "label_changed"
        ]
        assert len(label_changes) == 1
        assert label_changes[0].old_value == {"label": "Old Label"}
        assert label_changes[0].new_value == {"label": "New Label"}

    @pytest.mark.unit
    def test_edge_type_changed(self) -> None:
        retyped = WorkflowEdge(
            id="e1",
            source_node_id="start",
            target_node_id="end",
            type=WorkflowEdgeType.CONDITIONAL_TRUE,
        )
        old = _ver(1)
        new = _ver(2, edges=(retyped,))
        diff = compute_diff(old, new)

        types = [c for c in diff.edge_changes if c.change_type == "type_changed"]
        assert len(types) == 1


# ── Metadata changes ─────────────────────────────────────────────


class TestMetadataChanges:
    """Metadata-level diff detection."""

    @pytest.mark.unit
    def test_name_changed(self) -> None:
        old = _ver(1, name="Old Name")
        new = _ver(2, name="New Name")
        diff = compute_diff(old, new)

        meta = [m for m in diff.metadata_changes if m.field == "name"]
        assert len(meta) == 1
        assert meta[0].old_value == "Old Name"
        assert meta[0].new_value == "New Name"

    @pytest.mark.unit
    def test_description_changed(self) -> None:
        old = _ver(1, description="Old desc")
        new = _ver(2, description="New desc")
        diff = compute_diff(old, new)

        meta = [m for m in diff.metadata_changes if m.field == "description"]
        assert len(meta) == 1

    @pytest.mark.unit
    def test_workflow_type_changed(self) -> None:
        old = _ver(1, workflow_type=WorkflowType.SEQUENTIAL_PIPELINE)
        new = _ver(2, workflow_type=WorkflowType.PARALLEL_EXECUTION)
        diff = compute_diff(old, new)

        meta = [m for m in diff.metadata_changes if m.field == "workflow_type"]
        assert len(meta) == 1


# ── Summary ──────────────────────────────────────────────────────


class TestSummary:
    """Human-readable summary generation."""

    @pytest.mark.unit
    def test_combined_summary(self) -> None:
        old = _ver(1, nodes=(_START, _END, _TASK_A), name="Old")
        new = _ver(2, nodes=(_START, _END), name="New")
        diff = compute_diff(old, new)

        assert "1 removed node" in diff.summary
        assert "metadata changed: name" in diff.summary

    @pytest.mark.unit
    def test_no_changes_summary(self) -> None:
        v1 = _ver(1)
        v2 = _ver(2)
        diff = compute_diff(v1, v2)
        assert diff.summary == "No changes"
