"""Tests for workflow definition version model."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.core.enums import WorkflowNodeType, WorkflowType
from synthorg.engine.workflow.definition import WorkflowEdge, WorkflowNode
from synthorg.engine.workflow.version import WorkflowDefinitionVersion


def _make_version(**overrides: object) -> WorkflowDefinitionVersion:
    """Build a minimal valid version snapshot."""
    defaults: dict[str, object] = {
        "definition_id": "wfdef-abc123",
        "version": 1,
        "name": "Test Workflow",
        "description": "A test workflow",
        "workflow_type": WorkflowType.SEQUENTIAL_PIPELINE,
        "nodes": (
            WorkflowNode(id="start", type=WorkflowNodeType.START, label="Start"),
            WorkflowNode(id="end", type=WorkflowNodeType.END, label="End"),
        ),
        "edges": (WorkflowEdge(id="e1", source_node_id="start", target_node_id="end"),),
        "created_by": "user-1",
        "saved_by": "user-1",
        "saved_at": datetime(2026, 4, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return WorkflowDefinitionVersion.model_validate(defaults)


class TestWorkflowDefinitionVersion:
    """Version model creation and constraints."""

    @pytest.mark.unit
    def test_valid_version(self) -> None:
        v = _make_version()
        assert v.definition_id == "wfdef-abc123"
        assert v.version == 1
        assert v.name == "Test Workflow"
        assert len(v.nodes) == 2
        assert len(v.edges) == 1

    @pytest.mark.unit
    def test_frozen(self) -> None:
        v = _make_version()
        with pytest.raises(ValidationError, match="frozen"):
            v.version = 2  # type: ignore[misc]

    @pytest.mark.unit
    def test_version_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            _make_version(version=0)

    @pytest.mark.unit
    def test_blank_definition_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_version(definition_id="")

    @pytest.mark.unit
    def test_blank_saved_by_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_version(saved_by="")

    @pytest.mark.unit
    def test_no_graph_validators(self) -> None:
        """Version snapshots don't enforce graph constraints.

        Unlike WorkflowDefinition, versions store historical state
        without re-validating graph structure.
        """
        # Two START nodes would fail WorkflowDefinition but not version.
        v = _make_version(
            nodes=(
                WorkflowNode(id="s1", type=WorkflowNodeType.START, label="Start 1"),
                WorkflowNode(id="s2", type=WorkflowNodeType.START, label="Start 2"),
            ),
            edges=(),
        )
        assert len(v.nodes) == 2
