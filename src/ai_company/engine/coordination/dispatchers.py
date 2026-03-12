"""Topology-driven dispatch strategies.

Each dispatcher implementation maps a ``CoordinationTopology`` to a
specific execution pattern: wave construction, workspace lifecycle,
and merge orchestration.
"""

import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ai_company.core.enums import CoordinationTopology
from ai_company.core.types import NotBlankStr
from ai_company.engine.coordination.group_builder import build_execution_waves
from ai_company.engine.coordination.models import (
    CoordinationPhaseResult,
    CoordinationWave,
)
from ai_company.engine.parallel_models import (
    AgentAssignment,
    ParallelExecutionGroup,
)
from ai_company.engine.workspace.models import (
    Workspace,
    WorkspaceGroupResult,
    WorkspaceRequest,
)
from ai_company.observability import get_logger
from ai_company.observability.events.coordination import (
    COORDINATION_CLEANUP_COMPLETED,
    COORDINATION_CLEANUP_STARTED,
    COORDINATION_PHASE_COMPLETED,
    COORDINATION_PHASE_FAILED,
    COORDINATION_PHASE_STARTED,
    COORDINATION_TOPOLOGY_RESOLVED,
    COORDINATION_WAVE_COMPLETED,
    COORDINATION_WAVE_STARTED,
)

if TYPE_CHECKING:
    from ai_company.engine.coordination.config import CoordinationConfig
    from ai_company.engine.decomposition.models import DecompositionResult
    from ai_company.engine.parallel import ParallelExecutor
    from ai_company.engine.routing.models import RoutingResult
    from ai_company.engine.workspace.service import WorkspaceIsolationService

logger = get_logger(__name__)


class DispatchResult(BaseModel):
    """Result of a topology dispatcher's execution.

    Attributes:
        waves: Executed waves with their results.
        workspaces: Workspaces created during execution.
        workspace_merge: Merge result if workspaces were merged.
        phases: Phase results generated during dispatch.
    """

    model_config = ConfigDict(frozen=True)

    waves: tuple[CoordinationWave, ...] = Field(
        default=(),
        description="Executed waves",
    )
    workspaces: tuple[Workspace, ...] = Field(
        default=(),
        description="Workspaces created during execution",
    )
    workspace_merge: WorkspaceGroupResult | None = Field(
        default=None,
        description="Workspace merge result",
    )
    phases: tuple[CoordinationPhaseResult, ...] = Field(
        default=(),
        description="Phase results from dispatch",
    )


@runtime_checkable
class TopologyDispatcher(Protocol):
    """Protocol for topology-specific dispatch strategies."""

    async def dispatch(
        self,
        *,
        decomposition_result: DecompositionResult,
        routing_result: RoutingResult,
        parallel_executor: ParallelExecutor,
        workspace_service: WorkspaceIsolationService | None,
        config: CoordinationConfig,
    ) -> DispatchResult:
        """Execute subtasks according to topology-specific rules.

        Args:
            decomposition_result: Decomposition with subtasks.
            routing_result: Routing decisions for subtasks.
            parallel_executor: Executor for parallel agent runs.
            workspace_service: Optional workspace isolation service.
            config: Coordination configuration.

        Returns:
            Dispatch result with waves, workspaces, and phases.
        """
        ...


def _build_workspace_requests(
    routing_result: RoutingResult,
    config: CoordinationConfig,
) -> tuple[WorkspaceRequest, ...]:
    """Build workspace requests from routing decisions."""
    return tuple(
        WorkspaceRequest(
            task_id=d.subtask_id,
            agent_id=str(d.selected_candidate.agent_identity.id),
            base_branch=config.base_branch,
        )
        for d in routing_result.decisions
    )


async def _setup_workspaces(
    workspace_service: WorkspaceIsolationService,
    routing_result: RoutingResult,
    config: CoordinationConfig,
) -> tuple[tuple[Workspace, ...], CoordinationPhaseResult]:
    """Set up workspaces and return them with a phase result."""
    start = time.monotonic()
    phase_name = "workspace_setup"

    logger.info(COORDINATION_PHASE_STARTED, phase=phase_name)
    try:
        requests = _build_workspace_requests(routing_result, config)
        workspaces = await workspace_service.setup_group(requests=requests)
    except Exception as exc:
        elapsed = time.monotonic() - start
        phase = CoordinationPhaseResult(
            phase=phase_name,
            success=False,
            duration_seconds=elapsed,
            error=str(exc),
        )
        logger.warning(
            COORDINATION_PHASE_FAILED,
            phase=phase_name,
            error=str(exc),
        )
        return (), phase
    else:
        elapsed = time.monotonic() - start
        phase = CoordinationPhaseResult(
            phase=phase_name,
            success=True,
            duration_seconds=elapsed,
        )
        logger.info(
            COORDINATION_PHASE_COMPLETED,
            phase=phase_name,
            workspace_count=len(workspaces),
            duration_seconds=elapsed,
        )
        return workspaces, phase


async def _merge_workspaces(
    workspace_service: WorkspaceIsolationService,
    workspaces: tuple[Workspace, ...],
) -> tuple[WorkspaceGroupResult | None, CoordinationPhaseResult]:
    """Merge workspaces and return result with a phase result."""
    start = time.monotonic()
    phase_name = "merge"

    logger.info(COORDINATION_PHASE_STARTED, phase=phase_name)
    try:
        merge_result = await workspace_service.merge_group(
            workspaces=workspaces,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        phase = CoordinationPhaseResult(
            phase=phase_name,
            success=False,
            duration_seconds=elapsed,
            error=str(exc),
        )
        logger.warning(
            COORDINATION_PHASE_FAILED,
            phase=phase_name,
            error=str(exc),
        )
        return None, phase
    else:
        elapsed = time.monotonic() - start
        phase = CoordinationPhaseResult(
            phase=phase_name,
            success=True,
            duration_seconds=elapsed,
        )
        logger.info(
            COORDINATION_PHASE_COMPLETED,
            phase=phase_name,
            duration_seconds=elapsed,
        )
        return merge_result, phase


async def _teardown_workspaces(
    workspace_service: WorkspaceIsolationService,
    workspaces: tuple[Workspace, ...],
) -> None:
    """Best-effort teardown with logging."""
    logger.info(
        COORDINATION_CLEANUP_STARTED,
        workspace_count=len(workspaces),
    )
    try:
        await workspace_service.teardown_group(workspaces=workspaces)
    except Exception as exc:
        logger.warning(
            COORDINATION_CLEANUP_COMPLETED,
            workspace_count=len(workspaces),
            error=str(exc),
        )
    else:
        logger.info(
            COORDINATION_CLEANUP_COMPLETED,
            workspace_count=len(workspaces),
        )


async def _execute_waves(
    groups: tuple[ParallelExecutionGroup, ...],
    parallel_executor: ParallelExecutor,
    *,
    fail_fast: bool,
) -> tuple[list[CoordinationWave], list[CoordinationPhaseResult]]:
    """Execute wave groups sequentially, returning waves and phases."""
    waves: list[CoordinationWave] = []
    phases: list[CoordinationPhaseResult] = []

    for wave_idx, group in enumerate(groups):
        start = time.monotonic()
        phase_name = f"execute_wave_{wave_idx}"
        subtask_ids = tuple(NotBlankStr(a.task.id) for a in group.assignments)

        logger.info(
            COORDINATION_WAVE_STARTED,
            wave_index=wave_idx,
            subtask_count=len(subtask_ids),
        )

        try:
            exec_result = await parallel_executor.execute_group(group)
            elapsed = time.monotonic() - start

            wave = CoordinationWave(
                wave_index=wave_idx,
                subtask_ids=subtask_ids,
                execution_result=exec_result,
            )
            waves.append(wave)

            success = exec_result.all_succeeded
            phases.append(
                CoordinationPhaseResult(
                    phase=phase_name,
                    success=success,
                    duration_seconds=elapsed,
                    error=None
                    if success
                    else (
                        f"Wave {wave_idx}: {exec_result.agents_failed} agent(s) failed"
                    ),
                )
            )

            logger.info(
                COORDINATION_WAVE_COMPLETED,
                wave_index=wave_idx,
                succeeded=exec_result.agents_succeeded,
                failed=exec_result.agents_failed,
                duration_seconds=elapsed,
            )

            if not success and fail_fast:
                break

        except Exception as exc:
            elapsed = time.monotonic() - start
            wave = CoordinationWave(
                wave_index=wave_idx,
                subtask_ids=subtask_ids,
            )
            waves.append(wave)
            phases.append(
                CoordinationPhaseResult(
                    phase=phase_name,
                    success=False,
                    duration_seconds=elapsed,
                    error=str(exc),
                )
            )
            if fail_fast:
                break

    return waves, phases


def _rebuild_group_with_workspaces(
    group: ParallelExecutionGroup,
    wave_workspaces: tuple[Workspace, ...],
) -> ParallelExecutionGroup:
    """Rebuild an execution group with workspace resource claims."""
    ws_lookup = {ws.task_id: ws.worktree_path for ws in wave_workspaces}
    new_assignments = tuple(
        AgentAssignment(
            identity=a.identity,
            task=a.task,
            resource_claims=(ws_lookup[a.task.id],)
            if a.task.id in ws_lookup
            else a.resource_claims,
            max_turns=a.max_turns,
            timeout_seconds=a.timeout_seconds,
            memory_messages=a.memory_messages,
            completion_config=a.completion_config,
        )
        for a in group.assignments
    )
    return ParallelExecutionGroup(
        group_id=group.group_id,
        assignments=new_assignments,
        max_concurrency=group.max_concurrency,
        fail_fast=group.fail_fast,
    )


class SasDispatcher:
    """Single-Agent-Step dispatcher.

    Sequential waves of 1 subtask each. No workspace isolation.
    Single agent runs all subtasks.
    """

    async def dispatch(
        self,
        *,
        decomposition_result: DecompositionResult,
        routing_result: RoutingResult,
        parallel_executor: ParallelExecutor,
        workspace_service: WorkspaceIsolationService | None,  # noqa: ARG002
        config: CoordinationConfig,
    ) -> DispatchResult:
        """Execute subtasks sequentially, one per wave."""
        groups = build_execution_waves(
            decomposition_result=decomposition_result,
            routing_result=routing_result,
            config=config,
        )

        waves, phases = await _execute_waves(
            groups, parallel_executor, fail_fast=config.fail_fast
        )

        return DispatchResult(
            waves=tuple(waves),
            phases=tuple(phases),
        )


class CentralizedDispatcher:
    """Centralized dispatcher.

    Waves from DAG parallel_groups(). Workspace isolation for all
    agents. Merge after all waves complete.
    """

    async def dispatch(
        self,
        *,
        decomposition_result: DecompositionResult,
        routing_result: RoutingResult,
        parallel_executor: ParallelExecutor,
        workspace_service: WorkspaceIsolationService | None,
        config: CoordinationConfig,
    ) -> DispatchResult:
        """Execute waves with workspace isolation and post-merge."""
        all_phases: list[CoordinationPhaseResult] = []
        workspaces: tuple[Workspace, ...] = ()
        merge_result: WorkspaceGroupResult | None = None

        # Setup workspaces if service available and isolation enabled
        if workspace_service is not None and config.enable_workspace_isolation:
            workspaces, setup_phase = await _setup_workspaces(
                workspace_service, routing_result, config
            )
            all_phases.append(setup_phase)
            if not setup_phase.success:
                return DispatchResult(phases=tuple(all_phases))

        try:
            groups = build_execution_waves(
                decomposition_result=decomposition_result,
                routing_result=routing_result,
                config=config,
                workspaces=workspaces,
            )

            waves, exec_phases = await _execute_waves(
                groups,
                parallel_executor,
                fail_fast=config.fail_fast,
            )
            all_phases.extend(exec_phases)

            # Merge workspaces after all waves
            if workspaces and workspace_service is not None:
                merge_result, merge_phase = await _merge_workspaces(
                    workspace_service, workspaces
                )
                all_phases.append(merge_phase)

            return DispatchResult(
                waves=tuple(waves),
                workspaces=workspaces,
                workspace_merge=merge_result,
                phases=tuple(all_phases),
            )
        finally:
            if workspaces and workspace_service is not None:
                await _teardown_workspaces(workspace_service, workspaces)


class DecentralizedDispatcher:
    """Decentralized dispatcher.

    Single wave with all subtasks in parallel. Mandatory workspace
    isolation.
    """

    async def dispatch(
        self,
        *,
        decomposition_result: DecompositionResult,
        routing_result: RoutingResult,
        parallel_executor: ParallelExecutor,
        workspace_service: WorkspaceIsolationService | None,
        config: CoordinationConfig,
    ) -> DispatchResult:
        """Execute all subtasks in a single parallel wave."""
        all_phases: list[CoordinationPhaseResult] = []
        workspaces: tuple[Workspace, ...] = ()
        merge_result: WorkspaceGroupResult | None = None

        # Setup workspaces (mandatory for decentralized)
        if workspace_service is not None and config.enable_workspace_isolation:
            workspaces, setup_phase = await _setup_workspaces(
                workspace_service, routing_result, config
            )
            all_phases.append(setup_phase)
            if not setup_phase.success:
                return DispatchResult(phases=tuple(all_phases))

        try:
            groups = build_execution_waves(
                decomposition_result=decomposition_result,
                routing_result=routing_result,
                config=config,
                workspaces=workspaces,
            )

            waves, exec_phases = await _execute_waves(
                groups,
                parallel_executor,
                fail_fast=config.fail_fast,
            )
            all_phases.extend(exec_phases)

            # Merge workspaces
            if workspaces and workspace_service is not None:
                merge_result, merge_phase = await _merge_workspaces(
                    workspace_service, workspaces
                )
                all_phases.append(merge_phase)

            return DispatchResult(
                waves=tuple(waves),
                workspaces=workspaces,
                workspace_merge=merge_result,
                phases=tuple(all_phases),
            )
        finally:
            if workspaces and workspace_service is not None:
                await _teardown_workspaces(workspace_service, workspaces)


class ContextDependentDispatcher:
    """Context-dependent dispatcher.

    Waves from DAG. Single-subtask waves skip isolation.
    Multi-subtask waves use workspace isolation with per-wave
    setup/merge.
    """

    async def dispatch(
        self,
        *,
        decomposition_result: DecompositionResult,
        routing_result: RoutingResult,
        parallel_executor: ParallelExecutor,
        workspace_service: WorkspaceIsolationService | None,
        config: CoordinationConfig,
    ) -> DispatchResult:
        """Execute waves with conditional workspace isolation."""
        groups = build_execution_waves(
            decomposition_result=decomposition_result,
            routing_result=routing_result,
            config=config,
        )

        all_phases: list[CoordinationPhaseResult] = []
        all_waves: list[CoordinationWave] = []
        all_workspaces: list[Workspace] = []
        merge_results: list[WorkspaceGroupResult] = []

        for wave_idx, group in enumerate(groups):
            wave_workspaces, exec_group = await self._setup_wave(
                wave_idx, group, workspace_service, config, all_phases, all_workspaces
            )
            if exec_group is None:
                continue

            await self._execute_wave(
                wave_idx,
                exec_group,
                parallel_executor,
                config,
                all_waves,
                all_phases,
                wave_workspaces,
                workspace_service,
                merge_results,
            )

        return self._build_result(all_waves, all_workspaces, merge_results, all_phases)

    async def _setup_wave(  # noqa: PLR0913
        self,
        wave_idx: int,
        group: ParallelExecutionGroup,
        workspace_service: WorkspaceIsolationService | None,
        config: CoordinationConfig,
        all_phases: list[CoordinationPhaseResult],
        all_workspaces: list[Workspace],
    ) -> tuple[tuple[Workspace, ...], ParallelExecutionGroup | None]:
        """Set up workspaces for a wave if needed.

        Returns the wave's workspaces and the (possibly rebuilt) group,
        or ``None`` if setup failed.
        """
        needs_isolation = (
            len(group.assignments) > 1
            and workspace_service is not None
            and config.enable_workspace_isolation
        )

        if not needs_isolation or workspace_service is None:
            return (), group

        wave_requests = tuple(
            WorkspaceRequest(
                task_id=a.task.id,
                agent_id=a.agent_id,
                base_branch=config.base_branch,
            )
            for a in group.assignments
        )
        ws_start = time.monotonic()
        try:
            wave_workspaces = await workspace_service.setup_group(
                requests=wave_requests,
            )
        except Exception as exc:
            ws_elapsed = time.monotonic() - ws_start
            all_phases.append(
                CoordinationPhaseResult(
                    phase=f"workspace_setup_wave_{wave_idx}",
                    success=False,
                    duration_seconds=ws_elapsed,
                    error=str(exc),
                )
            )
            return (), None

        all_workspaces.extend(wave_workspaces)
        ws_elapsed = time.monotonic() - ws_start
        all_phases.append(
            CoordinationPhaseResult(
                phase=f"workspace_setup_wave_{wave_idx}",
                success=True,
                duration_seconds=ws_elapsed,
            )
        )

        rebuilt = _rebuild_group_with_workspaces(group, wave_workspaces)
        return wave_workspaces, rebuilt

    async def _execute_wave(  # noqa: PLR0913
        self,
        wave_idx: int,
        group: ParallelExecutionGroup,
        parallel_executor: ParallelExecutor,
        config: CoordinationConfig,  # noqa: ARG002
        all_waves: list[CoordinationWave],
        all_phases: list[CoordinationPhaseResult],
        wave_workspaces: tuple[Workspace, ...],
        workspace_service: WorkspaceIsolationService | None,
        merge_results: list[WorkspaceGroupResult],
    ) -> None:
        """Execute a single wave and handle per-wave merge/teardown."""
        start = time.monotonic()
        subtask_ids = tuple(NotBlankStr(a.task.id) for a in group.assignments)

        logger.info(
            COORDINATION_WAVE_STARTED,
            wave_index=wave_idx,
            subtask_count=len(subtask_ids),
        )

        try:
            exec_result = await parallel_executor.execute_group(group)
            elapsed = time.monotonic() - start

            all_waves.append(
                CoordinationWave(
                    wave_index=wave_idx,
                    subtask_ids=subtask_ids,
                    execution_result=exec_result,
                )
            )

            success = exec_result.all_succeeded
            all_phases.append(
                CoordinationPhaseResult(
                    phase=f"execute_wave_{wave_idx}",
                    success=success,
                    duration_seconds=elapsed,
                    error=None
                    if success
                    else (
                        f"Wave {wave_idx}: {exec_result.agents_failed} agent(s) failed"
                    ),
                )
            )

            logger.info(
                COORDINATION_WAVE_COMPLETED,
                wave_index=wave_idx,
                succeeded=exec_result.agents_succeeded,
                failed=exec_result.agents_failed,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            all_waves.append(
                CoordinationWave(
                    wave_index=wave_idx,
                    subtask_ids=subtask_ids,
                )
            )
            all_phases.append(
                CoordinationPhaseResult(
                    phase=f"execute_wave_{wave_idx}",
                    success=False,
                    duration_seconds=elapsed,
                    error=str(exc),
                )
            )
        finally:
            if wave_workspaces and workspace_service is not None:
                merge_result, merge_phase = await _merge_workspaces(
                    workspace_service, wave_workspaces
                )
                all_phases.append(merge_phase)
                if merge_result is not None:
                    merge_results.append(merge_result)
                await _teardown_workspaces(workspace_service, wave_workspaces)

    @staticmethod
    def _build_result(
        all_waves: list[CoordinationWave],
        all_workspaces: list[Workspace],
        merge_results: list[WorkspaceGroupResult],
        all_phases: list[CoordinationPhaseResult],
    ) -> DispatchResult:
        """Combine wave and merge results into a DispatchResult."""
        combined_merge: WorkspaceGroupResult | None = None
        if merge_results:
            all_merge_results = tuple(
                mr for wgr in merge_results for mr in wgr.merge_results
            )
            total_merge_duration = sum(wgr.duration_seconds for wgr in merge_results)
            combined_merge = WorkspaceGroupResult(
                group_id="context-dependent-merge",
                merge_results=all_merge_results,
                duration_seconds=total_merge_duration,
            )

        return DispatchResult(
            waves=tuple(all_waves),
            workspaces=tuple(all_workspaces),
            workspace_merge=combined_merge,
            phases=tuple(all_phases),
        )


def select_dispatcher(topology: CoordinationTopology) -> TopologyDispatcher:
    """Select the appropriate dispatcher for a topology.

    Args:
        topology: The resolved coordination topology.

    Returns:
        A dispatcher instance for the topology.

    Raises:
        ValueError: If AUTO topology is passed (must be resolved first).
    """
    logger.debug(COORDINATION_TOPOLOGY_RESOLVED, topology=topology.value)

    dispatchers: dict[CoordinationTopology, TopologyDispatcher] = {
        CoordinationTopology.SAS: SasDispatcher(),
        CoordinationTopology.CENTRALIZED: CentralizedDispatcher(),
        CoordinationTopology.DECENTRALIZED: DecentralizedDispatcher(),
        CoordinationTopology.CONTEXT_DEPENDENT: ContextDependentDispatcher(),
    }

    dispatcher = dispatchers.get(topology)
    if dispatcher is None:
        msg = (
            f"Cannot dispatch topology {topology.value!r}: "
            "AUTO must be resolved before dispatch"
        )
        raise ValueError(msg)
    return dispatcher
