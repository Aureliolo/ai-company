"""Tests for coordination group builder."""

import pytest

from ai_company.core.enums import CoordinationTopology, TaskStructure
from ai_company.engine.coordination.config import CoordinationConfig
from ai_company.engine.coordination.group_builder import build_execution_waves
from ai_company.engine.decomposition.models import (
    DecompositionPlan,
    DecompositionResult,
    SubtaskDefinition,
)
from ai_company.engine.routing.models import (
    RoutingCandidate,
    RoutingDecision,
    RoutingResult,
)
from tests.unit.engine.conftest import (
    make_assignment_agent,
    make_assignment_task,
    make_workspace,
)


def _make_subtask(
    subtask_id: str,
    *,
    dependencies: tuple[str, ...] = (),
) -> SubtaskDefinition:
    """Build a SubtaskDefinition with defaults."""
    return SubtaskDefinition(
        id=subtask_id,
        title=f"Subtask {subtask_id}",
        description=f"Description for {subtask_id}",
        dependencies=dependencies,
    )


def _make_decomposition(
    subtasks: tuple[SubtaskDefinition, ...],
    *,
    parent_task_id: str = "parent-1",
    structure: TaskStructure = TaskStructure.PARALLEL,
) -> DecompositionResult:
    """Build a DecompositionResult with created tasks from subtask defs."""
    plan = DecompositionPlan(
        parent_task_id=parent_task_id,
        subtasks=subtasks,
        task_structure=structure,
        coordination_topology=CoordinationTopology.CENTRALIZED,
    )
    created_tasks = tuple(
        make_assignment_task(
            id=s.id,
            title=s.title,
            description=s.description,
            parent_task_id=parent_task_id,
            dependencies=s.dependencies,
        )
        for s in subtasks
    )

    edges: list[tuple[str, str]] = []
    for s in subtasks:
        edges.extend((dep, s.id) for dep in s.dependencies)

    return DecompositionResult(
        plan=plan,
        created_tasks=created_tasks,
        dependency_edges=tuple(edges),
    )


def _make_routing_decision(
    subtask_id: str,
    agent_name: str,
) -> RoutingDecision:
    """Build a RoutingDecision for a subtask → agent mapping."""
    agent = make_assignment_agent(agent_name)
    return RoutingDecision(
        subtask_id=subtask_id,
        selected_candidate=RoutingCandidate(
            agent_identity=agent,
            score=0.9,
            reason="Good match",
        ),
        topology=CoordinationTopology.CENTRALIZED,
    )


class TestBuildExecutionWaves:
    """build_execution_waves tests."""

    @pytest.mark.unit
    def test_single_subtask_one_group(self) -> None:
        """Single subtask produces 1 group with 1 assignment."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(_make_routing_decision("sub-a", "alice"),),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
        )

        assert len(waves) == 1
        assert waves[0].group_id == "wave-0"
        assert len(waves[0].assignments) == 1
        assert waves[0].assignments[0].task.id == "sub-a"

    @pytest.mark.unit
    def test_two_independent_subtasks_one_wave(self) -> None:
        """Two independent subtasks produce 1 wave with 2 assignments."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        decomp = _make_decomposition((sub_a, sub_b))
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(
                _make_routing_decision("sub-a", "alice"),
                _make_routing_decision("sub-b", "bob"),
            ),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
        )

        assert len(waves) == 1
        assert len(waves[0].assignments) == 2

    @pytest.mark.unit
    def test_sequential_chain_two_waves(self) -> None:
        """A→B dependency chain produces 2 waves of 1 each."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b", dependencies=("sub-a",))
        decomp = _make_decomposition(
            (sub_a, sub_b),
            structure=TaskStructure.SEQUENTIAL,
        )
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(
                _make_routing_decision("sub-a", "alice"),
                _make_routing_decision("sub-b", "bob"),
            ),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
        )

        assert len(waves) == 2
        assert waves[0].assignments[0].task.id == "sub-a"
        assert waves[1].assignments[0].task.id == "sub-b"

    @pytest.mark.unit
    def test_diamond_dag(self) -> None:
        """Diamond A→C, B→C produces 2 waves: [A,B] then [C]."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        sub_c = _make_subtask("sub-c", dependencies=("sub-a", "sub-b"))
        decomp = _make_decomposition(
            (sub_a, sub_b, sub_c),
            structure=TaskStructure.MIXED,
        )
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(
                _make_routing_decision("sub-a", "alice"),
                _make_routing_decision("sub-b", "bob"),
                _make_routing_decision("sub-c", "charlie"),
            ),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
        )

        assert len(waves) == 2
        wave0_ids = {a.task.id for a in waves[0].assignments}
        assert wave0_ids == {"sub-a", "sub-b"}
        wave1_ids = {a.task.id for a in waves[1].assignments}
        assert wave1_ids == {"sub-c"}

    @pytest.mark.unit
    def test_max_concurrency_propagated(self) -> None:
        """max_concurrency_per_wave is propagated to groups."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(_make_routing_decision("sub-a", "alice"),),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(max_concurrency_per_wave=3),
        )

        assert waves[0].max_concurrency == 3

    @pytest.mark.unit
    def test_fail_fast_propagated(self) -> None:
        """fail_fast is propagated to groups."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(_make_routing_decision("sub-a", "alice"),),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(fail_fast=True),
        )

        assert waves[0].fail_fast is True

    @pytest.mark.unit
    def test_workspace_resource_claims_mapped(self) -> None:
        """Workspace worktree_path is mapped to resource_claims."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(_make_routing_decision("sub-a", "alice"),),
        )
        ws = make_workspace(
            workspace_id="ws-a",
            task_id="sub-a",
            agent_id="alice",
            worktree_path="fake/ws-a",
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
            workspaces=(ws,),
        )

        assert waves[0].assignments[0].resource_claims == ("fake/ws-a",)

    @pytest.mark.unit
    def test_unroutable_subtasks_skipped(self) -> None:
        """Unroutable subtasks are silently skipped."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        decomp = _make_decomposition((sub_a, sub_b))
        # Only route sub-a, sub-b is unroutable
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(_make_routing_decision("sub-a", "alice"),),
            unroutable=("sub-b",),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
        )

        assert len(waves) == 1
        assert len(waves[0].assignments) == 1
        assert waves[0].assignments[0].task.id == "sub-a"

    @pytest.mark.unit
    def test_all_unroutable_empty_waves(self) -> None:
        """All unroutable subtasks produce no waves."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = RoutingResult(
            parent_task_id="parent-1",
            unroutable=("sub-a",),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
        )

        assert len(waves) == 0

    @pytest.mark.unit
    def test_no_workspace_no_resource_claims(self) -> None:
        """Without workspaces, resource_claims is empty."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = RoutingResult(
            parent_task_id="parent-1",
            decisions=(_make_routing_decision("sub-a", "alice"),),
        )

        waves = build_execution_waves(
            decomposition_result=decomp,
            routing_result=routing,
            config=CoordinationConfig(),
        )

        assert waves[0].assignments[0].resource_claims == ()
