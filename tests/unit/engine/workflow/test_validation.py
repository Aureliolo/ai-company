"""Tests for workflow definition validation."""

import pytest

from synthorg.core.enums import WorkflowEdgeType, WorkflowNodeType
from synthorg.engine.workflow.validation import (
    ValidationErrorCode,
    validate_workflow,
)
from tests.unit.engine.workflow.conftest import (
    make_edge as _edge,
)
from tests.unit.engine.workflow.conftest import (
    make_node as _node,
)
from tests.unit.engine.workflow.conftest import (
    make_workflow as _wf,
)

# ── Valid workflows ─────────────────────────────────────────────


class TestValidWorkflows:
    """Workflows that should pass validation."""

    @pytest.mark.unit
    def test_minimal_sequential(self) -> None:
        """start -> task -> end."""
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("t", WorkflowNodeType.TASK, title="Do it"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "t"),
                    _edge("e2", "t", "e"),
                ),
            ),
        )
        assert result.valid
        assert len(result.errors) == 0

    @pytest.mark.unit
    def test_parallel_workflow(self) -> None:
        """start -> split -> [a, b] -> join -> end."""
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("split", WorkflowNodeType.PARALLEL_SPLIT),
                    _node("a", WorkflowNodeType.TASK, title="A"),
                    _node("b", WorkflowNodeType.TASK, title="B"),
                    _node("join", WorkflowNodeType.PARALLEL_JOIN),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "split"),
                    _edge("e2", "split", "a", WorkflowEdgeType.PARALLEL_BRANCH),
                    _edge("e3", "split", "b", WorkflowEdgeType.PARALLEL_BRANCH),
                    _edge("e4", "a", "join"),
                    _edge("e5", "b", "join"),
                    _edge("e6", "join", "e"),
                ),
            ),
        )
        assert result.valid

    @pytest.mark.unit
    def test_conditional_workflow(self) -> None:
        """start -> cond -> [true: a, false: b] -> end."""
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node(
                        "c", WorkflowNodeType.CONDITIONAL, condition_expression="x > 0"
                    ),
                    _node("a", WorkflowNodeType.TASK, title="Yes"),
                    _node("b", WorkflowNodeType.TASK, title="No"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "c"),
                    _edge("e2", "c", "a", WorkflowEdgeType.CONDITIONAL_TRUE),
                    _edge("e3", "c", "b", WorkflowEdgeType.CONDITIONAL_FALSE),
                    _edge("e4", "a", "e"),
                    _edge("e5", "b", "e"),
                ),
            ),
        )
        assert result.valid


# ── Unreachable nodes ───────────────────────────────────────────


class TestUnreachableNodes:
    """Nodes not reachable from START."""

    @pytest.mark.unit
    def test_disconnected_node(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("t", WorkflowNodeType.TASK, title="Work"),
                    _node("orphan", WorkflowNodeType.TASK, title="Orphan"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "t"),
                    _edge("e2", "t", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.UNREACHABLE_NODE in codes
        orphan_err = next(
            err
            for err in result.errors
            if err.code == ValidationErrorCode.UNREACHABLE_NODE
        )
        assert orphan_err.node_id == "orphan"


# ── END not reachable ───────────────────────────────────────────


class TestEndNotReachable:
    """END node not reachable from START."""

    @pytest.mark.unit
    def test_dead_end_path(self) -> None:
        """start -> task, end is disconnected."""
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("t", WorkflowNodeType.TASK, title="Work"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "t"),
                    # No edge to end
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.END_NOT_REACHABLE in codes


# ── Conditional edge constraints ────────────────────────────────


class TestConditionalConstraints:
    """Conditional node edge type requirements."""

    @pytest.mark.unit
    def test_missing_true_branch(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("c", WorkflowNodeType.CONDITIONAL),
                    _node("b", WorkflowNodeType.TASK, title="False"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "c"),
                    _edge("e2", "c", "b", WorkflowEdgeType.CONDITIONAL_FALSE),
                    _edge("e3", "b", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.CONDITIONAL_MISSING_TRUE in codes

    @pytest.mark.unit
    def test_missing_false_branch(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("c", WorkflowNodeType.CONDITIONAL),
                    _node("a", WorkflowNodeType.TASK, title="True"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "c"),
                    _edge("e2", "c", "a", WorkflowEdgeType.CONDITIONAL_TRUE),
                    _edge("e3", "a", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.CONDITIONAL_MISSING_FALSE in codes

    @pytest.mark.unit
    def test_extra_non_conditional_outgoing(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("c", WorkflowNodeType.CONDITIONAL),
                    _node("a", WorkflowNodeType.TASK, title="True"),
                    _node("b", WorkflowNodeType.TASK, title="False"),
                    _node("x", WorkflowNodeType.TASK, title="Extra"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "c"),
                    _edge("e2", "c", "a", WorkflowEdgeType.CONDITIONAL_TRUE),
                    _edge("e3", "c", "b", WorkflowEdgeType.CONDITIONAL_FALSE),
                    _edge("e4", "c", "x", WorkflowEdgeType.SEQUENTIAL),
                    _edge("e5", "a", "e"),
                    _edge("e6", "b", "e"),
                    _edge("e7", "x", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.CONDITIONAL_EXTRA_OUTGOING in codes


# ── Parallel split constraints ──────────────────────────────────


class TestParallelSplitConstraints:
    """Parallel split node branch requirements."""

    @pytest.mark.unit
    def test_single_branch_rejected(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("split", WorkflowNodeType.PARALLEL_SPLIT),
                    _node("a", WorkflowNodeType.TASK, title="A"),
                    _node("join", WorkflowNodeType.PARALLEL_JOIN),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "split"),
                    _edge("e2", "split", "a", WorkflowEdgeType.PARALLEL_BRANCH),
                    _edge("e3", "a", "join"),
                    _edge("e4", "join", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.SPLIT_TOO_FEW_BRANCHES in codes

    @pytest.mark.unit
    def test_zero_branches_rejected(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("split", WorkflowNodeType.PARALLEL_SPLIT),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "split"),
                    _edge("e2", "split", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.SPLIT_TOO_FEW_BRANCHES in codes


# ── Task config completeness ───────────────────────────────────


class TestTaskConfig:
    """Task node config requirements."""

    @pytest.mark.unit
    def test_missing_title(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("t", WorkflowNodeType.TASK),  # No title in config
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "t"),
                    _edge("e2", "t", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.TASK_MISSING_TITLE in codes

    @pytest.mark.unit
    def test_blank_title(self) -> None:
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("t", WorkflowNodeType.TASK, title="  "),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "t"),
                    _edge("e2", "t", "e"),
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.TASK_MISSING_TITLE in codes


# ── Cycle detection ─────────────────────────────────────────────


class TestCycleDetection:
    """Graph cycle detection."""

    @pytest.mark.unit
    def test_simple_cycle(self) -> None:
        """start -> a -> b -> a (cycle) and end unreachable."""
        result = validate_workflow(
            _wf(
                nodes=(
                    _node("s", WorkflowNodeType.START),
                    _node("a", WorkflowNodeType.TASK, title="A"),
                    _node("b", WorkflowNodeType.TASK, title="B"),
                    _node("e", WorkflowNodeType.END),
                ),
                edges=(
                    _edge("e1", "s", "a"),
                    _edge("e2", "a", "b"),
                    _edge("e3", "b", "a"),  # cycle
                ),
            ),
        )
        assert not result.valid
        codes = {err.code for err in result.errors}
        assert ValidationErrorCode.CYCLE_DETECTED in codes
