"""Agent engine -- top-level orchestrator.

Ties together prompt construction, execution context, execution loop,
tool invocation, and budget tracking into a single ``run()`` entry point.
"""

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal, TypedDict

from synthorg.budget.currency import DEFAULT_CURRENCY
from synthorg.budget.errors import BudgetExhaustedError, QuotaExhaustedError
from synthorg.budget.quota import DegradationAction
from synthorg.core.enums import FailureCategory  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine._security_factory import (
    make_security_interceptor,
    registry_with_approval_tool,
)
from synthorg.engine._validation import (
    validate_agent,
    validate_run_inputs,
    validate_task,
    validate_task_metadata,
)
from synthorg.engine.approval_gate import ApprovalGate
from synthorg.engine.checkpoint.models import CheckpointConfig
from synthorg.engine.checkpoint.resume import (
    cleanup_checkpoint_artifacts,
    deserialize_and_reconcile,
    make_loop_with_callback,
)
from synthorg.engine.classification.pipeline import classify_execution_errors
from synthorg.engine.context import DEFAULT_MAX_TURNS, AgentContext
from synthorg.engine.cost_recording import record_execution_costs
from synthorg.engine.errors import (
    ExecutionStateError,
    ProjectAgentNotMemberError,
    ProjectNotFoundError,
)
from synthorg.engine.loop_protocol import (
    ExecutionResult,
    TerminationReason,
    make_budget_checker,
)
from synthorg.engine.loop_selector import (
    AutoLoopConfig,
    build_execution_loop,
    select_loop_type,
)
from synthorg.engine.metrics import TaskCompletionMetrics
from synthorg.engine.prompt import (
    SystemPrompt,
    build_error_prompt,
    build_system_prompt,
    format_task_instruction,
)
from synthorg.engine.react_loop import ReactLoop
from synthorg.engine.recovery import (
    FailAndReassignStrategy,
    RecoveryResult,
    RecoveryStrategy,
)
from synthorg.engine.run_result import AgentRunResult
from synthorg.engine.sanitization import sanitize_message
from synthorg.engine.task_sync import (
    apply_post_execution_transitions,
    sync_to_task_engine,
    transition_task_if_needed,
)
from synthorg.observability import get_logger
from synthorg.observability.correlation import correlation_scope
from synthorg.observability.events.approval_gate import (
    APPROVAL_GATE_LOOP_WIRING_WARNING,
)
from synthorg.observability.events.degradation import (
    DEGRADATION_PROVIDER_SWAPPED,
)
from synthorg.observability.events.execution import (
    EXECUTION_ENGINE_BUDGET_STOPPED,
    EXECUTION_ENGINE_COMPLETE,
    EXECUTION_ENGINE_CREATED,
    EXECUTION_ENGINE_ERROR,
    EXECUTION_ENGINE_PROMPT_BUILT,
    EXECUTION_ENGINE_START,
    EXECUTION_ENGINE_TASK_METRICS,
    EXECUTION_ENGINE_TASK_TRANSITION,
    EXECUTION_ENGINE_TIMEOUT,
    EXECUTION_LOOP_AUTO_SELECTED,
    EXECUTION_LOOP_BUDGET_UNAVAILABLE,
    EXECUTION_PROJECT_VALIDATION_FAILED,
    EXECUTION_RECOVERY_DIAGNOSIS,
    EXECUTION_RECOVERY_FAILED,
    EXECUTION_RESUME_COMPLETE,
    EXECUTION_RESUME_FAILED,
    EXECUTION_RESUME_START,
)
from synthorg.observability.events.prompt import (
    PROMPT_PERSONALITY_NOTIFY_FAILED,
    PROMPT_PERSONALITY_TRIMMED,
    PROMPT_TOKEN_RATIO_HIGH,
)
from synthorg.observability.events.session import (
    SESSION_REPLAY_LOW_COMPLETENESS,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.errors import DriverNotRegisteredError
from synthorg.providers.models import ChatMessage
from synthorg.security.audit import AuditLog
from synthorg.security.autonomy.models import EffectiveAutonomy  # noqa: TC001
from synthorg.tools.invoker import ToolInvoker
from synthorg.tools.permissions import ToolPermissionChecker

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.api.approval_store import ApprovalStore
    from synthorg.budget.coordination_collector import CoordinationMetricsCollector
    from synthorg.budget.coordination_config import ErrorTaxonomyConfig
    from synthorg.budget.degradation import PreFlightResult
    from synthorg.budget.enforcer import BudgetEnforcer
    from synthorg.budget.tracker import CostTracker
    from synthorg.communication.event_stream.interrupt import InterruptStore
    from synthorg.communication.event_stream.stream import EventStreamHub
    from synthorg.config.schema import ProviderConfig
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.task import Task
    from synthorg.engine.compaction import CompactionCallback
    from synthorg.engine.coordination.attribution import (
        CoordinationResultWithAttribution,
    )
    from synthorg.engine.coordination.models import (
        CoordinationContext,
    )
    from synthorg.engine.coordination.service import MultiAgentCoordinator
    from synthorg.engine.hybrid_models import HybridLoopConfig
    from synthorg.engine.loop_protocol import (
        BudgetChecker,
        ExecutionLoop,
        ShutdownChecker,
    )
    from synthorg.engine.middleware.protocol import AgentMiddlewareChain
    from synthorg.engine.plan_models import PlanExecuteConfig
    from synthorg.engine.session import EventReader
    from synthorg.engine.stagnation.protocol import StagnationDetector
    from synthorg.engine.task_engine import TaskEngine
    from synthorg.memory.injection import MemoryInjectionStrategy
    from synthorg.memory.procedural.models import ProceduralMemoryConfig
    from synthorg.memory.procedural.proposer import ProceduralMemoryProposer
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.ontology.injection.protocol import OntologyInjectionStrategy
    from synthorg.persistence.artifact_project_repos import (
        ProjectRepository,
    )
    from synthorg.persistence.repositories import (
        CheckpointRepository,
        HeartbeatRepository,
        ParkedContextRepository,
    )
    from synthorg.providers.models import CompletionConfig
    from synthorg.providers.protocol import CompletionProvider
    from synthorg.providers.registry import ProviderRegistry
    from synthorg.providers.routing.resolver import ModelResolver
    from synthorg.security.config import SecurityConfig
    from synthorg.security.protocol import SecurityInterceptionStrategy
    from synthorg.settings.resolver import ConfigResolver
    from synthorg.tools.invocation_tracker import ToolInvocationTracker
    from synthorg.tools.registry import ToolRegistry

logger = get_logger(__name__)

_PROMPT_TOKEN_RATIO_THRESHOLD: float = 0.3
"""Prompt-to-total token ratio above which a warning is emitted."""

_REPLAY_LOW_COMPLETENESS_THRESHOLD: float = 0.5
"""Log a warning when session replay completeness is below this."""

_DEFAULT_RECOVERY_STRATEGY = FailAndReassignStrategy()

# Cap on the number of failed acceptance criteria embedded in the
# post-recovery transition reason.  Criteria beyond this limit are
# summarised as "+N more" so the status history does not grow
# unbounded on tasks with many criteria.
_TRANSITION_REASON_CRITERIA_CAP = 5
"""Module-level default instance for the recovery strategy."""


class PersonalityTrimPayload(TypedDict):
    """Structured payload forwarded to :data:`PersonalityTrimNotifier` callbacks.

    All keys are always present when the engine invokes the notifier from
    :meth:`AgentEngine._prepare_context`.  Identifier fields (``agent_id``,
    ``agent_name``, ``task_id``) are typed as :data:`NotBlankStr` to match
    the project-wide identifier convention documented in CLAUDE.md -- the
    Pydantic constraint is not enforced inside a ``TypedDict`` at runtime,
    but the alias communicates the contract to readers and keeps this
    surface consistent with the rest of the codebase.  ``trim_tier`` is
    one of ``1``, ``2``, or ``3`` (enforced upstream by
    :class:`synthorg.engine.prompt_helpers.PersonalityTrimInfo`).
    """

    agent_id: NotBlankStr
    agent_name: NotBlankStr
    task_id: NotBlankStr
    before_tokens: int
    after_tokens: int
    max_tokens: int
    trim_tier: Literal[1, 2, 3]
    budget_met: bool


type PersonalityTrimNotifier = Callable[[PersonalityTrimPayload], Awaitable[None]]
"""Async callback invoked when an agent's personality section is trimmed.

Contract: the engine invokes this callback best-effort from
:meth:`AgentEngine._prepare_context`.  Any exception the callback raises
(except :class:`MemoryError` and :class:`RecursionError`, which propagate) is
logged via ``PROMPT_PERSONALITY_NOTIFY_FAILED`` and swallowed so the trim
notification never blocks task execution.  :class:`asyncio.CancelledError`
propagates naturally because it is a :class:`BaseException` subclass.

External runners (e.g. an API server hosting an ``AgentEngine``) should wire
this to ``channels_plugin.publish(...)`` with a ``WsEvent(event_type=
WsEventType.PERSONALITY_TRIMMED, channel=CHANNEL_AGENTS, ...)`` so the
dashboard can show a live toast when trimming activates.  API-layer
integrations should use the factory function
:func:`synthorg.api.app.make_personality_trim_notifier`, which returns a
ready-to-wire callback matching this contract.
"""


class AgentEngine:
    """Top-level orchestrator for agent execution.

    Builds the system prompt, creates an execution context, delegates
    to the configured ``ExecutionLoop``, and returns an ``AgentRunResult``
    with full metadata.

    Args:
        provider: LLM completion provider (required).
        execution_loop: Static execution loop.  Defaults to
            ``ReactLoop()``.  Mutually exclusive with
            ``auto_loop_config``.
        tool_registry: Optional tools available to the agent.
        cost_tracker: Falls back to ``budget_enforcer.cost_tracker``
            when ``None`` and ``budget_enforcer`` is provided. Must
            match ``budget_enforcer.cost_tracker`` if both supplied.
        recovery_strategy: Defaults to ``FailAndReassignStrategy``.
        shutdown_checker: Returns ``True`` for graceful shutdown.
        error_taxonomy_config: Post-execution error classification.
        budget_enforcer: Pre-flight checks, auto-downgrade, and
            enhanced in-flight budget checking.
        security_config: Optional security subsystem configuration.
        approval_store: Optional approval queue store.
        parked_context_repo: Optional repository for parking
            execution contexts during approval escalation.
        task_engine: Optional centralized task engine for real-time
            status sync (incremental transitions at each lifecycle
            point, best-effort).
        checkpoint_repo: Optional checkpoint repository for
            persisting execution state at turn boundaries.
            Must be paired with ``heartbeat_repo``.
        heartbeat_repo: Optional heartbeat repository for
            crash detection during execution.  Must be paired
            with ``checkpoint_repo``.
        checkpoint_config: Checkpoint tuning (interval, max size).
            Defaults to ``CheckpointConfig()``.
        coordinator: Optional multi-agent coordinator for delegated
            coordination via :meth:`coordinate`.
        stagnation_detector: Optional detector for repetitive
            tool-call patterns.  Wired into the execution loop
            when using auto-selection or the default loop.
        auto_loop_config: Optional auto-loop selection configuration.
            Selects the execution loop per-task based on complexity
            and budget state.  Mutually exclusive with
            ``execution_loop``.
        hybrid_loop_config: Optional configuration for the hybrid
            plan+ReAct loop.  Passed to ``build_execution_loop``
            when auto-selection picks ``"hybrid"``.
        compaction_callback: Optional async callback invoked at turn
            boundaries to compress older conversation turns.  Passed
            to the execution loop (both static default and
            auto-selected).  When ``execution_loop`` is provided
            directly, the caller is responsible for wiring this
            callback into the loop.
        plan_execute_config: Optional configuration for the
            plan-execute loop.  Passed to ``build_execution_loop``
            when auto-selection picks ``"plan_execute"``.
        provider_registry: Optional registry of completion providers.
            Used for runtime provider CRUD and model discovery.
        tool_invocation_tracker: Optional tracker for recording tool
            invocations in the activity timeline.  Passed through to
            each ``ToolInvoker`` created by ``_make_tool_invoker``.
        memory_injection_strategy: Optional memory injection strategy.
            When a ``ToolBasedInjectionStrategy`` is provided, memory
            tools (``search_memory``, ``recall_memory``) are registered
            in the ``ToolRegistry`` for each agent execution.
        procedural_memory_config: Optional configuration for
            procedural memory auto-generation from agent failures.
            When set (and ``memory_backend`` is also provided), a
            proposer LLM call analyses failures and stores
            procedural memory entries.
        memory_backend: Optional memory backend used by both the
            procedural memory pipeline and distillation capture.  When
            omitted, both features are silently skipped regardless of
            ``procedural_memory_config`` / ``distillation_capture_enabled``.
        distillation_capture_enabled: When ``True``, the post-execution
            pipeline invokes ``capture_distillation`` to record a
            trajectory summary as an EPISODIC memory entry tagged
            ``"distillation"``.  Requires ``memory_backend`` to be
            provided; silently no-ops otherwise (skip paths are logged
            at DEBUG for operator visibility).  Defaults to ``False``
            (opt-in).
        config_resolver: Optional settings resolver for reading
            runtime ENGINE settings (personality trimming controls).
            When ``None``, built-in defaults are used.
        personality_trim_notifier: Optional async callback invoked
            when an agent's personality section is trimmed at prompt
            build time.  See :data:`PersonalityTrimNotifier` for the
            payload contract and recommended wiring.  When ``None``
            (or when the ``engine.personality_trimming_notify`` setting
            is ``False``), no callback fires.
        audit_log: Optional audit log for recording security
            evaluations and tool invocation verdicts.  When ``None``,
            a fresh :class:`AuditLog` is created internally.
        event_reader: Optional event reader for session replay.
            When provided alongside ``resume_execution_id`` in
            :meth:`run`, enables stateless recovery from a crashed
            execution via :meth:`Session.replay`.
    """

    def __init__(  # noqa: PLR0913, PLR0915
        self,
        *,
        provider: CompletionProvider,
        execution_loop: ExecutionLoop | None = None,
        tool_registry: ToolRegistry | None = None,
        cost_tracker: CostTracker | None = None,
        recovery_strategy: RecoveryStrategy | None = _DEFAULT_RECOVERY_STRATEGY,
        shutdown_checker: ShutdownChecker | None = None,
        error_taxonomy_config: ErrorTaxonomyConfig | None = None,
        budget_enforcer: BudgetEnforcer | None = None,
        security_config: SecurityConfig | None = None,
        approval_store: ApprovalStore | None = None,
        parked_context_repo: ParkedContextRepository | None = None,
        task_engine: TaskEngine | None = None,
        checkpoint_repo: CheckpointRepository | None = None,
        heartbeat_repo: HeartbeatRepository | None = None,
        checkpoint_config: CheckpointConfig | None = None,
        coordinator: MultiAgentCoordinator | None = None,
        stagnation_detector: StagnationDetector | None = None,
        auto_loop_config: AutoLoopConfig | None = None,
        hybrid_loop_config: HybridLoopConfig | None = None,
        compaction_callback: CompactionCallback | None = None,
        plan_execute_config: PlanExecuteConfig | None = None,
        provider_registry: ProviderRegistry | None = None,
        provider_configs: Mapping[str, ProviderConfig] | None = None,
        model_resolver: ModelResolver | None = None,
        tool_invocation_tracker: ToolInvocationTracker | None = None,
        memory_injection_strategy: MemoryInjectionStrategy | None = None,
        ontology_injection_strategy: OntologyInjectionStrategy | None = None,
        procedural_memory_config: ProceduralMemoryConfig | None = None,
        memory_backend: MemoryBackend | None = None,
        distillation_capture_enabled: bool = False,
        config_resolver: ConfigResolver | None = None,
        personality_trim_notifier: PersonalityTrimNotifier | None = None,
        coordination_metrics_collector: CoordinationMetricsCollector | None = None,
        audit_log: AuditLog | None = None,
        project_repo: ProjectRepository | None = None,
        agent_middleware_chain: AgentMiddlewareChain | None = None,
        event_reader: EventReader | None = None,
        event_stream_hub: EventStreamHub | None = None,
        interrupt_store: InterruptStore | None = None,
    ) -> None:
        self._agent_middleware_chain = agent_middleware_chain
        self._event_reader = event_reader
        self._event_stream_hub = event_stream_hub
        self._interrupt_store = interrupt_store
        if execution_loop is not None and auto_loop_config is not None:
            msg = "execution_loop and auto_loop_config are mutually exclusive"
            logger.warning(
                EXECUTION_ENGINE_ERROR,
                reason=msg,
            )
            raise ValueError(msg)
        self._provider = provider
        self._provider_registry = provider_registry
        self._provider_configs = provider_configs
        self._model_resolver = model_resolver
        self._approval_store = approval_store
        self._parked_context_repo = parked_context_repo
        self._stagnation_detector = stagnation_detector
        self._auto_loop_config = auto_loop_config
        self._hybrid_loop_config = hybrid_loop_config
        self._compaction_callback = compaction_callback
        self._plan_execute_config = plan_execute_config
        self._approval_gate = self._make_approval_gate()
        if execution_loop is not None and (
            self._approval_gate is not None
            or self._stagnation_detector is not None
            or self._compaction_callback is not None
        ):
            logger.warning(
                APPROVAL_GATE_LOOP_WIRING_WARNING,
                note=(
                    "execution_loop provided externally -- approval_gate, "
                    "stagnation_detector, and compaction_callback will NOT "
                    "be wired automatically. Configure the loop with "
                    "approval_gate=, stagnation_detector=, and "
                    "compaction_callback= explicitly."
                ),
            )
        self._loop: ExecutionLoop = execution_loop or self._make_default_loop()
        self._tool_registry = tool_registry
        self._budget_enforcer = budget_enforcer
        if (checkpoint_repo is None) != (heartbeat_repo is None):
            msg = (
                "checkpoint_repo and heartbeat_repo must both be "
                "provided or both omitted"
            )
            raise ValueError(msg)
        self._checkpoint_repo = checkpoint_repo
        self._heartbeat_repo = heartbeat_repo
        self._checkpoint_config = checkpoint_config or CheckpointConfig()
        self._cost_tracker: CostTracker | None
        if budget_enforcer is not None:
            if (
                cost_tracker is not None
                and cost_tracker is not budget_enforcer.cost_tracker
            ):
                msg = (
                    "cost_tracker must match budget_enforcer.cost_tracker "
                    "when budget_enforcer is provided"
                )
                raise ValueError(msg)
            self._cost_tracker = budget_enforcer.cost_tracker
        else:
            self._cost_tracker = cost_tracker
        self._security_config = security_config
        self._task_engine = task_engine
        self._recovery_strategy = recovery_strategy
        self._shutdown_checker = shutdown_checker
        self._error_taxonomy_config = error_taxonomy_config
        self._coordinator = coordinator
        self._tool_invocation_tracker = tool_invocation_tracker
        self._memory_injection_strategy = memory_injection_strategy
        self._ontology_injection_strategy = ontology_injection_strategy
        self._procedural_memory_config = procedural_memory_config
        self._memory_backend = memory_backend
        self._distillation_capture_enabled = distillation_capture_enabled
        self._config_resolver = config_resolver
        self._personality_trim_notifier = personality_trim_notifier
        self._coordination_metrics_collector = coordination_metrics_collector
        self._procedural_proposer: ProceduralMemoryProposer | None = None
        if (
            procedural_memory_config is not None
            and procedural_memory_config.enabled
            and memory_backend is not None
        ):
            from synthorg.memory.procedural.proposer import (  # noqa: PLC0415
                ProceduralMemoryProposer,
            )

            self._procedural_proposer = ProceduralMemoryProposer(
                provider=provider,
                config=procedural_memory_config,
            )
        self._audit_log = audit_log if audit_log is not None else AuditLog()
        self._project_repo = project_repo
        logger.debug(
            EXECUTION_ENGINE_CREATED,
            loop_type=(
                "auto"
                if self._auto_loop_config is not None
                else self._loop.get_loop_type()
            ),
            has_tool_registry=self._tool_registry is not None,
            has_cost_tracker=self._cost_tracker is not None,
            has_budget_enforcer=self._budget_enforcer is not None,
            has_coordinator=self._coordinator is not None,
            has_compaction_callback=self._compaction_callback is not None,
            has_plan_execute_config=self._plan_execute_config is not None,
            has_hybrid_loop_config=self._hybrid_loop_config is not None,
            has_personality_trim_notifier=self._personality_trim_notifier is not None,
        )

    @property
    def coordinator(self) -> MultiAgentCoordinator | None:
        """Return the multi-agent coordinator, or ``None`` if not configured."""
        return self._coordinator

    async def coordinate(
        self,
        context: CoordinationContext,
    ) -> CoordinationResultWithAttribution:
        """Delegate to the multi-agent coordinator.

        Args:
            context: Coordination context with task, agents, and config.

        Returns:
            Coordination result with per-agent attribution data.

        Raises:
            ExecutionStateError: If no coordinator is configured.
            CoordinationPhaseError: When a critical phase fails.
        """
        if self._coordinator is None:
            msg = "No coordinator configured for multi-agent dispatch"
            logger.warning(
                EXECUTION_ENGINE_ERROR,
                error=msg,
            )
            raise ExecutionStateError(msg)
        return await self._coordinator.coordinate(context)

    async def run(  # noqa: PLR0913, C901
        self,
        *,
        identity: AgentIdentity,
        task: Task,
        completion_config: CompletionConfig | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        memory_messages: tuple[ChatMessage, ...] = (),
        timeout_seconds: float | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        resume_execution_id: str | None = None,
    ) -> AgentRunResult:
        """Execute an agent on a task.

        Raises:
            ExecutionStateError: If pre-flight validation fails.
            ValueError: If ``max_turns < 1`` or ``timeout_seconds <= 0``.
            MemoryError: Re-raised unconditionally (non-recoverable).
            RecursionError: Re-raised unconditionally (non-recoverable).
        """
        agent_id = str(identity.id)
        task_id = task.id

        validate_run_inputs(
            agent_id=agent_id,
            task_id=task_id,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
        )
        validate_agent(identity, agent_id)
        validate_task(task, agent_id, task_id)
        validate_task_metadata(task, agent_id, task_id)

        with correlation_scope(agent_id=agent_id, task_id=task_id):
            start = time.monotonic()
            ctx: AgentContext | None = None
            system_prompt: SystemPrompt | None = None
            provider: CompletionProvider = self._provider
            _project_budget: float = 0.0
            try:
                loop_mode = (
                    "auto"
                    if self._auto_loop_config is not None
                    else self._loop.get_loop_type()
                )
                logger.info(
                    EXECUTION_ENGINE_START,
                    agent_id=agent_id,
                    task_id=task_id,
                    loop_type=loop_mode,
                    max_turns=max_turns,
                )

                # Pre-flight budget enforcement + degradation
                if self._budget_enforcer:
                    preflight = await self._budget_enforcer.check_can_execute(
                        agent_id,
                        provider_name=identity.model.provider,
                    )
                    provider, identity = self._apply_degradation(
                        preflight,
                        identity,
                        provider,
                    )
                    identity = await self._budget_enforcer.resolve_model(
                        identity,
                    )

                # Project validation and project-level budget check
                if self._project_repo is not None:
                    _project_budget = await self._validate_project(
                        task=task,
                        agent_id=agent_id,
                        task_id=task_id,
                    )
                elif task.project:
                    logger.warning(
                        EXECUTION_PROJECT_VALIDATION_FAILED,
                        agent_id=agent_id,
                        task_id=task_id,
                        project_id=task.project,
                        reason="project_repo_not_configured",
                    )

                # Session replay: reconstruct context from event log
                # when resuming a previous (crashed) execution.
                # NOTE: CompanyConfig.session_replay_on_start gates this
                # at the middleware layer (Issue A). The engine trusts
                # that the caller only passes resume_execution_id when
                # the flag is enabled.
                replay_ctx: AgentContext | None = None
                if resume_execution_id is not None and self._event_reader is not None:
                    from synthorg.engine.session import Session  # noqa: PLC0415

                    replay_result = await Session.replay(
                        execution_id=resume_execution_id,
                        event_reader=self._event_reader,
                        identity=identity,
                        task=task,
                        max_turns=max_turns,
                    )
                    if (
                        replay_result.replay_completeness
                        < _REPLAY_LOW_COMPLETENESS_THRESHOLD
                    ):
                        logger.warning(
                            SESSION_REPLAY_LOW_COMPLETENESS,
                            execution_id=resume_execution_id,
                            replay_completeness=replay_result.replay_completeness,
                        )
                    replay_ctx = replay_result.context

                tool_invoker = self._make_tool_invoker(
                    identity,
                    task_id=task_id,
                    effective_autonomy=effective_autonomy,
                )
                ctx, system_prompt = await self._prepare_context(
                    identity=identity,
                    task=task,
                    agent_id=agent_id,
                    task_id=task_id,
                    max_turns=max_turns,
                    memory_messages=memory_messages,
                    tool_invoker=tool_invoker,
                    effective_autonomy=effective_autonomy,
                )
                if replay_ctx is not None:
                    # Merge replayed execution state into the prepared
                    # context so system prompt, memory messages, and
                    # task instruction are preserved.  Also restore
                    # the original execution lineage (ID + start time).
                    ctx = ctx.model_copy(
                        update={
                            "execution_id": replay_ctx.execution_id,
                            "started_at": replay_ctx.started_at,
                            "conversation": (
                                *ctx.conversation,
                                *replay_ctx.conversation,
                            ),
                            "accumulated_cost": replay_ctx.accumulated_cost,
                            "turn_count": replay_ctx.turn_count,
                            "task_execution": (
                                replay_ctx.task_execution or ctx.task_execution
                            ),
                        },
                    )
                return await self._execute(
                    identity=identity,
                    task=task,
                    agent_id=agent_id,
                    task_id=task_id,
                    completion_config=completion_config,
                    ctx=ctx,
                    system_prompt=system_prompt,
                    start=start,
                    timeout_seconds=timeout_seconds,
                    tool_invoker=tool_invoker,
                    effective_autonomy=effective_autonomy,
                    provider=provider,
                    project_budget=_project_budget,
                )
            except MemoryError, RecursionError:
                logger.exception(
                    EXECUTION_ENGINE_ERROR,
                    agent_id=agent_id,
                    task_id=task_id,
                    error="non-recoverable error in run()",
                )
                raise
            except ProjectNotFoundError, ProjectAgentNotMemberError:
                # ProjectBudgetExhaustedError (from _validate_project)
                # is a BudgetExhaustedError subclass -- intentionally
                # caught by the handler below, not here.
                raise
            except BudgetExhaustedError as exc:
                return self._handle_budget_error(
                    exc=exc,
                    identity=identity,
                    task=task,
                    agent_id=agent_id,
                    task_id=task_id,
                    duration_seconds=time.monotonic() - start,
                    ctx=ctx,
                    system_prompt=system_prompt,
                )
            except Exception as exc:
                return await self._handle_fatal_error(
                    exc=exc,
                    identity=identity,
                    task=task,
                    agent_id=agent_id,
                    task_id=task_id,
                    duration_seconds=time.monotonic() - start,
                    ctx=ctx,
                    system_prompt=system_prompt,
                    completion_config=completion_config,
                    effective_autonomy=effective_autonomy,
                    provider=provider,
                )

    async def _execute(  # noqa: PLR0913
        self,
        *,
        identity: AgentIdentity,
        task: Task,
        agent_id: str,
        task_id: str,
        completion_config: CompletionConfig | None,
        ctx: AgentContext,
        system_prompt: SystemPrompt,
        start: float,
        timeout_seconds: float | None = None,
        tool_invoker: ToolInvoker | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
        project_budget: float = 0.0,
    ) -> AgentRunResult:
        """Run execution loop, record costs, apply transitions, and build result."""
        budget_checker: BudgetChecker | None
        if self._budget_enforcer:
            budget_checker = await self._budget_enforcer.make_budget_checker(
                task,
                agent_id,
                project_id=task.project,
                project_budget=project_budget,
            )
        else:
            budget_checker = make_budget_checker(task)

        logger.debug(
            EXECUTION_ENGINE_PROMPT_BUILT,
            agent_id=agent_id,
            task_id=task_id,
            estimated_tokens=system_prompt.estimated_tokens,
        )

        loop = await self._resolve_loop(task, agent_id, task_id)

        execution_result = await self._run_loop_with_timeout(
            loop=loop,
            ctx=ctx,
            agent_id=agent_id,
            task_id=task_id,
            completion_config=completion_config,
            budget_checker=budget_checker,
            tool_invoker=tool_invoker,
            start=start,
            timeout_seconds=timeout_seconds,
            provider=provider or self._provider,
        )

        execution_result = await self._post_execution_pipeline(
            execution_result,
            identity,
            agent_id,
            task_id,
            completion_config=completion_config,
            effective_autonomy=effective_autonomy,
            provider=provider or self._provider,
            project_id=task.project,
        )

        return self._build_and_log_result(
            execution_result,
            system_prompt,
            start,
            agent_id,
            task_id,
        )

    async def _post_execution_pipeline(  # noqa: PLR0913
        self,
        execution_result: ExecutionResult,
        identity: AgentIdentity,
        agent_id: str,
        task_id: str,
        *,
        completion_config: CompletionConfig | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
        project_id: str | None = None,
    ) -> ExecutionResult:
        """Post-execution: costs, transitions, recovery, classify.

        Each transition is synced to TaskEngine incrementally
        (best-effort).  Classification and sync failures are logged,
        never fatal.
        """
        # Costs are recorded BEFORE recovery intentionally -- the
        # pre-recovery execution's cost (including partial turns that
        # led to the error) should be tracked.  The resumed execution
        # records its own costs inside _finalize_resume.
        await record_execution_costs(
            execution_result,
            identity,
            agent_id,
            task_id,
            tracker=self._cost_tracker,
            project_id=project_id,
        )
        execution_result = await apply_post_execution_transitions(
            execution_result,
            agent_id,
            task_id,
            self._task_engine,
            approval_store=self._approval_store,
        )
        recovery_result: RecoveryResult | None = None
        failed_result: ExecutionResult | None = None
        if execution_result.termination_reason == TerminationReason.ERROR:
            failed_result = execution_result
            pre_recovery_ctx = execution_result.context
            pre_recovery_status = (
                pre_recovery_ctx.task_execution.status
                if pre_recovery_ctx.task_execution is not None
                else None
            )
            execution_result, recovery_result = await self._apply_recovery(
                execution_result,
                identity,
                agent_id,
                task_id,
                completion_config=completion_config,
                effective_autonomy=effective_autonomy,
                provider=provider,
                project_id=project_id,
            )
            if recovery_result is not None:
                logger.info(
                    EXECUTION_RECOVERY_DIAGNOSIS,
                    agent_id=agent_id,
                    task_id=task_id,
                    failure_category=recovery_result.failure_category.value,
                    criteria_failed_count=len(recovery_result.criteria_failed),
                )
            # Sync post-recovery status to TaskEngine (typically FAILED,
            # depends on recovery strategy).
            ctx = execution_result.context
            if (
                ctx.task_execution is not None
                and pre_recovery_status is not None
                and ctx.task_execution.status != pre_recovery_status
            ):
                logger.info(
                    EXECUTION_ENGINE_TASK_TRANSITION,
                    agent_id=agent_id,
                    task_id=task_id,
                    from_status=pre_recovery_status.value,
                    to_status=ctx.task_execution.status.value,
                )
                # Embed the failure category in the transition reason so
                # the downstream task router / reassignment selector can
                # read it from the task's status history and make a more
                # informed decision (e.g. route TOOL_FAILURE retries to
                # an agent with different tool access, BUDGET_EXCEEDED to
                # a cheaper tier, etc.).  recovery_result is guaranteed
                # non-None here: reaching this block requires the status
                # to have changed, which only happens when a recovery
                # strategy ran and produced a result.
                assert recovery_result is not None  # noqa: S101
                category = recovery_result.failure_category.value
                # When the category is QUALITY_GATE_FAILED (or any other
                # category that collected criteria_failed), preserve a
                # sanitized summary of the failing criteria in the
                # transition reason so downstream routing/history does
                # not lose them.  Capped at the first ~5 criteria and
                # each sanitized via sanitize_message() to strip
                # paths/URLs/injection markers before the string hits
                # the task status history.
                criteria_suffix = ""
                if recovery_result.criteria_failed:
                    capped = recovery_result.criteria_failed[
                        :_TRANSITION_REASON_CRITERIA_CAP
                    ]
                    sanitized = "; ".join(sanitize_message(c) for c in capped)
                    overflow = (
                        len(recovery_result.criteria_failed)
                        - _TRANSITION_REASON_CRITERIA_CAP
                    )
                    more = f" +{overflow} more" if overflow > 0 else ""
                    criteria_suffix = f", unmet_criteria={sanitized}{more}"
                await sync_to_task_engine(
                    self._task_engine,
                    target_status=ctx.task_execution.status,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason=(
                        f"Post-recovery status: {ctx.task_execution.status.value} "
                        f"(failure_category={category}{criteria_suffix})"
                    ),
                )
        # Clean up checkpoints and heartbeat on non-ERROR exits.
        # The ERROR path is handled inside _finalize_resume (resume)
        # and _delegate_to_fallback (fallback).  Normal completions
        # (COMPLETED, MAX_TURNS, BUDGET_EXHAUSTED, SHUTDOWN, PARKED, STAGNATION)
        # bypass recovery entirely, so cleanup runs here.
        if execution_result.termination_reason != TerminationReason.ERROR:
            exec_id = execution_result.context.execution_id
            if self._recovery_strategy is not None:
                await self._recovery_strategy.finalize(exec_id)
            await cleanup_checkpoint_artifacts(
                self._checkpoint_repo,
                self._heartbeat_repo,
                exec_id,
            )
        # Classification is non-critical -- never destroys a result.
        if self._error_taxonomy_config is not None:
            try:
                await classify_execution_errors(
                    execution_result,
                    agent_id,
                    task_id,
                    config=self._error_taxonomy_config,
                )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    EXECUTION_ENGINE_ERROR,
                    agent_id=agent_id,
                    task_id=task_id,
                    error=f"classification failed: {type(exc).__name__}: {exc}",
                    exc_info=True,
                )
        await self._try_procedural_memory(
            failed_result or execution_result,
            recovery_result,
            agent_id,
            task_id,
        )
        await self._try_capture_distillation(
            execution_result,
            agent_id,
            task_id,
        )
        await self._try_collect_coordination_metrics(
            execution_result,
            agent_id,
            task_id,
        )
        return execution_result

    async def _try_capture_distillation(
        self,
        execution_result: ExecutionResult,
        agent_id: str,
        task_id: str,
    ) -> None:
        """Capture trajectory distillation at task completion (non-critical).

        Delegates to :func:`post_execution.try_capture_distillation`.
        """
        from synthorg.engine.post_execution import (  # noqa: PLC0415
            try_capture_distillation,
        )

        await try_capture_distillation(
            execution_result,
            agent_id,
            task_id,
            distillation_capture_enabled=self._distillation_capture_enabled,
            memory_backend=self._memory_backend,
        )

    async def _try_collect_coordination_metrics(
        self,
        execution_result: ExecutionResult,
        agent_id: str,
        task_id: str,
    ) -> None:
        """Collect coordination metrics post-execution (non-critical, never fatal).

        Mirrors the ``_try_capture_distillation`` best-effort pattern.
        When ``coordination_metrics_collector`` is not configured, this
        is a no-op.
        """
        if self._coordination_metrics_collector is None:
            return
        try:
            await self._coordination_metrics_collector.collect(
                execution_result=execution_result,
                agent_id=agent_id,
                task_id=task_id,
                is_multi_agent=False,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                EXECUTION_ENGINE_ERROR,
                agent_id=agent_id,
                task_id=task_id,
                error=f"coordination metrics failed: {type(exc).__name__}: {exc}",
                exc_info=True,
            )

    async def _try_procedural_memory(
        self,
        execution_result: ExecutionResult,
        recovery_result: RecoveryResult | None,
        agent_id: str,
        task_id: str,
    ) -> None:
        """Run procedural memory pipeline (non-critical, never fatal).

        Delegates to :func:`post_execution.try_procedural_memory`.
        """
        from synthorg.engine.post_execution import (  # noqa: PLC0415
            try_procedural_memory,
        )

        await try_procedural_memory(
            execution_result,
            recovery_result,
            agent_id,
            task_id,
            procedural_proposer=self._procedural_proposer,
            memory_backend=self._memory_backend,
            procedural_memory_config=self._procedural_memory_config,
        )

    def _build_and_log_result(
        self,
        execution_result: ExecutionResult,
        system_prompt: SystemPrompt,
        start: float,
        agent_id: str,
        task_id: str,
    ) -> AgentRunResult:
        """Build ``AgentRunResult`` and log completion metrics."""
        duration = time.monotonic() - start
        result = AgentRunResult(
            execution_result=execution_result,
            system_prompt=system_prompt,
            duration_seconds=duration,
            agent_id=agent_id,
            task_id=task_id,
        )
        try:
            self._log_completion(result, agent_id, task_id, duration)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                EXECUTION_ENGINE_ERROR,
                agent_id=agent_id,
                task_id=task_id,
                error="Completion logging failed",
            )
        return result

    def _make_loop_with_callback(
        self,
        loop: ExecutionLoop,
        agent_id: str,
        task_id: str,
    ) -> ExecutionLoop:
        """Return the execution loop with a checkpoint callback if configured."""
        return make_loop_with_callback(
            loop,
            self._checkpoint_repo,
            self._heartbeat_repo,
            self._checkpoint_config,
            agent_id,
            task_id,
        )

    async def _run_loop_with_timeout(  # noqa: PLR0913
        self,
        *,
        loop: ExecutionLoop,
        ctx: AgentContext,
        agent_id: str,
        task_id: str,
        completion_config: CompletionConfig | None,
        budget_checker: BudgetChecker | None,
        tool_invoker: ToolInvoker | None,
        start: float,
        timeout_seconds: float | None,
        provider: CompletionProvider | None = None,
    ) -> ExecutionResult:
        """Execute the loop, using ``asyncio.wait`` for timeout control.

        Uses ``asyncio.wait`` instead of ``asyncio.wait_for`` so that
        ``TimeoutError`` raised inside the loop propagates normally
        and is not conflated with the engine's wall-clock deadline.
        """
        wrapped_loop = self._make_loop_with_callback(loop, agent_id, task_id)
        coro = wrapped_loop.execute(
            context=ctx,
            provider=provider or self._provider,
            tool_invoker=tool_invoker,
            budget_checker=budget_checker,
            shutdown_checker=self._shutdown_checker,
            completion_config=completion_config,
        )
        if timeout_seconds is None:
            return await coro

        loop_task = asyncio.create_task(coro)
        _done, pending = await asyncio.wait(
            {loop_task},
            timeout=timeout_seconds,
        )
        if not pending:
            return loop_task.result()

        duration = time.monotonic() - start
        error_msg = (
            f"Wall-clock timeout after {duration:.1f}s (limit: {timeout_seconds}s)"
        )
        logger.warning(
            EXECUTION_ENGINE_TIMEOUT,
            agent_id=agent_id,
            task_id=task_id,
            duration_seconds=duration,
            timeout_seconds=timeout_seconds,
        )
        loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop_task
        return ExecutionResult(
            context=ctx,
            termination_reason=TerminationReason.ERROR,
            error_message=error_msg,
        )

    # ── Setup ────────────────────────────────────────────────────

    async def _prepare_context(  # noqa: PLR0913
        self,
        *,
        identity: AgentIdentity,
        task: Task,
        agent_id: str,
        task_id: str,
        max_turns: int,
        memory_messages: tuple[ChatMessage, ...],
        tool_invoker: ToolInvoker | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
    ) -> tuple[AgentContext, SystemPrompt]:
        """Build system prompt and prepare execution context."""
        l1_summaries = tool_invoker.get_l1_summaries() if tool_invoker else ()
        cur_code = (
            self._budget_enforcer.currency
            if self._budget_enforcer is not None
            else DEFAULT_CURRENCY
        )
        trimming_enabled = True
        tokens_override: int | None = None
        if self._config_resolver is not None:
            try:
                resolved_enabled = await self._config_resolver.get_bool(
                    "engine",
                    "personality_trimming_enabled",
                )
                resolved_override = await self._config_resolver.get_int(
                    "engine",
                    "personality_max_tokens_override",
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    EXECUTION_ENGINE_ERROR,
                    agent_id=agent_id,
                    task_id=task_id,
                    note="failed to read ENGINE settings, using defaults",
                    failed_keys=(
                        "personality_trimming_enabled",
                        "personality_max_tokens_override",
                    ),
                    fallback_trimming_enabled=True,
                    fallback_tokens_override=None,
                    exc_info=True,
                )
            else:
                trimming_enabled = resolved_enabled
                if resolved_override > 0:
                    tokens_override = resolved_override
        system_prompt = build_system_prompt(
            agent=identity,
            task=task,
            l1_summaries=l1_summaries,
            effective_autonomy=effective_autonomy,
            currency=cur_code,
            model_tier=identity.model.model_tier,
            personality_trimming_enabled=trimming_enabled,
            max_personality_tokens_override=tokens_override,
        )

        if system_prompt.personality_trim_info is not None:
            ti = system_prompt.personality_trim_info
            trim_payload: PersonalityTrimPayload = {
                "agent_id": agent_id,
                "agent_name": identity.name,
                "task_id": task_id,
                "before_tokens": ti.before_tokens,
                "after_tokens": ti.after_tokens,
                "max_tokens": ti.max_tokens,
                "trim_tier": ti.trim_tier,  # type: ignore[typeddict-item]  # validated 1|2|3 by PersonalityTrimInfo
                "budget_met": ti.budget_met,
            }
            logger.info(PROMPT_PERSONALITY_TRIMMED, **trim_payload)
            await self._maybe_notify_personality_trim(trim_payload)

        ctx = AgentContext.from_identity(
            identity,
            task=task,
            max_turns=max_turns,
        )
        ctx = ctx.with_message(
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt.content),
        )
        for msg in memory_messages:
            ctx = ctx.with_message(msg)
        ctx = ctx.with_message(
            ChatMessage(
                role=MessageRole.USER,
                content=format_task_instruction(task, currency=cur_code),
            ),
        )

        ctx = await transition_task_if_needed(
            ctx,
            agent_id,
            task_id,
            self._task_engine,
        )
        return ctx, system_prompt

    async def _maybe_notify_personality_trim(
        self,
        payload: PersonalityTrimPayload,
    ) -> None:
        """Publish a personality-trim WebSocket notification, best-effort.

        Reads the ``engine.personality_trimming_notify`` setting and, when
        enabled and a ``personality_trim_notifier`` callback is wired, invokes
        the callback with the trim payload.

        Emits ``PROMPT_PERSONALITY_NOTIFY_FAILED`` on three paths: (1) the
        setting read raised an exception (``reason="failed to read
        personality_trimming_notify setting; fail-open with default
        notify_enabled=True"``), in which case the method proceeds with the
        built-in default and still invokes the notifier; (2) the notifier
        callback exceeded its 2-second execution budget
        (``reason="notifier callback timed out (>2s)"``); (3) the notifier
        callback raised (``reason="notifier callback raised"``).  In all
        cases :class:`MemoryError`, :class:`RecursionError`, and
        :class:`asyncio.CancelledError` propagate per the best-effort
        publisher contract -- notification never silently blocks task
        execution.  The 2-second timeout guards against a slow or hung
        external runner stalling the main execution path.

        When ``config_resolver`` is ``None``, the setting is treated as
        enabled (``notify_enabled=True``) so the callback fires unconditionally.

        Args:
            payload: The trim info dict logged via ``PROMPT_PERSONALITY_TRIMMED``.
                See :class:`PersonalityTrimPayload` for the key contract.
        """
        if self._personality_trim_notifier is None:
            return
        notify_enabled = await self._read_notify_enabled(payload)
        if not notify_enabled:
            return
        agent_id = payload["agent_id"]
        agent_name = payload["agent_name"]
        task_id = payload["task_id"]
        trim_tier = payload["trim_tier"]
        # Bound the notifier call so a slow or hung implementation cannot
        # stall ``run()``.  2 seconds is comfortably above any legitimate
        # fire-and-forget enqueue and short enough that a real stall
        # surfaces loudly via the warning log below.
        try:
            async with asyncio.timeout(2.0):
                await self._personality_trim_notifier(payload)
        except TimeoutError:
            logger.warning(
                PROMPT_PERSONALITY_NOTIFY_FAILED,
                agent_id=agent_id,
                agent_name=agent_name,
                task_id=task_id,
                trim_tier=trim_tier,
                reason="notifier callback timed out (>2s)",
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                PROMPT_PERSONALITY_NOTIFY_FAILED,
                agent_id=agent_id,
                agent_name=agent_name,
                task_id=task_id,
                trim_tier=trim_tier,
                reason="notifier callback raised",
                exc_info=True,
            )

    async def _read_notify_enabled(
        self,
        payload: PersonalityTrimPayload,
    ) -> bool:
        """Read the ``personality_trimming_notify`` setting, fail-open.

        Returns ``True`` when the resolver is unavailable or raises,
        so a transient failure never silently disables notifications
        the operator enabled.
        """
        if self._config_resolver is None:
            return True
        try:
            return await self._config_resolver.get_bool(
                "engine",
                "personality_trimming_notify",
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                PROMPT_PERSONALITY_NOTIFY_FAILED,
                agent_id=payload["agent_id"],
                agent_name=payload["agent_name"],
                task_id=payload["task_id"],
                trim_tier=payload["trim_tier"],
                reason=(
                    "failed to read personality_trimming_notify setting;"
                    " fail-open with default notify_enabled=True"
                ),
                exc_info=True,
            )
            return True

    async def _validate_project(
        self,
        *,
        task: Task,
        agent_id: str,
        task_id: str,
    ) -> float:
        """Validate project existence and agent membership.

        Returns the project budget (0.0 when no project-level budget
        or when the task has no project assigned).

        Raises:
            ProjectNotFoundError: When the project does not exist.
            ProjectAgentNotMemberError: When the agent is not in the
                project team (non-empty team only).
        """
        if not task.project:
            return 0.0
        project = await self._project_repo.get(task.project)  # type: ignore[union-attr]
        if project is None:
            logger.warning(
                EXECUTION_PROJECT_VALIDATION_FAILED,
                agent_id=agent_id,
                task_id=task_id,
                project_id=task.project,
                reason="project_not_found",
            )
            raise ProjectNotFoundError(project_id=task.project)
        if project.team and agent_id not in project.team:
            logger.warning(
                EXECUTION_PROJECT_VALIDATION_FAILED,
                agent_id=agent_id,
                task_id=task_id,
                project_id=task.project,
                reason="agent_not_in_team",
            )
            raise ProjectAgentNotMemberError(
                project_id=task.project,
                agent_id=agent_id,
            )
        if self._budget_enforcer is not None and project.budget > 0:
            await self._budget_enforcer.check_project_budget(
                project_id=project.id,
                project_budget=project.budget,
            )
        return project.budget

    # ── Helpers ──────────────────────────────────────────────────

    async def _apply_recovery(  # noqa: PLR0913
        self,
        execution_result: ExecutionResult,
        identity: AgentIdentity,
        agent_id: str,
        task_id: str,
        *,
        completion_config: CompletionConfig | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
        project_id: str | None = None,
    ) -> tuple[ExecutionResult, RecoveryResult | None]:
        """Invoke the configured recovery strategy on error outcomes.

        The default strategy transitions the task to FAILED; checkpoint
        recovery may resume from a persisted checkpoint.  If no strategy
        is set or no task execution exists, returns the result unchanged.
        Recovery failures are logged but never block the error result.

        Returns:
            Tuple of (updated execution result, recovery result or None).
        """
        if self._recovery_strategy is None:
            return execution_result, None
        ctx = execution_result.context
        if ctx.task_execution is None:
            return execution_result, None

        error_msg = execution_result.error_message or "Unknown error"
        try:
            recovery_result = await self._recovery_strategy.recover(
                task_execution=ctx.task_execution,
                error_message=error_msg,
                context=ctx,
            )

            # Checkpoint resume path
            if recovery_result.can_resume:
                resumed = await self._resume_from_checkpoint(
                    recovery_result,
                    identity,
                    ctx.task_execution.task,
                    agent_id,
                    task_id,
                    completion_config=completion_config,
                    effective_autonomy=effective_autonomy,
                    provider=provider,
                    project_id=project_id,
                )
                return resumed, recovery_result

            updated_ctx = ctx.model_copy(
                update={"task_execution": recovery_result.task_execution},
            )
            updated_result = execution_result.model_copy(
                update={"context": updated_ctx},
            )
            return updated_result, recovery_result  # noqa: TRY300
        except MemoryError, RecursionError:
            raise
        except ProjectNotFoundError, ProjectAgentNotMemberError:
            # Re-validate raised from _resume_from_checkpoint;
            # let run()'s dedicated project-error handler deal with it.
            raise
        except BudgetExhaustedError:
            # Includes ProjectBudgetExhaustedError from re-validation;
            # let run()'s budget-error handler deal with it.
            raise
        except Exception as exc:
            logger.exception(
                EXECUTION_RECOVERY_FAILED,
                agent_id=agent_id,
                task_id=task_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            return execution_result, None

    def _validate_checkpoint_json(
        self,
        recovery_result: RecoveryResult,
        agent_id: str,
        task_id: str,
    ) -> str:
        """Return checkpoint JSON or raise if unexpectedly absent."""
        if recovery_result.checkpoint_context_json is None:
            logger.error(
                EXECUTION_RESUME_FAILED,
                agent_id=agent_id,
                task_id=task_id,
                error="checkpoint_context_json is None but can_resume was True",
            )
            msg = "checkpoint_context_json is None but can_resume was True"
            raise RuntimeError(msg)
        return recovery_result.checkpoint_context_json

    async def _resume_from_checkpoint(  # noqa: PLR0913
        self,
        recovery_result: RecoveryResult,
        identity: AgentIdentity,
        task: Task,
        agent_id: str,
        task_id: str,
        *,
        completion_config: CompletionConfig | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
        project_id: str | None = None,
    ) -> ExecutionResult:
        """Resume execution from a checkpoint.

        Policy: resumed executions run without a wall-clock timeout.
        The loop's per-turn budget and max_turns still constrain
        execution.

        Re-validates project membership and budget before resuming
        to prevent stale checkpoint runs after team/budget changes.
        """
        # Re-validate project context (team may have changed since crash)
        project_budget = 0.0
        if self._project_repo is not None:
            project_budget = await self._validate_project(
                task=task,
                agent_id=agent_id,
                task_id=task_id,
            )
            project_id = task.project

        checkpoint_json = self._validate_checkpoint_json(
            recovery_result,
            agent_id,
            task_id,
        )
        logger.info(
            EXECUTION_RESUME_START,
            agent_id=agent_id,
            task_id=task_id,
            resume_attempt=recovery_result.resume_attempt,
        )

        try:
            result, execution_id = await self._reconstruct_and_run_resume(
                checkpoint_json,
                recovery_result.error_message,
                agent_id,
                task_id,
                failure_category=recovery_result.failure_category,
                criteria_failed=recovery_result.criteria_failed,
                completion_config=completion_config,
                effective_autonomy=effective_autonomy,
                provider=provider,
                project_id=project_id,
                project_budget=project_budget,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.exception(
                EXECUTION_RESUME_FAILED,
                agent_id=agent_id,
                task_id=task_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        else:
            return await self._finalize_resume(
                result,
                identity,
                execution_id,
                agent_id,
                task_id,
                project_id=project_id,
            )

    async def _reconstruct_and_run_resume(  # noqa: PLR0913
        self,
        checkpoint_context_json: str,
        error_message: str,
        agent_id: str,
        task_id: str,
        *,
        failure_category: FailureCategory,
        criteria_failed: tuple[str, ...] = (),
        completion_config: CompletionConfig | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
        project_id: str | None = None,
        project_budget: float = 0.0,
    ) -> tuple[ExecutionResult, str]:
        """Deserialize checkpoint context and run the resumed loop.

        Returns:
            A ``(result, execution_id)`` tuple so the caller can
            call ``_finalize_resume`` with the execution identifier.
        """
        checkpoint_ctx = deserialize_and_reconcile(
            checkpoint_context_json,
            error_message,
            agent_id,
            task_id,
            failure_category=failure_category,
            criteria_failed=criteria_failed,
        )
        result = await self._execute_resumed_loop(
            checkpoint_ctx,
            agent_id,
            task_id,
            completion_config=completion_config,
            effective_autonomy=effective_autonomy,
            provider=provider,
            project_id=project_id,
            project_budget=project_budget,
        )
        return result, checkpoint_ctx.execution_id

    async def _execute_resumed_loop(  # noqa: PLR0913
        self,
        checkpoint_ctx: AgentContext,
        agent_id: str,
        task_id: str,
        *,
        completion_config: CompletionConfig | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
        project_id: str | None = None,
        project_budget: float = 0.0,
    ) -> ExecutionResult:
        """Run the execution loop on a reconstituted checkpoint context."""
        budget_checker: BudgetChecker | None
        if checkpoint_ctx.task_execution is None:
            budget_checker = None
        elif self._budget_enforcer:
            budget_checker = await self._budget_enforcer.make_budget_checker(
                checkpoint_ctx.task_execution.task,
                agent_id,
                project_id=project_id,
                project_budget=project_budget,
            )
        else:
            budget_checker = make_budget_checker(
                checkpoint_ctx.task_execution.task,
            )

        base_loop = self._loop
        if checkpoint_ctx.task_execution is not None:
            base_loop = await self._resolve_loop(
                checkpoint_ctx.task_execution.task,
                agent_id,
                task_id,
            )
        loop = self._make_loop_with_callback(base_loop, agent_id, task_id)
        return await loop.execute(
            context=checkpoint_ctx,
            provider=provider or self._provider,
            tool_invoker=self._make_tool_invoker(
                checkpoint_ctx.identity,
                task_id=task_id,
                effective_autonomy=effective_autonomy,
            ),
            budget_checker=budget_checker,
            shutdown_checker=self._shutdown_checker,
            completion_config=completion_config,
        )

    async def _finalize_resume(  # noqa: PLR0913
        self,
        result: ExecutionResult,
        identity: AgentIdentity,
        execution_id: str,
        agent_id: str,
        task_id: str,
        *,
        project_id: str | None = None,
    ) -> ExecutionResult:
        """Record costs, apply transitions, and clean up after resume.

        The resumed execution bypasses the normal pipeline's
        ``record_execution_costs`` and ``apply_post_execution_transitions``
        (those ran on the pre-crash result).  This method applies them
        to the resumed result so costs are tracked and task state is
        correctly transitioned.
        """
        await record_execution_costs(
            result,
            identity,
            agent_id,
            task_id,
            tracker=self._cost_tracker,
            project_id=project_id,
        )
        # Deliberately omit approval_store: the pre-crash execution
        # already created review approval items if the task reached
        # IN_REVIEW.  Passing approval_store here would create
        # duplicates because approval IDs are random UUIDs.
        result = await apply_post_execution_transitions(
            result,
            agent_id,
            task_id,
            self._task_engine,
        )
        logger.info(
            EXECUTION_RESUME_COMPLETE,
            agent_id=agent_id,
            task_id=task_id,
            termination_reason=result.termination_reason.value,
        )
        if result.termination_reason != TerminationReason.ERROR:
            if self._recovery_strategy is not None:
                await self._recovery_strategy.finalize(execution_id)
            await cleanup_checkpoint_artifacts(
                self._checkpoint_repo,
                self._heartbeat_repo,
                execution_id,
            )
        return result

    def _make_approval_gate(self) -> ApprovalGate | None:
        """Build an ApprovalGate if an approval store is configured.

        Returns ``None`` when no approval store is available -- the
        execution loop skips approval-gate checks in that case.
        """
        if self._approval_store is None:
            return None

        from synthorg.security.timeout.park_service import (  # noqa: PLC0415
            ParkService,
        )

        return ApprovalGate(
            park_service=ParkService(),
            parked_context_repo=self._parked_context_repo,
            event_hub=self._event_stream_hub,
            interrupt_store=self._interrupt_store,
        )

    def _make_default_loop(self) -> ReactLoop:
        """Build the default ReactLoop with approval gate and stagnation detector."""
        return ReactLoop(
            approval_gate=self._approval_gate,
            stagnation_detector=self._stagnation_detector,
            compaction_callback=self._compaction_callback,
        )

    async def _resolve_loop(
        self,
        task: Task,
        agent_id: str = "",
        task_id: str = "",
    ) -> ExecutionLoop:
        """Select the execution loop for a task.

        When ``auto_loop_config`` is set, selects the loop based on
        task complexity and optional budget state.  Otherwise returns
        the statically configured loop (``self._loop``).
        """
        if self._auto_loop_config is None:
            return self._loop

        cfg = self._auto_loop_config
        # Dry-run without budget and without hybrid fallback to see the
        # raw rule result.  Only query budget when "hybrid" is the raw
        # match (budget downgrade applies before hybrid fallback).
        preliminary = select_loop_type(
            complexity=task.estimated_complexity,
            rules=cfg.rules,
            budget_utilization_pct=None,
            budget_tight_threshold=cfg.budget_tight_threshold,
            hybrid_fallback=None,
            default_loop_type=cfg.default_loop_type,
        )

        budget_utilization_pct: float | None = None
        if preliminary == "hybrid" and self._budget_enforcer is not None:
            budget_utilization_pct = (
                await self._budget_enforcer.get_budget_utilization_pct()
            )
            if budget_utilization_pct is None:
                logger.debug(
                    EXECUTION_LOOP_BUDGET_UNAVAILABLE,
                    note="budget utilization unknown; skipping budget-aware downgrade",
                )

        loop_type = select_loop_type(
            complexity=task.estimated_complexity,
            rules=cfg.rules,
            budget_utilization_pct=budget_utilization_pct,
            budget_tight_threshold=cfg.budget_tight_threshold,
            hybrid_fallback=cfg.hybrid_fallback,
            default_loop_type=cfg.default_loop_type,
        )

        logger.info(
            EXECUTION_LOOP_AUTO_SELECTED,
            agent_id=agent_id,
            task_id=task_id,
            complexity=task.estimated_complexity.value,
            selected_loop=loop_type,
            budget_utilization_pct=budget_utilization_pct,
        )

        return build_execution_loop(
            loop_type,
            approval_gate=self._approval_gate,
            stagnation_detector=self._stagnation_detector,
            compaction_callback=self._compaction_callback,
            plan_execute_config=self._plan_execute_config,
            hybrid_loop_config=self._hybrid_loop_config,
        )

    def _make_security_interceptor(
        self,
        effective_autonomy: EffectiveAutonomy | None = None,
    ) -> SecurityInterceptionStrategy | None:
        """Build the SecOps security interceptor if configured."""
        return make_security_interceptor(
            self._security_config,
            self._audit_log,
            approval_store=self._approval_store,
            effective_autonomy=effective_autonomy,
            provider_registry=self._provider_registry,
            provider_configs=self._provider_configs,
            model_resolver=self._model_resolver,
        )

    def _make_tool_invoker(
        self,
        identity: AgentIdentity,
        task_id: str | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
    ) -> ToolInvoker | None:
        """Create a ToolInvoker with permission checking and security."""
        if self._tool_registry is None:
            return None

        registry = registry_with_approval_tool(
            self._tool_registry,
            self._approval_store,
            identity,
            task_id=task_id,
        )
        if self._memory_injection_strategy is not None:
            from synthorg.memory.tools import (  # noqa: PLC0415
                registry_with_memory_tools,
            )

            registry = registry_with_memory_tools(
                registry,
                self._memory_injection_strategy,
                agent_id=str(identity.id),
            )
        if self._ontology_injection_strategy is not None:
            tool_defs = self._ontology_injection_strategy.get_tool_definitions()
            if tool_defs:
                from synthorg.ontology.injection.hybrid import (  # noqa: PLC0415
                    HybridInjectionStrategy,
                )
                from synthorg.ontology.injection.tool import (  # noqa: PLC0415
                    ToolBasedInjectionStrategy,
                )
                from synthorg.tools.registry import (  # noqa: PLC0415
                    ToolRegistry as _ToolRegistry,
                )

                if isinstance(
                    self._ontology_injection_strategy,
                    ToolBasedInjectionStrategy | HybridInjectionStrategy,
                ):
                    import copy as _copy  # noqa: PLC0415

                    ontology_tool = _copy.deepcopy(
                        self._ontology_injection_strategy.tool,
                    )
                    existing = [_copy.deepcopy(t) for t in registry.all_tools()]
                    registry = _ToolRegistry([*existing, ontology_tool])
        # Add discovery tools with a deferred manager that binds
        # to the invoker after construction.
        from synthorg.tools.discovery import (  # noqa: PLC0415
            DeferredDisclosureManager,
            build_discovery_tools,
        )
        from synthorg.tools.registry import (  # noqa: PLC0415
            ToolRegistry as _ToolRegistry2,
        )

        deferred = DeferredDisclosureManager()
        discovery = build_discovery_tools(deferred)
        existing = list(registry.all_tools())
        registry = _ToolRegistry2([*existing, *discovery])

        checker = ToolPermissionChecker.from_permissions(identity.tools)
        interceptor = self._make_security_interceptor(effective_autonomy)
        invoker = ToolInvoker(
            registry,
            permission_checker=checker,
            security_interceptor=interceptor,
            agent_id=str(identity.id),
            task_id=task_id,
            invocation_tracker=self._tool_invocation_tracker,
        )
        deferred.bind(invoker)
        return invoker

    def _log_completion(
        self,
        result: AgentRunResult,
        agent_id: str,
        task_id: str,
        duration: float,
    ) -> None:
        """Log structured completion event and proxy overhead metrics."""
        accumulated = result.execution_result.context.accumulated_cost
        logger.info(
            EXECUTION_ENGINE_COMPLETE,
            agent_id=agent_id,
            task_id=task_id,
            termination_reason=result.termination_reason.value,
            total_turns=result.total_turns,
            total_tokens=accumulated.total_tokens,
            duration_seconds=duration,
            cost=result.total_cost,
        )

        metrics = TaskCompletionMetrics.from_run_result(result)
        logger.info(
            EXECUTION_ENGINE_TASK_METRICS,
            agent_id=agent_id,
            task_id=task_id,
            termination_reason=result.termination_reason.value,
            turns_per_task=metrics.turns_per_task,
            tokens_per_task=metrics.tokens_per_task,
            cost_per_task=metrics.cost_per_task,
            duration_seconds=metrics.duration_seconds,
            prompt_tokens=metrics.prompt_tokens,
            prompt_token_ratio=metrics.prompt_token_ratio,
        )

        if metrics.prompt_token_ratio > _PROMPT_TOKEN_RATIO_THRESHOLD:
            logger.warning(
                PROMPT_TOKEN_RATIO_HIGH,
                agent_id=agent_id,
                task_id=task_id,
                prompt_token_ratio=metrics.prompt_token_ratio,
                prompt_tokens=metrics.prompt_tokens,
                total_tokens=metrics.tokens_per_task,
            )

    def _apply_degradation(
        self,
        preflight: PreFlightResult,
        identity: AgentIdentity,
        provider: CompletionProvider,
    ) -> tuple[CompletionProvider, AgentIdentity]:
        """Apply degradation result: swap provider if FALLBACK selected.

        Note:
            FALLBACK assumes the fallback provider supports the same
            ``model_id`` as the original.  If fallback providers serve
            different models, a model mapping in ``DegradationConfig``
            or ``ModelResolver`` integration is needed.
        """
        effective = preflight.effective_provider
        if effective is None or effective == identity.model.provider:
            return provider, identity

        # FALLBACK: need a different provider driver
        original = identity.model.provider
        if self._provider_registry is None:
            logger.warning(
                DEGRADATION_PROVIDER_SWAPPED,
                original_provider=original,
                fallback_provider=effective,
                error="no provider_registry available",
                result="failed",
            )
            msg = (
                f"FALLBACK selected provider {effective!r} "
                f"but no provider_registry available"
            )
            raise QuotaExhaustedError(
                msg,
                provider_name=original,
                degradation_action=DegradationAction.FALLBACK,
            )

        try:
            new_provider = self._provider_registry.get(effective)
        except DriverNotRegisteredError as exc:
            logger.warning(
                DEGRADATION_PROVIDER_SWAPPED,
                original_provider=original,
                fallback_provider=effective,
                error=str(exc),
                result="failed",
            )
            msg = f"Fallback provider {effective!r} not found in registry"
            raise QuotaExhaustedError(
                msg,
                provider_name=original,
                degradation_action=DegradationAction.FALLBACK,
            ) from exc

        logger.info(
            DEGRADATION_PROVIDER_SWAPPED,
            original_provider=identity.model.provider,
            fallback_provider=effective,
            result="success",
        )
        new_identity = identity.model_copy(
            update={
                "model": identity.model.model_copy(
                    update={"provider": effective},
                ),
            },
        )
        return new_provider, new_identity

    def _handle_budget_error(  # noqa: PLR0913
        self,
        *,
        exc: BudgetExhaustedError,
        identity: AgentIdentity,
        task: Task,
        agent_id: str,
        task_id: str,
        duration_seconds: float,
        ctx: AgentContext | None = None,
        system_prompt: SystemPrompt | None = None,
    ) -> AgentRunResult:
        """Build a BUDGET_EXHAUSTED result (no recovery -- controlled stop)."""
        logger.warning(
            EXECUTION_ENGINE_BUDGET_STOPPED,
            agent_id=agent_id,
            task_id=task_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        try:
            error_ctx = ctx or AgentContext.from_identity(identity, task=task)
            budget_result = ExecutionResult(
                context=error_ctx,
                termination_reason=TerminationReason.BUDGET_EXHAUSTED,
            )
            error_prompt = build_error_prompt(
                identity,
                agent_id,
                system_prompt,
            )
            return AgentRunResult(
                execution_result=budget_result,
                system_prompt=error_prompt,
                duration_seconds=duration_seconds,
                agent_id=agent_id,
                task_id=task_id,
            )
        except MemoryError, RecursionError:
            logger.exception(
                EXECUTION_ENGINE_ERROR,
                agent_id=agent_id,
                task_id=task_id,
                error="non-recoverable error while building budget-exhausted result",
            )
            raise
        except Exception as build_exc:
            logger.exception(
                EXECUTION_ENGINE_ERROR,
                agent_id=agent_id,
                task_id=task_id,
                error=f"Failed to build budget-exhausted result: {build_exc}",
            )
            exc.add_note(
                f"Secondary failure while building budget-exhausted "
                f"result: {type(build_exc).__name__}: {build_exc}",
            )
            raise exc from None

    async def _handle_fatal_error(  # noqa: PLR0913
        self,
        *,
        exc: Exception,
        identity: AgentIdentity,
        task: Task,
        agent_id: str,
        task_id: str,
        duration_seconds: float,
        ctx: AgentContext | None = None,
        system_prompt: SystemPrompt | None = None,
        completion_config: CompletionConfig | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
    ) -> AgentRunResult:
        """Build an error ``AgentRunResult`` when the execution pipeline fails.

        If constructing the error result itself fails, the original
        exception is re-raised with a note describing the secondary
        failure so it is never silently lost.
        """
        raw_msg = str(exc)
        sanitized = sanitize_message(raw_msg)
        error_msg = f"{type(exc).__name__}: {sanitized}"
        logger.exception(
            EXECUTION_ENGINE_ERROR,
            agent_id=agent_id,
            task_id=task_id,
            error=error_msg,
        )

        pre_fatal_status = (
            ctx.task_execution.status
            if ctx is not None and ctx.task_execution is not None
            else None
        )
        try:
            error_execution = await self._build_error_execution(
                identity,
                task,
                agent_id,
                task_id,
                error_msg,
                ctx,
                completion_config=completion_config,
                effective_autonomy=effective_autonomy,
                provider=provider,
            )
            # Sync fatal-error recovery status to TaskEngine (best-effort).
            error_ctx = error_execution.context
            if (
                error_ctx.task_execution is not None
                and pre_fatal_status is not None
                and error_ctx.task_execution.status != pre_fatal_status
            ):
                logger.info(
                    EXECUTION_ENGINE_TASK_TRANSITION,
                    agent_id=agent_id,
                    task_id=task_id,
                    from_status=pre_fatal_status.value,
                    to_status=error_ctx.task_execution.status.value,
                )
                await sync_to_task_engine(
                    self._task_engine,
                    target_status=error_ctx.task_execution.status,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason=f"Fatal error recovery: {type(exc).__name__}",
                )
            error_prompt = build_error_prompt(
                identity,
                agent_id,
                system_prompt,
            )
            return AgentRunResult(
                execution_result=error_execution,
                system_prompt=error_prompt,
                duration_seconds=duration_seconds,
                agent_id=agent_id,
                task_id=task_id,
            )
        except MemoryError, RecursionError:
            logger.exception(
                EXECUTION_ENGINE_ERROR,
                agent_id=agent_id,
                task_id=task_id,
                error="non-recoverable error while building error result",
            )
            raise
        except Exception as build_exc:
            logger.exception(
                EXECUTION_ENGINE_ERROR,
                agent_id=agent_id,
                task_id=task_id,
                error=f"Failed to build error result: {build_exc}",
                original_error=error_msg,
            )
            exc.add_note(
                f"Secondary failure while building error result: "
                f"{type(build_exc).__name__}: {build_exc}",
            )
            raise exc from None

    async def _build_error_execution(  # noqa: PLR0913
        self,
        identity: AgentIdentity,
        task: Task,
        agent_id: str,
        task_id: str,
        error_msg: str,
        ctx: AgentContext | None,
        *,
        completion_config: CompletionConfig | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        provider: CompletionProvider | None = None,
    ) -> ExecutionResult:
        """Create an error ``ExecutionResult`` and apply recovery."""
        error_ctx = ctx or AgentContext.from_identity(identity, task=task)
        error_execution = ExecutionResult(
            context=error_ctx,
            termination_reason=TerminationReason.ERROR,
            error_message=error_msg,
        )
        result, _ = await self._apply_recovery(
            error_execution,
            identity,
            agent_id,
            task_id,
            completion_config=completion_config,
            effective_autonomy=effective_autonomy,
            provider=provider,
        )
        return result
