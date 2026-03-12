"""Tests for MultiAgentCoordinator service."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_company.core.enums import (
    CoordinationTopology,
    TaskStatus,
    TaskStructure,
)
from ai_company.engine.coordination.config import CoordinationConfig
from ai_company.engine.coordination.models import (
    CoordinationContext,
)
from ai_company.engine.coordination.service import MultiAgentCoordinator
from ai_company.engine.decomposition.models import (
    DecompositionPlan,
    DecompositionResult,
    SubtaskDefinition,
)
from ai_company.engine.errors import CoordinationPhaseError
from ai_company.engine.parallel_models import (
    AgentOutcome,
    ParallelExecutionResult,
)
from ai_company.engine.routing.models import (
    RoutingCandidate,
    RoutingDecision,
    RoutingResult,
)
from ai_company.engine.run_result import AgentRunResult
from ai_company.engine.task_engine_models import TaskMutationResult
from ai_company.engine.workspace.models import (
    MergeResult,
    Workspace,
    WorkspaceGroupResult,
)
from tests.unit.engine.conftest import make_assignment_agent, make_assignment_task

# ── Helpers ─────────────────────────────────────────────────────


def _make_subtask(
    subtask_id: str,
    *,
    dependencies: tuple[str, ...] = (),
) -> SubtaskDefinition:
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
    topology: CoordinationTopology = CoordinationTopology.CENTRALIZED,
    structure: TaskStructure = TaskStructure.PARALLEL,
) -> DecompositionResult:
    plan = DecompositionPlan(
        parent_task_id=parent_task_id,
        subtasks=subtasks,
        task_structure=structure,
        coordination_topology=topology,
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


def _make_routing(
    subtask_agent_pairs: list[tuple[str, str]],
    *,
    parent_task_id: str = "parent-1",
    topology: CoordinationTopology = CoordinationTopology.CENTRALIZED,
    unroutable: tuple[str, ...] = (),
) -> RoutingResult:
    decisions: list[RoutingDecision] = []
    for subtask_id, agent_name in subtask_agent_pairs:
        agent = make_assignment_agent(agent_name)
        decisions.append(
            RoutingDecision(
                subtask_id=subtask_id,
                selected_candidate=RoutingCandidate(
                    agent_identity=agent,
                    score=0.9,
                    reason="Good match",
                ),
                topology=topology,
            )
        )
    return RoutingResult(
        parent_task_id=parent_task_id,
        decisions=tuple(decisions),
        unroutable=unroutable,
    )


def _build_run_result(task_id: str, agent_id: str) -> AgentRunResult:
    """Build a minimal AgentRunResult for testing."""
    from ai_company.engine.context import AgentContext
    from ai_company.engine.loop_protocol import ExecutionResult, TerminationReason
    from ai_company.engine.prompt import SystemPrompt

    identity = make_assignment_agent("test-agent")
    task = make_assignment_task(
        id=task_id,
        assigned_to=agent_id,
        status=TaskStatus.ASSIGNED,
    )
    ctx = AgentContext.from_identity(identity, task=task)
    execution_result = ExecutionResult(
        context=ctx,
        termination_reason=TerminationReason.COMPLETED,
    )
    return AgentRunResult(
        execution_result=execution_result,
        system_prompt=SystemPrompt(
            content="test",
            template_version="1.0",
            estimated_tokens=1,
            sections=("identity",),
            metadata={"agent_id": agent_id},
        ),
        duration_seconds=0.5,
        agent_id=agent_id,
        task_id=task_id,
    )


def _make_exec_result(
    group_id: str,
    task_agent_pairs: list[tuple[str, str]],
    *,
    all_succeed: bool = True,
) -> ParallelExecutionResult:
    outcomes: list[AgentOutcome] = []
    for task_id, agent_id in task_agent_pairs:
        if all_succeed:
            outcomes.append(
                AgentOutcome(
                    task_id=task_id,
                    agent_id=agent_id,
                    result=_build_run_result(task_id, agent_id),
                )
            )
        else:
            outcomes.append(
                AgentOutcome(
                    task_id=task_id,
                    agent_id=agent_id,
                    error="Test failure",
                )
            )
    return ParallelExecutionResult(
        group_id=group_id,
        outcomes=tuple(outcomes),
        total_duration_seconds=1.0,
    )


def _make_coordinator(  # noqa: PLR0913
    *,
    decomp_result: DecompositionResult | None = None,
    routing_result: RoutingResult | None = None,
    exec_results: list[ParallelExecutionResult] | None = None,
    workspace_service: AsyncMock | None = None,
    task_engine: AsyncMock | None = None,
    decompose_error: Exception | None = None,
    route_error: Exception | None = None,
) -> MultiAgentCoordinator:
    """Build a MultiAgentCoordinator with mocked dependencies."""
    decomp_service = AsyncMock()
    if decompose_error:
        decomp_service.decompose_task.side_effect = decompose_error
    elif decomp_result:
        decomp_service.decompose_task.return_value = decomp_result
    decomp_service.rollup_status = MagicMock()
    if decomp_result:
        from ai_company.engine.decomposition.rollup import StatusRollup

        decomp_service.rollup_status.side_effect = StatusRollup.compute

    routing_service = MagicMock()
    if route_error:
        routing_service.route.side_effect = route_error
    elif routing_result:
        routing_service.route.return_value = routing_result

    executor = AsyncMock()
    if exec_results:
        executor.execute_group.side_effect = exec_results

    return MultiAgentCoordinator(
        decomposition_service=decomp_service,
        routing_service=routing_service,
        parallel_executor=executor,
        workspace_service=workspace_service,
        task_engine=task_engine,
    )


# ── Tests ───────────────────────────────────────────────────────


class TestMultiAgentCoordinator:
    """MultiAgentCoordinator tests."""

    @pytest.mark.unit
    async def test_happy_path_two_parallel_subtasks(self) -> None:
        """Full pipeline with 2 parallel subtasks succeeds."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        decomp = _make_decomposition((sub_a, sub_b))
        routing = _make_routing(
            [
                ("sub-a", "alice"),
                ("sub-b", "bob"),
            ]
        )

        agent_id_a = str(routing.decisions[0].selected_candidate.agent_identity.id)
        agent_id_b = str(routing.decisions[1].selected_candidate.agent_identity.id)

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
            exec_results=[
                _make_exec_result(
                    "wave-0",
                    [
                        ("sub-a", agent_id_a),
                        ("sub-b", agent_id_b),
                    ],
                ),
            ],
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(
                make_assignment_agent("alice"),
                make_assignment_agent("bob"),
            ),
        )

        result = await coordinator.coordinate(ctx)

        assert result.is_success
        assert result.topology == CoordinationTopology.CENTRALIZED
        assert result.decomposition_result is not None
        assert result.routing_result is not None
        assert len(result.waves) == 1
        assert result.status_rollup is not None
        assert result.status_rollup.completed == 2
        assert result.total_duration_seconds > 0

    @pytest.mark.unit
    async def test_sas_topology_single_agent(self) -> None:
        """SAS topology with sequential subtasks."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b", dependencies=("sub-a",))
        decomp = _make_decomposition(
            (sub_a, sub_b),
            topology=CoordinationTopology.SAS,
            structure=TaskStructure.SEQUENTIAL,
        )
        routing = _make_routing(
            [("sub-a", "alice"), ("sub-b", "alice")],
            topology=CoordinationTopology.SAS,
        )

        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
            exec_results=[
                _make_exec_result("wave-0", [("sub-a", agent_id)]),
                _make_exec_result("wave-1", [("sub-b", agent_id)]),
            ],
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(make_assignment_agent("alice"),),
        )

        result = await coordinator.coordinate(ctx)

        assert result.is_success
        assert result.topology == CoordinationTopology.SAS
        assert len(result.waves) == 2

    @pytest.mark.unit
    async def test_decompose_failure_raises_phase_error(self) -> None:
        """Decompose failure raises CoordinationPhaseError."""
        coordinator = _make_coordinator(
            decompose_error=RuntimeError("LLM down"),
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(make_assignment_agent("alice"),),
        )

        with pytest.raises(CoordinationPhaseError) as exc_info:
            await coordinator.coordinate(ctx)

        assert exc_info.value.phase == "decompose"
        assert len(exc_info.value.partial_phases) > 0

    @pytest.mark.unit
    async def test_route_failure_raises_phase_error(self) -> None:
        """Route failure raises CoordinationPhaseError."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))

        coordinator = _make_coordinator(
            decomp_result=decomp,
            route_error=RuntimeError("Routing broken"),
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(make_assignment_agent("alice"),),
        )

        with pytest.raises(CoordinationPhaseError) as exc_info:
            await coordinator.coordinate(ctx)

        assert exc_info.value.phase == "route"
        # Should have decompose phase in partial_phases
        assert len(exc_info.value.partial_phases) >= 2

    @pytest.mark.unit
    async def test_all_unroutable_raises_phase_error(self) -> None:
        """All unroutable subtasks raises CoordinationPhaseError."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = RoutingResult(
            parent_task_id="parent-1",
            unroutable=("sub-a",),
        )

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(make_assignment_agent("alice"),),
        )

        with pytest.raises(CoordinationPhaseError) as exc_info:
            await coordinator.coordinate(ctx)

        assert exc_info.value.phase == "validate"

    @pytest.mark.unit
    async def test_partial_execution_fail_fast_off(self) -> None:
        """With fail_fast=False, failed waves don't stop execution."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b", dependencies=("sub-a",))
        decomp = _make_decomposition(
            (sub_a, sub_b),
            structure=TaskStructure.SEQUENTIAL,
        )
        routing = _make_routing(
            [
                ("sub-a", "alice"),
                ("sub-b", "bob"),
            ]
        )

        agent_id_a = str(routing.decisions[0].selected_candidate.agent_identity.id)
        agent_id_b = str(routing.decisions[1].selected_candidate.agent_identity.id)

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
            exec_results=[
                # Wave 0 fails
                _make_exec_result("wave-0", [("sub-a", agent_id_a)], all_succeed=False),
                # Wave 1 succeeds
                _make_exec_result("wave-1", [("sub-b", agent_id_b)], all_succeed=True),
            ],
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(
                make_assignment_agent("alice"),
                make_assignment_agent("bob"),
            ),
            config=CoordinationConfig(fail_fast=False),
        )

        result = await coordinator.coordinate(ctx)

        # Not fully successful (wave 0 failed)
        assert not result.is_success
        # Both waves still executed
        assert len(result.waves) == 2
        assert result.status_rollup is not None
        assert result.status_rollup.failed == 1
        assert result.status_rollup.completed == 1

    @pytest.mark.unit
    async def test_task_engine_parent_update(self) -> None:
        """Parent task is updated via TaskEngine when provided."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])
        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        task_engine = AsyncMock()
        task_engine.submit.return_value = TaskMutationResult(
            request_id="req-1",
            success=True,
            task=make_assignment_task(
                id="parent-1",
                status=TaskStatus.COMPLETED,
                assigned_to="coordinator",
            ),
            version=2,
        )

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
            exec_results=[
                _make_exec_result("wave-0", [("sub-a", agent_id)]),
            ],
            task_engine=task_engine,
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(make_assignment_agent("alice"),),
        )

        result = await coordinator.coordinate(ctx)

        assert result.is_success
        task_engine.submit.assert_called_once()

    @pytest.mark.unit
    async def test_no_task_engine_skips_update(self) -> None:
        """Without TaskEngine, parent update is skipped."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])
        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
            exec_results=[
                _make_exec_result("wave-0", [("sub-a", agent_id)]),
            ],
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(make_assignment_agent("alice"),),
        )

        result = await coordinator.coordinate(ctx)

        assert result.is_success
        # No update_parent phase in results
        update_phases = [p for p in result.phases if p.phase == "update_parent"]
        assert len(update_phases) == 0

    @pytest.mark.unit
    async def test_status_rollup_correctness(self) -> None:
        """Status rollup accurately reflects execution outcomes."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        decomp = _make_decomposition((sub_a, sub_b))
        routing = _make_routing(
            [
                ("sub-a", "alice"),
                ("sub-b", "bob"),
            ]
        )

        agent_id_a = str(routing.decisions[0].selected_candidate.agent_identity.id)
        agent_id_b = str(routing.decisions[1].selected_candidate.agent_identity.id)

        # sub-a succeeds, sub-b fails
        outcomes = (
            AgentOutcome(
                task_id="sub-a",
                agent_id=agent_id_a,
                result=_build_run_result("sub-a", agent_id_a),
            ),
            AgentOutcome(
                task_id="sub-b",
                agent_id=agent_id_b,
                error="Test failure",
            ),
        )
        exec_result = ParallelExecutionResult(
            group_id="wave-0",
            outcomes=outcomes,
            total_duration_seconds=1.0,
        )

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
            exec_results=[exec_result],
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(
                make_assignment_agent("alice"),
                make_assignment_agent("bob"),
            ),
        )

        result = await coordinator.coordinate(ctx)

        assert result.status_rollup is not None
        assert result.status_rollup.completed == 1
        assert result.status_rollup.failed == 1
        assert result.status_rollup.total == 2
        assert result.status_rollup.derived_parent_status == TaskStatus.FAILED

    @pytest.mark.unit
    async def test_workspace_lifecycle(self) -> None:
        """Workspace setup → execute → merge → teardown lifecycle."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        decomp = _make_decomposition((sub_a, sub_b))
        routing = _make_routing(
            [
                ("sub-a", "alice"),
                ("sub-b", "bob"),
            ]
        )

        agent_id_a = str(routing.decisions[0].selected_candidate.agent_identity.id)
        agent_id_b = str(routing.decisions[1].selected_candidate.agent_identity.id)

        ws_a = Workspace(
            workspace_id="ws-a",
            task_id="sub-a",
            agent_id=agent_id_a,
            branch_name="workspace/sub-a",
            worktree_path="fake/ws-a",
            base_branch="main",
            created_at=datetime.now(UTC),
        )
        ws_b = Workspace(
            workspace_id="ws-b",
            task_id="sub-b",
            agent_id=agent_id_b,
            branch_name="workspace/sub-b",
            worktree_path="fake/ws-b",
            base_branch="main",
            created_at=datetime.now(UTC),
        )

        ws_service = AsyncMock()
        ws_service.setup_group.return_value = (ws_a, ws_b)
        ws_service.merge_group.return_value = WorkspaceGroupResult(
            group_id="merge-1",
            merge_results=(
                MergeResult(
                    workspace_id="ws-a",
                    branch_name="workspace/sub-a",
                    success=True,
                    merged_commit_sha="abc123",
                    duration_seconds=0.1,
                ),
                MergeResult(
                    workspace_id="ws-b",
                    branch_name="workspace/sub-b",
                    success=True,
                    merged_commit_sha="def456",
                    duration_seconds=0.1,
                ),
            ),
            duration_seconds=0.5,
        )
        ws_service.teardown_group.return_value = None

        coordinator = _make_coordinator(
            decomp_result=decomp,
            routing_result=routing,
            exec_results=[
                _make_exec_result(
                    "wave-0",
                    [
                        ("sub-a", agent_id_a),
                        ("sub-b", agent_id_b),
                    ],
                ),
            ],
            workspace_service=ws_service,
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(
                make_assignment_agent("alice"),
                make_assignment_agent("bob"),
            ),
        )

        result = await coordinator.coordinate(ctx)

        assert result.is_success
        ws_service.setup_group.assert_called_once()
        ws_service.merge_group.assert_called_once()
        ws_service.teardown_group.assert_called_once()
        assert result.workspace_merge is not None
        assert result.workspace_merge.all_merged

    @pytest.mark.unit
    async def test_memory_error_propagated(self) -> None:
        """MemoryError from decomposition is not swallowed."""
        coordinator = _make_coordinator(
            decompose_error=MemoryError("out of memory"),
        )

        ctx = CoordinationContext(
            task=make_assignment_task(id="parent-1"),
            available_agents=(make_assignment_agent("alice"),),
        )

        with pytest.raises(CoordinationPhaseError):
            await coordinator.coordinate(ctx)
