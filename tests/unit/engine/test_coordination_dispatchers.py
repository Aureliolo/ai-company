"""Tests for coordination dispatchers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from ai_company.core.enums import CoordinationTopology, TaskStructure
from ai_company.engine.coordination.config import CoordinationConfig
from ai_company.engine.coordination.dispatchers import (
    CentralizedDispatcher,
    ContextDependentDispatcher,
    DecentralizedDispatcher,
    DispatchResult,
    SasDispatcher,
    TopologyDispatcher,
    select_dispatcher,
)
from ai_company.engine.decomposition.models import (
    DecompositionPlan,
    DecompositionResult,
    SubtaskDefinition,
)
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
    structure: TaskStructure = TaskStructure.PARALLEL,
) -> DecompositionResult:
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


def _make_routing(
    subtask_agent_pairs: list[tuple[str, str]],
    *,
    parent_task_id: str = "parent-1",
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
                topology=CoordinationTopology.CENTRALIZED,
            )
        )
    return RoutingResult(
        parent_task_id=parent_task_id,
        decisions=tuple(decisions),
    )


def _make_exec_result(
    group_id: str,
    task_agent_pairs: list[tuple[str, str]],
    *,
    all_succeed: bool = True,
) -> ParallelExecutionResult:
    """Build a ParallelExecutionResult with given outcomes."""
    outcomes: list[AgentOutcome] = []
    for task_id, agent_id in task_agent_pairs:
        if all_succeed:
            run_result = _build_run_result(task_id, agent_id)
            outcomes.append(
                AgentOutcome(
                    task_id=task_id,
                    agent_id=agent_id,
                    result=run_result,
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


def _build_run_result(
    task_id: str,
    agent_id: str,
) -> AgentRunResult:
    """Build a minimal AgentRunResult for testing."""
    from ai_company.core.enums import TaskStatus
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


def _mock_executor(
    exec_results: list[ParallelExecutionResult] | None = None,
) -> AsyncMock:
    """Create a mock ParallelExecutor."""
    mock = AsyncMock()
    if exec_results:
        mock.execute_group.side_effect = exec_results
    return mock


def _mock_workspace_service(
    workspaces: tuple[Workspace, ...] = (),
    merge_result: WorkspaceGroupResult | None = None,
) -> AsyncMock:
    """Create a mock WorkspaceIsolationService."""
    mock = AsyncMock()
    mock.setup_group.return_value = workspaces
    mock.merge_group.return_value = merge_result or WorkspaceGroupResult(
        group_id="merge-1",
        merge_results=tuple(
            MergeResult(
                workspace_id=ws.workspace_id,
                branch_name=ws.branch_name,
                success=True,
                merged_commit_sha="abc123",
                duration_seconds=0.1,
            )
            for ws in workspaces
        ),
        duration_seconds=0.5,
    )
    mock.teardown_group.return_value = None
    return mock


# ── Tests ───────────────────────────────────────────────────────


class TestSelectDispatcher:
    """select_dispatcher factory tests."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("topology", "expected_type"),
        [
            (CoordinationTopology.SAS, SasDispatcher),
            (CoordinationTopology.CENTRALIZED, CentralizedDispatcher),
            (CoordinationTopology.DECENTRALIZED, DecentralizedDispatcher),
            (CoordinationTopology.CONTEXT_DEPENDENT, ContextDependentDispatcher),
        ],
    )
    def test_returns_correct_dispatcher(
        self,
        topology: CoordinationTopology,
        expected_type: type,
    ) -> None:
        """Factory returns correct dispatcher type."""
        dispatcher = select_dispatcher(topology)
        assert isinstance(dispatcher, expected_type)

    @pytest.mark.unit
    def test_auto_topology_raises(self) -> None:
        """AUTO topology raises ValueError."""
        with pytest.raises(ValueError, match="AUTO must be resolved"):
            select_dispatcher(CoordinationTopology.AUTO)

    @pytest.mark.unit
    def test_all_dispatchers_satisfy_protocol(self) -> None:
        """All dispatchers satisfy the TopologyDispatcher protocol."""
        for topo in (
            CoordinationTopology.SAS,
            CoordinationTopology.CENTRALIZED,
            CoordinationTopology.DECENTRALIZED,
            CoordinationTopology.CONTEXT_DEPENDENT,
        ):
            dispatcher = select_dispatcher(topo)
            assert isinstance(dispatcher, TopologyDispatcher)


class TestSasDispatcher:
    """SasDispatcher tests."""

    @pytest.mark.unit
    async def test_sequential_execution(self) -> None:
        """SAS executes subtasks as sequential waves."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b", dependencies=("sub-a",))
        decomp = _make_decomposition(
            (sub_a, sub_b),
            structure=TaskStructure.SEQUENTIAL,
        )
        routing = _make_routing(
            [
                ("sub-a", "alice"),
                ("sub-b", "alice"),
            ]
        )

        # One result per wave (2 sequential waves)
        agent_id_a = str(routing.decisions[0].selected_candidate.agent_identity.id)
        agent_id_b = str(routing.decisions[1].selected_candidate.agent_identity.id)
        executor = _mock_executor(
            [
                _make_exec_result("wave-0", [("sub-a", agent_id_a)]),
                _make_exec_result("wave-1", [("sub-b", agent_id_b)]),
            ]
        )

        dispatcher = SasDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=None,
            config=CoordinationConfig(),
        )

        assert len(result.waves) == 2
        assert result.workspaces == ()
        assert result.workspace_merge is None
        assert executor.execute_group.call_count == 2

    @pytest.mark.unit
    async def test_no_workspace_isolation(self) -> None:
        """SAS does not use workspace isolation."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])
        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        ws_service = _mock_workspace_service()
        executor = _mock_executor(
            [
                _make_exec_result("wave-0", [("sub-a", agent_id)]),
            ]
        )

        dispatcher = SasDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(),
        )

        # SAS never calls workspace service
        ws_service.setup_group.assert_not_called()
        assert result.workspaces == ()


class TestCentralizedDispatcher:
    """CentralizedDispatcher tests."""

    @pytest.mark.unit
    async def test_parallel_waves_with_isolation(self) -> None:
        """Centralized uses DAG waves and workspace isolation."""
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

        ws_service = _mock_workspace_service(
            workspaces=(ws_a, ws_b),
        )
        executor = _mock_executor(
            [
                _make_exec_result(
                    "wave-0",
                    [
                        ("sub-a", agent_id_a),
                        ("sub-b", agent_id_b),
                    ],
                ),
            ]
        )

        dispatcher = CentralizedDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(),
        )

        assert len(result.waves) == 1
        assert len(result.workspaces) == 2
        ws_service.setup_group.assert_called_once()
        ws_service.merge_group.assert_called_once()
        ws_service.teardown_group.assert_called_once()

    @pytest.mark.unit
    async def test_no_workspace_service(self) -> None:
        """Centralized works without workspace service."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])
        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        executor = _mock_executor(
            [
                _make_exec_result("wave-0", [("sub-a", agent_id)]),
            ]
        )

        dispatcher = CentralizedDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=None,
            config=CoordinationConfig(),
        )

        assert len(result.waves) == 1
        assert result.workspaces == ()

    @pytest.mark.unit
    async def test_workspace_isolation_disabled(self) -> None:
        """Centralized skips isolation when disabled in config."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])
        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        ws_service = _mock_workspace_service()
        executor = _mock_executor(
            [
                _make_exec_result("wave-0", [("sub-a", agent_id)]),
            ]
        )

        dispatcher = CentralizedDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(enable_workspace_isolation=False),
        )

        ws_service.setup_group.assert_not_called()
        assert result.workspaces == ()

    @pytest.mark.unit
    async def test_teardown_on_execution_error(self) -> None:
        """Workspaces are torn down even if execution raises."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])

        ws_a = Workspace(
            workspace_id="ws-a",
            task_id="sub-a",
            agent_id="alice",
            branch_name="workspace/sub-a",
            worktree_path="fake/ws-a",
            base_branch="main",
            created_at=datetime.now(UTC),
        )
        ws_service = _mock_workspace_service(workspaces=(ws_a,))

        executor = AsyncMock()
        executor.execute_group.side_effect = RuntimeError("boom")

        dispatcher = CentralizedDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(),
        )

        # Teardown still called
        ws_service.teardown_group.assert_called_once()
        # Wave phase captured the error
        exec_phases = [p for p in result.phases if p.phase.startswith("execute")]
        assert any(not p.success for p in exec_phases)


class TestDecentralizedDispatcher:
    """DecentralizedDispatcher tests."""

    @pytest.mark.unit
    async def test_no_workspace_service_raises(self) -> None:
        """DecentralizedDispatcher raises when workspace_service is None."""
        from ai_company.engine.errors import CoordinationError

        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])

        dispatcher = DecentralizedDispatcher()
        with pytest.raises(CoordinationError, match="workspace isolation"):
            await dispatcher.dispatch(
                decomposition_result=decomp,
                routing_result=routing,
                parallel_executor=_mock_executor(),
                workspace_service=None,
                config=CoordinationConfig(),
            )

    @pytest.mark.unit
    async def test_isolation_disabled_raises(self) -> None:
        """DecentralizedDispatcher raises when isolation is disabled."""
        from ai_company.engine.errors import CoordinationError

        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])

        dispatcher = DecentralizedDispatcher()
        with pytest.raises(CoordinationError, match="workspace isolation"):
            await dispatcher.dispatch(
                decomposition_result=decomp,
                routing_result=routing,
                parallel_executor=_mock_executor(),
                workspace_service=_mock_workspace_service(),
                config=CoordinationConfig(enable_workspace_isolation=False),
            )

    @pytest.mark.unit
    async def test_single_wave_all_parallel(self) -> None:
        """Decentralized puts everything in parallel waves per DAG."""
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
        ws_service = _mock_workspace_service(workspaces=(ws_a, ws_b))

        executor = _mock_executor(
            [
                _make_exec_result(
                    "wave-0",
                    [
                        ("sub-a", agent_id_a),
                        ("sub-b", agent_id_b),
                    ],
                ),
            ]
        )

        dispatcher = DecentralizedDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(),
        )

        assert len(result.waves) == 1
        assert len(result.workspaces) == 2
        ws_service.setup_group.assert_called_once()
        ws_service.merge_group.assert_called_once()
        ws_service.teardown_group.assert_called_once()


class TestContextDependentDispatcher:
    """ContextDependentDispatcher tests."""

    @pytest.mark.unit
    async def test_single_subtask_wave_no_isolation(self) -> None:
        """Single-subtask waves skip workspace isolation."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])
        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        ws_service = _mock_workspace_service()
        executor = _mock_executor(
            [
                _make_exec_result("wave-0", [("sub-a", agent_id)]),
            ]
        )

        dispatcher = ContextDependentDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(),
        )

        assert len(result.waves) == 1
        # No workspace setup for single-subtask wave
        ws_service.setup_group.assert_not_called()

    @pytest.mark.unit
    async def test_multi_subtask_wave_uses_isolation(self) -> None:
        """Multi-subtask waves use workspace isolation."""
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
        ws_service = _mock_workspace_service(workspaces=(ws_a, ws_b))

        executor = _mock_executor(
            [
                _make_exec_result(
                    "wave-0",
                    [
                        ("sub-a", agent_id_a),
                        ("sub-b", agent_id_b),
                    ],
                ),
            ]
        )

        dispatcher = ContextDependentDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(),
        )

        assert len(result.waves) == 1
        ws_service.setup_group.assert_called_once()
        # Per-wave merge
        ws_service.merge_group.assert_called_once()


class TestCentralizedWorkspaceFailure:
    """CentralizedDispatcher workspace setup failure tests."""

    @pytest.mark.unit
    async def test_workspace_setup_failure_returns_early(self) -> None:
        """CentralizedDispatcher returns early when workspace setup fails."""
        sub_a = _make_subtask("sub-a")
        decomp = _make_decomposition((sub_a,))
        routing = _make_routing([("sub-a", "alice")])

        ws_service = AsyncMock()
        ws_service.setup_group.side_effect = RuntimeError("setup failed")

        executor = _mock_executor()

        dispatcher = CentralizedDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(),
        )

        assert len(result.phases) == 1
        assert result.phases[0].phase == "workspace_setup"
        assert not result.phases[0].success
        executor.execute_group.assert_not_called()
        assert len(result.waves) == 0


class TestContextDependentFailFast:
    """ContextDependentDispatcher fail_fast behavior tests."""

    @pytest.mark.unit
    async def test_fail_fast_stops_on_wave_failure(self) -> None:
        """fail_fast=True stops after first failed wave."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b", dependencies=("sub-a",))
        decomp = _make_decomposition(
            (sub_a, sub_b),
            structure=TaskStructure.SEQUENTIAL,
        )
        routing = _make_routing([("sub-a", "alice"), ("sub-b", "alice")])
        agent_id = str(routing.decisions[0].selected_candidate.agent_identity.id)

        executor = _mock_executor(
            [
                _make_exec_result("wave-0", [("sub-a", agent_id)], all_succeed=False),
                _make_exec_result("wave-1", [("sub-b", agent_id)]),
            ]
        )

        dispatcher = ContextDependentDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=None,
            config=CoordinationConfig(fail_fast=True),
        )

        # Only first wave executed
        assert len(result.waves) == 1
        assert executor.execute_group.call_count == 1

    @pytest.mark.unit
    async def test_setup_failure_skips_wave(self) -> None:
        """CDD skips wave when workspace setup fails (fail_fast=False)."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        decomp = _make_decomposition((sub_a, sub_b))
        routing = _make_routing([("sub-a", "alice"), ("sub-b", "bob")])

        ws_service = AsyncMock()
        ws_service.setup_group.side_effect = RuntimeError("setup failed")

        executor = _mock_executor()

        dispatcher = ContextDependentDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(fail_fast=False),
        )

        # Setup failed, wave skipped, no execution
        setup_phases = [
            p for p in result.phases if p.phase.startswith("workspace_setup")
        ]
        assert len(setup_phases) == 1
        assert not setup_phases[0].success
        executor.execute_group.assert_not_called()
        assert len(result.waves) == 0

    @pytest.mark.unit
    async def test_fail_fast_stops_on_setup_failure(self) -> None:
        """fail_fast=True stops when workspace setup fails."""
        sub_a = _make_subtask("sub-a")
        sub_b = _make_subtask("sub-b")
        decomp = _make_decomposition((sub_a, sub_b))
        routing = _make_routing([("sub-a", "alice"), ("sub-b", "bob")])

        ws_service = AsyncMock()
        ws_service.setup_group.side_effect = RuntimeError("setup failed")

        executor = _mock_executor()

        dispatcher = ContextDependentDispatcher()
        result = await dispatcher.dispatch(
            decomposition_result=decomp,
            routing_result=routing,
            parallel_executor=executor,
            workspace_service=ws_service,
            config=CoordinationConfig(fail_fast=True),
        )

        # Setup failed, pipeline stopped
        setup_phases = [
            p for p in result.phases if p.phase.startswith("workspace_setup")
        ]
        assert len(setup_phases) == 1
        assert not setup_phases[0].success
        executor.execute_group.assert_not_called()


class TestDispatchResult:
    """DispatchResult model tests."""

    @pytest.mark.unit
    def test_empty_defaults(self) -> None:
        """DispatchResult defaults are empty."""
        result = DispatchResult()
        assert result.waves == ()
        assert result.workspaces == ()
        assert result.workspace_merge is None
        assert result.phases == ()
