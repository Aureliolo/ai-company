"""Service auto-wiring for production startup.

Phase 1 (construction time): creates services that don't need a
connected persistence backend -- message bus, cost tracker, provider
registry, task engine, provider health tracker.

Meeting auto-wire (construction time): creates meeting orchestrator
and meeting scheduler (same lifecycle as Phase 1 but separate call).

Phase 2 (on_startup): creates SettingsService + dispatcher after
persistence connects and migrations complete.
"""

import contextlib
from typing import TYPE_CHECKING, NamedTuple, Protocol

from synthorg.api.channels import ALL_CHANNELS
from synthorg.budget.tracker import CostTracker
from synthorg.communication.meeting.enums import MeetingProtocolType
from synthorg.communication.meeting.models import AgentResponse
from synthorg.communication.meeting.orchestrator import MeetingOrchestrator
from synthorg.communication.meeting.scheduler import MeetingScheduler
from synthorg.engine.task_engine import TaskEngine
from synthorg.engine.workflow.ceremony_scheduler import CeremonyScheduler
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_APP_STARTUP,
    API_SERVICE_AUTO_WIRED,
)
from synthorg.observability.events.meeting import MEETING_STUB_AGENT_CALLER
from synthorg.providers.health import ProviderHealthTracker
from synthorg.providers.registry import ProviderRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.api.state import AppState
    from synthorg.backup.service import BackupService
    from synthorg.communication.bus_protocol import MessageBus
    from synthorg.communication.config import NatsConfig
    from synthorg.communication.meeting.participant import (
        ParticipantResolver,
    )
    from synthorg.communication.meeting.protocol import (
        AgentCaller,
        MeetingProtocol,
    )
    from synthorg.config.schema import RootConfig
    from synthorg.hr.registry import AgentRegistryService
    from synthorg.ontology.service import OntologyService
    from synthorg.persistence.protocol import PersistenceBackend
    from synthorg.settings.dispatcher import SettingsChangeDispatcher
    from synthorg.settings.service import SettingsService
    from synthorg.workers.claim import JetStreamTaskQueue
    from synthorg.workers.config import QueueConfig

logger = get_logger(__name__)


class Phase1Result(NamedTuple):
    """Services created during Phase 1 auto-wiring."""

    message_bus: MessageBus | None
    cost_tracker: CostTracker | None
    task_engine: TaskEngine | None
    provider_registry: ProviderRegistry | None
    provider_health_tracker: ProviderHealthTracker | None
    distributed_task_queue: JetStreamTaskQueue | None


class MeetingWireResult(NamedTuple):
    """Services created during meeting auto-wiring.

    All fields are guaranteed non-``None`` after
    ``auto_wire_meetings()`` returns -- explicit values pass through
    and ``None`` inputs are replaced with auto-wired instances.
    """

    meeting_orchestrator: MeetingOrchestrator
    meeting_scheduler: MeetingScheduler
    ceremony_scheduler: CeremonyScheduler


class BuildDispatcherFn(Protocol):
    """Protocol for the dispatcher builder callback."""

    def __call__(  # noqa: D102
        self,
        message_bus: MessageBus | None,
        settings_service: SettingsService | None,
        config: RootConfig,
        app_state: AppState,
        backup_service: BackupService | None = None,
    ) -> SettingsChangeDispatcher | None: ...


def auto_wire_phase1(  # noqa: PLR0913
    *,
    effective_config: RootConfig,
    persistence: PersistenceBackend | None,
    message_bus: MessageBus | None,
    cost_tracker: CostTracker | None,
    task_engine: TaskEngine | None,
    provider_registry: ProviderRegistry | None,
    provider_health_tracker: ProviderHealthTracker | None,
) -> Phase1Result:
    """Auto-wire services that don't need connected persistence.

    Each service is created only when the caller passes ``None``.
    Explicit values are preserved unchanged.

    Args:
        effective_config: Root company configuration.
        persistence: Persistence backend (may be ``None``).  When
            ``None``, ``task_engine`` cannot be auto-wired and a
            warning is logged.
        message_bus: Explicit bus or ``None`` to auto-wire.
        cost_tracker: Explicit tracker or ``None`` to auto-wire.
        task_engine: Explicit engine or ``None`` to auto-wire.
        provider_registry: Explicit registry or ``None`` to auto-wire.
        provider_health_tracker: Explicit tracker or ``None`` to
            auto-wire.

    Returns:
        A ``Phase1Result`` with all (possibly auto-wired) services.
    """
    distributed_task_queue: JetStreamTaskQueue | None = None

    if message_bus is None:
        message_bus = _auto_wire_message_bus(effective_config)

    if cost_tracker is None:
        cost_tracker = _wire_cost_tracker(effective_config)

    if provider_registry is None and effective_config.providers:
        provider_registry = _wire_provider_registry(effective_config)

    if task_engine is None and persistence is not None:
        task_engine, distributed_task_queue = _wire_task_engine(
            persistence,
            message_bus,
            queue_config=effective_config.queue,
            nats_config=effective_config.communication.message_bus.nats,
        )

    if provider_health_tracker is None:
        provider_health_tracker = ProviderHealthTracker()
        logger.info(API_SERVICE_AUTO_WIRED, service="provider_health_tracker")

    if persistence is None:
        logger.warning(
            API_APP_STARTUP,
            note=(
                "No persistence backend available (SYNTHORG_DB_PATH not set) "
                "-- persistence-dependent services (task_engine, "
                "settings_service) will not be auto-wired; affected "
                "controllers will return 503"
            ),
        )

    return Phase1Result(
        message_bus=message_bus,
        cost_tracker=cost_tracker,
        task_engine=task_engine,
        provider_registry=provider_registry,
        provider_health_tracker=provider_health_tracker,
        distributed_task_queue=distributed_task_queue,
    )


def _wire_cost_tracker(effective_config: RootConfig) -> CostTracker:
    """Create a CostTracker from config."""
    try:
        tracker = CostTracker(budget_config=effective_config.budget)
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to auto-wire cost tracker",
        )
        raise
    logger.info(API_SERVICE_AUTO_WIRED, service="cost_tracker")
    return tracker


def _wire_provider_registry(
    effective_config: RootConfig,
) -> ProviderRegistry:
    """Create a ProviderRegistry from config."""
    try:
        registry = ProviderRegistry.from_config(effective_config.providers)
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to build provider registry from config",
        )
        raise
    logger.info(API_SERVICE_AUTO_WIRED, service="provider_registry")
    return registry


def _wire_task_engine(
    persistence: PersistenceBackend,
    message_bus: MessageBus | None,
    queue_config: QueueConfig | None = None,
    nats_config: NatsConfig | None = None,
) -> tuple[TaskEngine, JetStreamTaskQueue | None]:
    """Create a TaskEngine from persistence and optional bus.

    When ``queue_config.enabled`` is true, also create a
    :class:`JetStreamTaskQueue` and register a
    :class:`DistributedDispatcher` observer so task state changes are
    published to the distributed work queue. The caller owns the
    returned task queue's async lifecycle: it must be ``start()``ed
    before any observer events fire and ``stop()``ped during shutdown
    to avoid leaked NATS connections. The dispatcher registration
    itself is synchronous.

    Returns:
        A ``(task_engine, task_queue)`` tuple. ``task_queue`` is
        non-``None`` only when ``queue_config.enabled`` is true, the
        ``nats_config`` is present, and ``synthorg[distributed]`` is
        installed; otherwise it is ``None`` and the in-process path is
        used.
    """
    try:
        engine = TaskEngine(
            persistence=persistence,
            message_bus=message_bus,
        )
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to auto-wire task engine",
        )
        raise

    task_queue: JetStreamTaskQueue | None = None
    if queue_config is not None and queue_config.enabled:
        if nats_config is None:
            logger.warning(
                API_APP_STARTUP,
                note=(
                    "queue.enabled is true but nats config is missing; "
                    "distributed dispatcher will not be registered"
                ),
            )
        else:
            task_queue = _register_distributed_dispatcher(
                engine,
                queue_config,
                nats_config,
            )

    logger.info(API_SERVICE_AUTO_WIRED, service="task_engine")
    return engine, task_queue


def _register_distributed_dispatcher(
    engine: TaskEngine,
    queue_config: QueueConfig,
    nats_config: NatsConfig,
) -> JetStreamTaskQueue | None:
    """Register the distributed dispatcher observer on the task engine.

    Creates a :class:`JetStreamTaskQueue` (not started) and a
    :class:`DistributedDispatcher` observer. Registration is
    idempotent and best-effort: any failure here is logged but does
    not abort startup, because the in-process path remains viable.

    Returns the constructed queue so the caller can drive its async
    ``start()``/``stop()`` lifecycle; returns ``None`` when the
    optional ``synthorg[distributed]`` dependency is missing or
    construction itself fails.
    """
    try:
        from synthorg.workers.claim import (  # noqa: PLC0415
            JetStreamTaskQueue,
        )
        from synthorg.workers.dispatcher import (  # noqa: PLC0415
            DistributedDispatcher,
        )
    except ImportError:
        logger.warning(
            API_APP_STARTUP,
            note=(
                "queue.enabled is true but 'synthorg[distributed]' is not "
                "installed; distributed dispatcher will not be registered"
            ),
        )
        return None

    try:
        task_queue = JetStreamTaskQueue(
            queue_config=queue_config,
            nats_config=nats_config,
        )
        dispatcher = DistributedDispatcher(task_queue=task_queue)
        engine.register_observer(dispatcher.on_task_state_changed)
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to register distributed dispatcher",
        )
        return None

    logger.info(
        API_SERVICE_AUTO_WIRED,
        service="distributed_dispatcher",
    )
    return task_queue


def _auto_wire_message_bus(
    effective_config: RootConfig,
) -> MessageBus:
    """Create the configured MessageBus with API channels merged in.

    Dispatches to the correct backend via ``build_message_bus`` based
    on ``communication.message_bus.backend``. The default
    ``MessageBusConfig`` channels are organizational (``#all-hands``,
    ``#engineering``, etc.). The API bridge needs additional channels
    defined in ``ALL_CHANNELS`` (see ``synthorg.api.channels``) to
    forward events to WebSocket clients, so they are merged in here
    before the factory runs.

    Args:
        effective_config: Root company configuration.

    Returns:
        A configured ``MessageBus`` instance (not started).
    """
    from synthorg.communication.bus import build_message_bus  # noqa: PLC0415

    try:
        bus_config = effective_config.communication.message_bus
        extra = tuple(ch for ch in ALL_CHANNELS if ch not in bus_config.channels)
        if extra:
            bus_config = bus_config.model_copy(
                update={"channels": (*bus_config.channels, *extra)},
            )
        bus = build_message_bus(bus_config)
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to auto-wire message bus",
        )
        raise
    logger.info(
        API_SERVICE_AUTO_WIRED,
        service="message_bus",
        backend=bus_config.backend.value,
    )
    return bus


def auto_wire_meetings(
    *,
    effective_config: RootConfig,
    meeting_orchestrator: MeetingOrchestrator | None,
    meeting_scheduler: MeetingScheduler | None,
    agent_registry: AgentRegistryService | None,
) -> MeetingWireResult:
    """Auto-wire meeting orchestrator and scheduler.

    Each service is created only when the caller passes ``None``.
    Explicit values are preserved unchanged.  This runs at the same
    lifecycle stage as Phase 1 -- meeting services don't need
    connected persistence.

    Args:
        effective_config: Root company configuration.
        meeting_orchestrator: Explicit orchestrator or ``None`` to
            auto-wire.
        meeting_scheduler: Explicit scheduler or ``None`` to auto-wire.
        agent_registry: Agent registry (may be ``None``).  When
            ``None``, a passthrough participant resolver is used.

    Returns:
        A ``MeetingWireResult`` with both services.
    """
    if meeting_orchestrator is None:
        meeting_orchestrator = _wire_meeting_orchestrator()
        if meeting_scheduler is not None:
            logger.warning(
                API_APP_STARTUP,
                note=(
                    "Auto-wired a new orchestrator but using an explicit "
                    "scheduler -- the scheduler's internal orchestrator "
                    "reference will diverge from the auto-wired one. "
                    "Provide both or neither for consistent state"
                ),
            )

    if meeting_scheduler is None:
        meeting_scheduler = _wire_meeting_scheduler(
            effective_config,
            meeting_orchestrator,
            agent_registry,
        )

    ceremony_scheduler = CeremonyScheduler(
        meeting_scheduler=meeting_scheduler,
    )
    logger.info(API_SERVICE_AUTO_WIRED, service="ceremony_scheduler")

    return MeetingWireResult(
        meeting_orchestrator=meeting_orchestrator,
        meeting_scheduler=meeting_scheduler,
        ceremony_scheduler=ceremony_scheduler,
    )


def _build_protocol_registry() -> Mapping[MeetingProtocolType, MeetingProtocol]:
    """Create a registry of all meeting protocol implementations.

    Uses default per-protocol configs from the Pydantic models.
    The protocol type selected per meeting is determined by
    ``MeetingProtocolConfig.protocol``, not by the registry.

    Returns:
        Mapping from protocol type to implementation.
    """
    # Deferred imports to avoid heavy transitive deps at module level.
    from synthorg.communication.meeting.config import (  # noqa: PLC0415
        PositionPapersConfig,
        RoundRobinConfig,
        StructuredPhasesConfig,
    )
    from synthorg.communication.meeting.position_papers import (  # noqa: PLC0415
        PositionPapersProtocol,
    )
    from synthorg.communication.meeting.round_robin import (  # noqa: PLC0415
        RoundRobinProtocol,
    )
    from synthorg.communication.meeting.structured_phases import (  # noqa: PLC0415
        StructuredPhasesProtocol,
    )

    registry: dict[MeetingProtocolType, MeetingProtocol] = {
        MeetingProtocolType.ROUND_ROBIN: RoundRobinProtocol(
            RoundRobinConfig(),
        ),
        MeetingProtocolType.POSITION_PAPERS: PositionPapersProtocol(
            PositionPapersConfig(),
        ),
        MeetingProtocolType.STRUCTURED_PHASES: StructuredPhasesProtocol(
            StructuredPhasesConfig(),
        ),
    }

    if len(registry) != len(MeetingProtocolType):
        msg = (
            f"Protocol registry has {len(registry)} entries but "
            f"{len(MeetingProtocolType)} protocol types exist"
        )
        raise RuntimeError(msg)

    return registry


def _build_stub_agent_caller() -> AgentCaller:
    """Create a stub agent caller for auto-wired meetings.

    Returns an async callback that produces placeholder
    ``AgentResponse`` instances with zero tokens and empty content.
    This allows the meeting subsystem to be structurally available
    (no 503) while actual agent invocation requires a coordinator.

    Returns:
        An ``AgentCaller`` compatible async callback.
    """

    async def _stub_caller(
        agent_id: str,
        _prompt: str,
        _max_tokens: int,
    ) -> AgentResponse:
        logger.warning(
            MEETING_STUB_AGENT_CALLER,
            agent_id=agent_id,
            note=(
                "Stub agent caller invoked -- response will be "
                "empty until a coordinator is configured"
            ),
        )
        return AgentResponse(
            agent_id=agent_id,
            content="",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )

    return _stub_caller


def _wire_meeting_orchestrator() -> MeetingOrchestrator:
    """Create a MeetingOrchestrator with all protocols registered.

    Returns:
        A configured ``MeetingOrchestrator`` instance.
    """
    try:
        protocol_registry = _build_protocol_registry()
        agent_caller = _build_stub_agent_caller()
        orchestrator = MeetingOrchestrator(
            protocol_registry=protocol_registry,
            agent_caller=agent_caller,
        )
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to auto-wire meeting orchestrator",
        )
        raise
    logger.info(API_SERVICE_AUTO_WIRED, service="meeting_orchestrator")
    return orchestrator


def _select_participant_resolver(
    agent_registry: AgentRegistryService | None,
) -> ParticipantResolver:
    """Choose a participant resolver based on registry availability.

    Args:
        agent_registry: Agent registry (may be ``None``).

    Returns:
        ``RegistryParticipantResolver`` if *agent_registry* is
        available, otherwise ``PassthroughParticipantResolver``.
    """
    from synthorg.communication.meeting.participant import (  # noqa: PLC0415
        PassthroughParticipantResolver,
        RegistryParticipantResolver,
    )

    if agent_registry is not None:
        return RegistryParticipantResolver(agent_registry)
    logger.warning(
        API_APP_STARTUP,
        note=(
            "No agent registry available -- meeting "
            "scheduler using passthrough participant "
            "resolver (literal IDs only)"
        ),
    )
    return PassthroughParticipantResolver()


def _wire_meeting_scheduler(
    effective_config: RootConfig,
    orchestrator: MeetingOrchestrator,
    agent_registry: AgentRegistryService | None,
) -> MeetingScheduler:
    """Create a MeetingScheduler with participant resolver.

    Args:
        effective_config: Root company configuration.
        orchestrator: Meeting orchestrator instance.
        agent_registry: Agent registry (may be ``None``).

    Returns:
        A configured ``MeetingScheduler`` instance.
    """
    try:
        resolver = _select_participant_resolver(agent_registry)
        scheduler = MeetingScheduler(
            config=effective_config.communication.meetings,
            orchestrator=orchestrator,
            participant_resolver=resolver,
        )
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to auto-wire meeting scheduler",
        )
        raise
    logger.info(API_SERVICE_AUTO_WIRED, service="meeting_scheduler")
    return scheduler


async def auto_wire_settings(  # noqa: PLR0913
    persistence: PersistenceBackend,
    message_bus: MessageBus | None,
    effective_config: RootConfig,
    app_state: AppState,
    backup_service: BackupService | None,
    build_dispatcher: BuildDispatcherFn,
) -> SettingsChangeDispatcher | None:
    """Phase 2 auto-wire: create SettingsService after persistence connects.

    Called from ``on_startup`` after persistence connects.  Creates
    the settings service, starts the dispatcher, and only then injects
    the service into *app_state* (to avoid partial state corruption if
    the dispatcher fails to start).

    Args:
        persistence: Connected persistence backend.
        message_bus: Message bus instance (may be ``None``).
        effective_config: Root company configuration.
        app_state: Application state container.
        backup_service: Backup service (for settings subscriber wiring).
        build_dispatcher: Callable that builds a settings dispatcher.

    Returns:
        The started dispatcher, or ``None`` if ``build_dispatcher``
        returns ``None`` (typically when no message bus is available).
    """
    # Deferred to break import cycle: settings.* -> api.* -> auto_wire
    import synthorg.settings.definitions  # noqa: F401, PLC0415
    from synthorg.settings.encryption import SettingsEncryptor  # noqa: PLC0415
    from synthorg.settings.registry import get_registry  # noqa: PLC0415
    from synthorg.settings.service import SettingsService  # noqa: PLC0415

    try:
        encryptor = SettingsEncryptor.from_env()
        settings_svc = SettingsService(
            repository=persistence.settings,
            registry=get_registry(),
            config=effective_config,
            encryptor=encryptor,
            message_bus=message_bus,
        )
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error=(
                "Failed to create SettingsService -- check encryption key configuration"
            ),
        )
        raise

    # Build and start the dispatcher BEFORE mutating AppState, so a
    # dispatcher.start() failure doesn't leave app_state with a
    # settings service that has no running dispatcher.
    try:
        dispatcher = build_dispatcher(
            message_bus,
            settings_svc,
            effective_config,
            app_state,
            backup_service,
        )
    except Exception:
        logger.exception(
            API_APP_STARTUP,
            error="Failed to build settings dispatcher",
        )
        raise

    if dispatcher is not None:
        try:
            await dispatcher.start()
        except Exception:
            logger.exception(
                API_APP_STARTUP,
                error="Failed to start auto-wired settings dispatcher",
            )
            raise
        logger.info(API_SERVICE_AUTO_WIRED, service="settings_dispatcher")

    # All fallible operations succeeded -- safe to mutate AppState.
    # If set_settings_service fails, stop the dispatcher to prevent leaks.
    try:
        app_state.set_settings_service(settings_svc)
    except Exception:
        if dispatcher is not None:
            with contextlib.suppress(Exception):
                await dispatcher.stop()
        raise
    logger.info(API_SERVICE_AUTO_WIRED, service="settings_service")
    return dispatcher


async def auto_wire_ontology(
    effective_config: RootConfig,
) -> OntologyService | None:
    """Auto-wire the ontology subsystem.

    Creates the SQLite backend, connects it, applies the schema,
    wires up versioning, creates the ``OntologyService``, and runs
    bootstrap (decorator registry + config entities).

    Args:
        effective_config: Root company configuration.

    Returns:
        The bootstrapped ``OntologyService``, or ``None`` if wiring
        fails (non-fatal -- ontology is not required for startup).
    """
    from synthorg.observability.events.ontology import (  # noqa: PLC0415
        ONTOLOGY_AUTO_WIRE_FAILED,
    )
    from synthorg.ontology.backends.sqlite.backend import (  # noqa: PLC0415
        SQLiteOntologyBackend,
    )
    from synthorg.ontology.service import OntologyService  # noqa: PLC0415
    from synthorg.ontology.versioning import (  # noqa: PLC0415
        create_ontology_versioning,
    )

    ontology_config = effective_config.ontology
    # Resolve database path: use the persistence SQLite path if available,
    # otherwise default to in-memory.
    db_path = effective_config.persistence.sqlite.path or ":memory:"

    backend = SQLiteOntologyBackend(db_path=db_path)
    try:
        await backend.connect()
        versioning = create_ontology_versioning(backend.get_db())
        service = OntologyService(
            backend=backend,
            versioning=versioning,
            config=ontology_config,
        )
        await service.bootstrap()
        if ontology_config.entities.entries:
            await service.bootstrap_from_config(ontology_config.entities)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.warning(
            ONTOLOGY_AUTO_WIRE_FAILED,
            error_type=type(exc).__name__,
            error=str(exc),
            exc_info=True,
        )
        with contextlib.suppress(Exception):
            await backend.disconnect()
        return None
    else:
        logger.info(API_SERVICE_AUTO_WIRED, service="ontology_service")
        return service
