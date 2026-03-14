"""Coordinator factory — builds a fully wired MultiAgentCoordinator.

Constructs the decomposition, routing, execution, and workspace
dependency tree from config and runtime services.
"""

from typing import TYPE_CHECKING

from ai_company.engine.coordination.service import MultiAgentCoordinator
from ai_company.engine.decomposition.classifier import TaskStructureClassifier
from ai_company.engine.decomposition.service import DecompositionService
from ai_company.engine.errors import DecompositionError
from ai_company.engine.parallel import ParallelExecutor
from ai_company.engine.routing.scorer import AgentTaskScorer
from ai_company.engine.routing.service import TaskRoutingService
from ai_company.engine.routing.topology_selector import TopologySelector
from ai_company.observability import get_logger
from ai_company.observability.events.coordination import (
    COORDINATION_STARTED,
)

if TYPE_CHECKING:
    from ai_company.config.schema import TaskAssignmentConfig
    from ai_company.core.task import Task
    from ai_company.engine.agent_engine import AgentEngine
    from ai_company.engine.coordination.section_config import (
        CoordinationSectionConfig,
    )
    from ai_company.engine.decomposition.models import (
        DecompositionContext,
        DecompositionPlan,
    )
    from ai_company.engine.decomposition.protocol import DecompositionStrategy
    from ai_company.engine.shutdown import ShutdownManager
    from ai_company.engine.task_engine import TaskEngine
    from ai_company.engine.workspace.config import WorkspaceIsolationConfig
    from ai_company.engine.workspace.protocol import WorkspaceIsolationStrategy
    from ai_company.engine.workspace.service import WorkspaceIsolationService
    from ai_company.providers.protocol import CompletionProvider

logger = get_logger(__name__)


class _NoProviderDecompositionStrategy:
    """Placeholder strategy that raises when no LLM provider is available.

    Used when the factory is called without a provider, so that the
    coordinator can still be constructed (e.g. for manual decomposition
    tests). Attempting to actually decompose will raise a clear error.
    """

    async def decompose(
        self,
        task: Task,  # noqa: ARG002
        context: DecompositionContext,  # noqa: ARG002
    ) -> DecompositionPlan:
        """Raise DecompositionError — no provider configured."""
        msg = (
            "No LLM provider configured for decomposition. "
            "Provide a CompletionProvider and decomposition_model "
            "to enable LLM-based task decomposition."
        )
        raise DecompositionError(msg)


def build_coordinator(  # noqa: PLR0913
    *,
    config: CoordinationSectionConfig,
    engine: AgentEngine,
    task_assignment_config: TaskAssignmentConfig,
    provider: CompletionProvider | None = None,
    decomposition_model: str | None = None,
    task_engine: TaskEngine | None = None,
    workspace_strategy: WorkspaceIsolationStrategy | None = None,
    workspace_config: WorkspaceIsolationConfig | None = None,
    shutdown_manager: ShutdownManager | None = None,
) -> MultiAgentCoordinator:
    """Build a fully wired :class:`MultiAgentCoordinator`.

    Constructs the dependency tree:
        1. ``TaskStructureClassifier`` (no deps)
        2. ``DecompositionStrategy`` — LLM if provider+model provided,
           otherwise a placeholder that raises at decompose-time
        3. ``DecompositionService(strategy, classifier)``
        4. ``AgentTaskScorer(min_score=task_assignment_config.min_score)``
        5. ``TopologySelector(config.auto_topology_rules)``
        6. ``TaskRoutingService(scorer, topology_selector)``
        7. ``ParallelExecutor(engine=engine)``
        8. ``WorkspaceIsolationService`` if workspace deps provided
        9. ``MultiAgentCoordinator(decomposition, routing, executor, ...)``

    Args:
        config: Company-level coordination section config.
        engine: Agent execution engine (for parallel executor).
        task_assignment_config: Task assignment config (for min_score).
        provider: Optional LLM provider for decomposition.
        decomposition_model: Optional model ID for decomposition.
        task_engine: Optional task engine for parent status updates.
        workspace_strategy: Optional workspace isolation strategy.
        workspace_config: Optional workspace isolation config.
        shutdown_manager: Optional shutdown manager for the executor.

    Returns:
        A fully constructed ``MultiAgentCoordinator``.
    """
    logger.debug(
        COORDINATION_STARTED,
        note="Building coordinator from config",
        topology=config.topology.value,
        has_provider=provider is not None,
        has_workspace=workspace_strategy is not None,
    )

    # 1. Classifier
    classifier = TaskStructureClassifier()

    # 2. Decomposition strategy
    strategy: DecompositionStrategy
    if provider is not None and decomposition_model is not None:
        from ai_company.engine.decomposition.llm import (  # noqa: PLC0415
            LlmDecompositionStrategy,
        )

        strategy = LlmDecompositionStrategy(
            provider=provider,
            model=decomposition_model,
        )
    else:
        strategy = _NoProviderDecompositionStrategy()  # type: ignore[assignment]

    # 3. Decomposition service
    decomposition_service = DecompositionService(strategy, classifier)

    # 4. Scorer
    scorer = AgentTaskScorer(min_score=task_assignment_config.min_score)

    # 5. Topology selector
    topology_selector = TopologySelector(config.auto_topology_rules)

    # 6. Routing service
    routing_service = TaskRoutingService(scorer, topology_selector)

    # 7. Parallel executor
    parallel_executor = ParallelExecutor(
        engine=engine,
        shutdown_manager=shutdown_manager,
    )

    # 8. Workspace isolation service (optional)
    workspace_service: WorkspaceIsolationService | None = None
    if workspace_strategy is not None and workspace_config is not None:
        from ai_company.engine.workspace.service import (  # noqa: PLC0415
            WorkspaceIsolationService,
        )

        workspace_service = WorkspaceIsolationService(
            strategy=workspace_strategy,
            config=workspace_config,
        )

    # 9. Coordinator
    return MultiAgentCoordinator(
        decomposition_service=decomposition_service,
        routing_service=routing_service,
        parallel_executor=parallel_executor,
        workspace_service=workspace_service,
        task_engine=task_engine,
    )
