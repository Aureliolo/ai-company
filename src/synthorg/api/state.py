"""Application state container.

Holds typed references to core services, injected into
``app.state`` at startup and accessed by controllers via
``request.app.state``.
"""

from typing import TYPE_CHECKING

from synthorg.api.approval_store import ApprovalStore  # noqa: TC001
from synthorg.api.auth.lockout_store import LockoutStore  # noqa: TC001
from synthorg.api.auth.presence import UserPresence
from synthorg.api.auth.service import AuthService  # noqa: TC001
from synthorg.api.auth.session_store import SessionStore  # noqa: TC001
from synthorg.api.auth.ticket_store import WsTicketStore
from synthorg.api.errors import ServiceUnavailableError
from synthorg.api.services.org_mutations import OrgMutationService
from synthorg.backup.service import BackupService  # noqa: TC001
from synthorg.budget.coordination_store import (
    CoordinationMetricsStore,  # noqa: TC001
)
from synthorg.budget.tracker import CostTracker  # noqa: TC001
from synthorg.communication.bus_protocol import MessageBus  # noqa: TC001
from synthorg.communication.delegation.record_store import (
    DelegationRecordStore,  # noqa: TC001
)
from synthorg.communication.meeting.orchestrator import (
    MeetingOrchestrator,  # noqa: TC001
)
from synthorg.communication.meeting.scheduler import MeetingScheduler  # noqa: TC001
from synthorg.config.schema import RootConfig  # noqa: TC001
from synthorg.engine.approval_gate import ApprovalGate  # noqa: TC001
from synthorg.engine.coordination.service import MultiAgentCoordinator  # noqa: TC001
from synthorg.engine.review_gate import ReviewGateService  # noqa: TC001
from synthorg.engine.task_engine import TaskEngine  # noqa: TC001
from synthorg.engine.workflow.ceremony_scheduler import CeremonyScheduler  # noqa: TC001
from synthorg.hr.performance.tracker import PerformanceTracker  # noqa: TC001
from synthorg.hr.registry import AgentRegistryService  # noqa: TC001
from synthorg.memory.embedding.fine_tune_orchestrator import (
    FineTuneOrchestrator,  # noqa: TC001
)
from synthorg.notifications.dispatcher import (
    NotificationDispatcher,  # noqa: TC001
)
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_STARTUP, API_SERVICE_UNAVAILABLE
from synthorg.observability.events.settings import SETTINGS_SERVICE_SWAPPED
from synthorg.observability.prometheus_collector import (
    PrometheusCollector,  # noqa: TC001
)
from synthorg.ontology.drift.service import DriftDetectionService  # noqa: TC001
from synthorg.ontology.drift.store import DriftReportStore  # noqa: TC001
from synthorg.ontology.service import OntologyService  # noqa: TC001
from synthorg.ontology.sync import OntologyOrgMemorySync  # noqa: TC001
from synthorg.persistence.artifact_storage import (
    ArtifactStorageBackend,  # noqa: TC001
)
from synthorg.persistence.protocol import PersistenceBackend  # noqa: TC001
from synthorg.providers.health import ProviderHealthTracker  # noqa: TC001
from synthorg.providers.management.service import (
    ProviderManagementService,
)
from synthorg.providers.registry import ProviderRegistry  # noqa: TC001
from synthorg.providers.routing.router import ModelRouter  # noqa: TC001
from synthorg.security.audit import AuditLog  # noqa: TC001
from synthorg.security.timeout.scheduler import ApprovalTimeoutScheduler  # noqa: TC001
from synthorg.security.trust.service import TrustService  # noqa: TC001
from synthorg.settings.resolver import ConfigResolver
from synthorg.settings.service import SettingsService  # noqa: TC001
from synthorg.tools.invocation_tracker import ToolInvocationTracker  # noqa: TC001

if TYPE_CHECKING:
    # Imported under TYPE_CHECKING so the optional ``synthorg[distributed]``
    # extra is not required at runtime for deployments that do not use the
    # distributed task queue.
    from synthorg.workers.claim import JetStreamTaskQueue

logger = get_logger(__name__)


class AppState:
    """Typed application state container.

    All service fields accept ``None`` at construction time for
    dev/test mode.  Property accessors raise
    ``ServiceUnavailableError`` (HTTP 503) when the service is not
    configured, producing a clear error instead of an opaque
    ``AttributeError``.

    Attributes:
        config: Root company configuration.
        approval_store: In-memory approval queue store.
        startup_time: ``time.monotonic()`` snapshot at app creation.
        ticket_store: In-memory one-time WebSocket ticket store
            (always available, no ``_require_service`` guard needed).
    """

    __slots__ = (
        "_agent_registry",
        "_approval_gate",
        "_approval_timeout_scheduler",
        "_artifact_storage",
        "_audit_log",
        "_auth_service",
        "_backup_service",
        "_ceremony_scheduler",
        "_config_resolver",
        "_coordination_metrics_store",
        "_coordinator",
        "_cost_tracker",
        "_delegation_record_store",
        "_distributed_task_queue",
        "_drift_detection_service",
        "_drift_report_store",
        "_fine_tune_orchestrator",
        "_lockout_store",
        "_meeting_orchestrator",
        "_meeting_scheduler",
        "_message_bus",
        "_model_router",
        "_notification_dispatcher",
        "_ontology_service",
        "_ontology_sync_service",
        "_org_mutation_service",
        "_performance_tracker",
        "_persistence",
        "_prometheus_collector",
        "_provider_health_tracker",
        "_provider_management",
        "_provider_registry",
        "_review_gate_service",
        "_session_store",
        "_settings_service",
        "_task_engine",
        "_ticket_store",
        "_tool_invocation_tracker",
        "_trust_service",
        "_user_presence",
        "approval_store",
        "config",
        "startup_time",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        config: RootConfig,
        approval_store: ApprovalStore,
        persistence: PersistenceBackend | None = None,
        message_bus: MessageBus | None = None,
        cost_tracker: CostTracker | None = None,
        auth_service: AuthService | None = None,
        task_engine: TaskEngine | None = None,
        approval_gate: ApprovalGate | None = None,
        coordinator: MultiAgentCoordinator | None = None,
        agent_registry: AgentRegistryService | None = None,
        performance_tracker: PerformanceTracker | None = None,
        meeting_orchestrator: MeetingOrchestrator | None = None,
        meeting_scheduler: MeetingScheduler | None = None,
        ceremony_scheduler: CeremonyScheduler | None = None,
        settings_service: SettingsService | None = None,
        provider_registry: ProviderRegistry | None = None,
        model_router: ModelRouter | None = None,
        provider_health_tracker: ProviderHealthTracker | None = None,
        tool_invocation_tracker: ToolInvocationTracker | None = None,
        delegation_record_store: DelegationRecordStore | None = None,
        artifact_storage: ArtifactStorageBackend | None = None,
        notification_dispatcher: NotificationDispatcher | None = None,
        ontology_service: OntologyService | None = None,
        audit_log: AuditLog | None = None,
        trust_service: TrustService | None = None,
        coordination_metrics_store: CoordinationMetricsStore | None = None,
        startup_time: float = 0.0,
    ) -> None:
        self.config = config
        self.approval_store = approval_store
        self._approval_gate = approval_gate
        self._artifact_storage = artifact_storage
        self._audit_log = audit_log
        self._backup_service: BackupService | None = None
        self._coordination_metrics_store = coordination_metrics_store
        self._notification_dispatcher = notification_dispatcher
        self._ontology_service = ontology_service
        self._drift_report_store: DriftReportStore | None = None
        self._drift_detection_service: DriftDetectionService | None = None
        self._ontology_sync_service: OntologyOrgMemorySync | None = None
        self._persistence = persistence
        self._message_bus = message_bus
        self._cost_tracker = cost_tracker
        self._auth_service = auth_service
        self._task_engine = task_engine
        self._distributed_task_queue: JetStreamTaskQueue | None = None
        self._coordinator = coordinator
        self._agent_registry = agent_registry
        self._performance_tracker = performance_tracker
        self._trust_service = trust_service
        self._meeting_orchestrator = meeting_orchestrator
        self._meeting_scheduler = meeting_scheduler
        self._ceremony_scheduler = ceremony_scheduler
        self._settings_service = settings_service
        self._provider_registry = provider_registry
        self._model_router = model_router
        self._provider_health_tracker = provider_health_tracker
        self._tool_invocation_tracker = tool_invocation_tracker
        self._delegation_record_store = delegation_record_store
        self._prometheus_collector: PrometheusCollector | None = None
        self._fine_tune_orchestrator: FineTuneOrchestrator | None = None
        self._config_resolver: ConfigResolver | None = (
            ConfigResolver(settings_service=settings_service, config=config)
            if settings_service is not None
            else None
        )
        self._provider_management: ProviderManagementService | None = (
            ProviderManagementService(
                settings_service=settings_service,
                config_resolver=self._config_resolver,
                app_state=self,
                config=config,
            )
            if settings_service is not None and self._config_resolver is not None
            else None
        )
        self._org_mutation_service: OrgMutationService | None = (
            OrgMutationService(
                settings_service=settings_service,
                config_resolver=self._config_resolver,
                budget_config_versions=(
                    persistence.budget_config_versions
                    if persistence is not None
                    else None
                ),
                company_versions=(
                    persistence.company_versions if persistence is not None else None
                ),
            )
            if settings_service is not None and self._config_resolver is not None
            else None
        )
        self._review_gate_service: ReviewGateService | None = None
        self._approval_timeout_scheduler: ApprovalTimeoutScheduler | None = None
        self._session_store: SessionStore | None = None
        self._lockout_store: LockoutStore | None = None
        self._ticket_store = WsTicketStore()
        self._user_presence = UserPresence()
        self.startup_time = startup_time

    def _require_service[T](self, service: T | None, name: str) -> T:
        """Return *service* or raise 503 if not configured.

        Args:
            service: Service instance (``None`` when not configured).
            name: Service name for logging and error message.

        Raises:
            ServiceUnavailableError: If *service* is ``None``.
        """
        if service is None:
            logger.warning(API_SERVICE_UNAVAILABLE, service=name)
            msg = f"{name.replace('_', ' ').title()} not configured"
            raise ServiceUnavailableError(msg)
        return service

    @property
    def has_persistence(self) -> bool:
        """Check whether the persistence backend is configured."""
        return self._persistence is not None

    @property
    def persistence(self) -> PersistenceBackend:
        """Return persistence backend or raise 503."""
        return self._require_service(self._persistence, "persistence")

    @property
    def has_prometheus_collector(self) -> bool:
        """Check whether the Prometheus collector is configured."""
        return self._prometheus_collector is not None

    @property
    def prometheus_collector(self) -> PrometheusCollector:
        """Return Prometheus collector or raise 503."""
        return self._require_service(
            self._prometheus_collector,
            "prometheus_collector",
        )

    def set_prometheus_collector(
        self,
        collector: PrometheusCollector,
    ) -> None:
        """Set the Prometheus collector (deferred initialisation).

        Args:
            collector: Fully configured Prometheus collector.

        Raises:
            RuntimeError: If the collector was already configured.
        """
        if self._prometheus_collector is not None:
            msg = "Prometheus collector already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._prometheus_collector = collector
        logger.info(API_APP_STARTUP, note="Prometheus collector configured")

    @property
    def has_artifact_storage(self) -> bool:
        """Check whether the artifact storage backend is configured."""
        return self._artifact_storage is not None

    @property
    def artifact_storage(self) -> ArtifactStorageBackend:
        """Return artifact storage backend or raise 503."""
        return self._require_service(self._artifact_storage, "artifact_storage")

    @property
    def has_message_bus(self) -> bool:
        """Check whether the message bus is configured."""
        return self._message_bus is not None

    @property
    def message_bus(self) -> MessageBus:
        """Return message bus or raise 503."""
        return self._require_service(self._message_bus, "message_bus")

    @property
    def has_cost_tracker(self) -> bool:
        """Check whether the cost tracker is configured."""
        return self._cost_tracker is not None

    @property
    def cost_tracker(self) -> CostTracker:
        """Return cost tracker or raise 503."""
        return self._require_service(self._cost_tracker, "cost_tracker")

    @property
    def auth_service(self) -> AuthService:
        """Return auth service or raise 503."""
        return self._require_service(self._auth_service, "auth_service")

    @property
    def task_engine(self) -> TaskEngine:
        """Return task engine or raise 503."""
        return self._require_service(self._task_engine, "task_engine")

    @property
    def has_task_engine(self) -> bool:
        """Check whether the task engine is already configured."""
        return self._task_engine is not None

    def set_task_engine(self, engine: TaskEngine) -> None:
        """Set the task engine (deferred initialisation).

        Supports late binding when the task engine is created after
        ``AppState`` construction.

        Args:
            engine: Fully configured task engine.

        Raises:
            RuntimeError: If the task engine was already configured.
        """
        if self._task_engine is not None:
            msg = "Task engine already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._task_engine = engine
        logger.info(API_APP_STARTUP, note="Task engine configured")

    @property
    def distributed_task_queue(self) -> JetStreamTaskQueue | None:
        """Return the distributed task queue, or ``None`` when not wired."""
        return self._distributed_task_queue

    def set_distributed_task_queue(
        self,
        task_queue: JetStreamTaskQueue | None,
    ) -> None:
        """Attach the distributed task queue so the lifecycle can manage it.

        Only set when ``queue.enabled`` is true and the ``synthorg[distributed]``
        extra is installed. The lifecycle starts and stops the queue
        alongside the other async services so the dispatcher observer
        sees a connected client before any task state changes fire.

        Logs the transition (attach/detach/replace) at INFO so the
        lifecycle state of ``_distributed_task_queue`` is observable in
        structured logs.
        """
        previous = self._distributed_task_queue
        # Identity check first: assigning the same instance is a noop
        # even when both sides are non-None, so callers that re-set
        # the queue during idempotent rewire paths don't see a
        # misleading "replaced" transition in logs.
        if previous is task_queue:
            transition = "noop"
        elif previous is None:
            transition = "attached"
        elif task_queue is None:
            transition = "detached"
        else:
            transition = "replaced"
        self._distributed_task_queue = task_queue
        logger.info(
            API_APP_STARTUP,
            service="distributed_task_queue",
            transition=transition,
        )

    @property
    def meeting_orchestrator(self) -> MeetingOrchestrator:
        """Return meeting orchestrator or raise 503."""
        return self._require_service(
            self._meeting_orchestrator,
            "meeting_orchestrator",
        )

    @property
    def meeting_scheduler(self) -> MeetingScheduler:
        """Return meeting scheduler or raise 503."""
        return self._require_service(
            self._meeting_scheduler,
            "meeting_scheduler",
        )

    @property
    def ceremony_scheduler(self) -> CeremonyScheduler | None:
        """Return ceremony scheduler, or None if not configured."""
        return self._ceremony_scheduler

    @property
    def approval_gate(self) -> ApprovalGate | None:
        """Return approval gate, or None if not configured."""
        return self._approval_gate

    @property
    def review_gate_service(self) -> ReviewGateService | None:
        """Return review gate service, or None if not configured."""
        return self._review_gate_service

    def set_review_gate_service(self, service: ReviewGateService) -> None:
        """Set the review gate service (deferred initialisation).

        Args:
            service: Configured review gate service.

        Raises:
            RuntimeError: If the review gate service was already configured.
        """
        if self._review_gate_service is not None:
            msg = "Review gate service already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._review_gate_service = service
        logger.info(API_APP_STARTUP, note="Review gate service configured")

    @property
    def approval_timeout_scheduler(self) -> ApprovalTimeoutScheduler | None:
        """Return approval timeout scheduler, or None if not configured."""
        return self._approval_timeout_scheduler

    def set_approval_timeout_scheduler(
        self,
        scheduler: ApprovalTimeoutScheduler,
    ) -> None:
        """Set the approval timeout scheduler (deferred initialisation).

        Args:
            scheduler: Configured scheduler instance.

        Raises:
            RuntimeError: If the scheduler was already configured.
        """
        if self._approval_timeout_scheduler is not None:
            msg = "Approval timeout scheduler already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._approval_timeout_scheduler = scheduler
        logger.info(API_APP_STARTUP, note="Approval timeout scheduler configured")

    @property
    def coordinator(self) -> MultiAgentCoordinator:
        """Return coordinator or raise 503."""
        return self._require_service(self._coordinator, "coordinator")

    @property
    def has_coordinator(self) -> bool:
        """Check whether the coordinator is configured."""
        return self._coordinator is not None

    @property
    def performance_tracker(self) -> PerformanceTracker:
        """Return performance tracker or raise 503."""
        return self._require_service(
            self._performance_tracker,
            "performance_tracker",
        )

    @property
    def agent_registry(self) -> AgentRegistryService:
        """Return agent registry or raise 503."""
        return self._require_service(self._agent_registry, "agent_registry")

    @property
    def has_agent_registry(self) -> bool:
        """Check whether the agent registry is configured."""
        return self._agent_registry is not None

    @property
    def audit_log(self) -> AuditLog:
        """Return audit log or raise 503."""
        return self._require_service(self._audit_log, "audit_log")

    @property
    def has_audit_log(self) -> bool:
        """Check whether the audit log is configured."""
        return self._audit_log is not None

    @property
    def trust_service(self) -> TrustService:
        """Return trust service or raise 503."""
        return self._require_service(
            self._trust_service,
            "trust_service",
        )

    @property
    def has_trust_service(self) -> bool:
        """Check whether the trust service is configured."""
        return self._trust_service is not None

    @property
    def coordination_metrics_store(self) -> CoordinationMetricsStore:
        """Return coordination metrics store or raise 503."""
        return self._require_service(
            self._coordination_metrics_store,
            "coordination_metrics_store",
        )

    @property
    def has_coordination_metrics_store(self) -> bool:
        """Check whether the coordination metrics store is configured."""
        return self._coordination_metrics_store is not None

    @property
    def settings_service(self) -> SettingsService:
        """Return settings service or raise 503."""
        return self._require_service(self._settings_service, "settings_service")

    @property
    def has_settings_service(self) -> bool:
        """Check whether the settings service is configured."""
        return self._settings_service is not None

    @property
    def fine_tune_orchestrator(self) -> FineTuneOrchestrator:
        """Return fine-tune orchestrator or raise 503."""
        return self._require_service(
            self._fine_tune_orchestrator,
            "fine_tune_orchestrator",
        )

    @property
    def has_fine_tune_orchestrator(self) -> bool:
        """Check whether the fine-tune orchestrator is configured."""
        return self._fine_tune_orchestrator is not None

    def set_fine_tune_orchestrator(
        self,
        orchestrator: FineTuneOrchestrator,
    ) -> None:
        """Set the fine-tune orchestrator (lifecycle wiring).

        Args:
            orchestrator: Fully configured fine-tune orchestrator.

        Raises:
            RuntimeError: If the orchestrator was already configured.
        """
        if self._fine_tune_orchestrator is not None:
            msg = "Fine-tune orchestrator already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._fine_tune_orchestrator = orchestrator
        logger.info(
            API_APP_STARTUP,
            note="Fine-tune orchestrator configured",
        )

    @property
    def has_config_resolver(self) -> bool:
        """Check whether the config resolver is configured."""
        return self._config_resolver is not None

    @property
    def config_resolver(self) -> ConfigResolver:
        """Return the cached config resolver or raise 503."""
        return self._require_service(self._config_resolver, "config_resolver")

    @property
    def has_org_mutation_service(self) -> bool:
        """Check whether the org mutation service is configured."""
        return self._org_mutation_service is not None

    @property
    def org_mutation_service(self) -> OrgMutationService:
        """Return the org mutation service or raise 503."""
        return self._require_service(
            self._org_mutation_service,
            "org_mutation_service",
        )

    @property
    def provider_management(self) -> ProviderManagementService:
        """Return provider management service or raise 503."""
        return self._require_service(
            self._provider_management,
            "provider_management",
        )

    @property
    def has_provider_management(self) -> bool:
        """Check whether the provider management service is configured."""
        return self._provider_management is not None

    @property
    def provider_health_tracker(self) -> ProviderHealthTracker:
        """Return provider health tracker or raise 503."""
        return self._require_service(
            self._provider_health_tracker,
            "provider_health_tracker",
        )

    @property
    def has_provider_health_tracker(self) -> bool:
        """Check whether the provider health tracker is configured."""
        return self._provider_health_tracker is not None

    @property
    def has_tool_invocation_tracker(self) -> bool:
        """Check whether the tool invocation tracker is configured."""
        return self._tool_invocation_tracker is not None

    @property
    def tool_invocation_tracker(self) -> ToolInvocationTracker:
        """Return tool invocation tracker or raise 503."""
        return self._require_service(
            self._tool_invocation_tracker,
            "tool_invocation_tracker",
        )

    @property
    def has_delegation_record_store(self) -> bool:
        """Check whether the delegation record store is configured."""
        return self._delegation_record_store is not None

    @property
    def delegation_record_store(self) -> DelegationRecordStore:
        """Return delegation record store or raise 503."""
        return self._require_service(
            self._delegation_record_store,
            "delegation_record_store",
        )

    @property
    def has_auth_service(self) -> bool:
        """Check whether the auth service is already configured."""
        return self._auth_service is not None

    @property
    def ticket_store(self) -> WsTicketStore:
        """Return the WebSocket ticket store (always available)."""
        return self._ticket_store

    @property
    def has_session_store(self) -> bool:
        """Check whether the session store is configured."""
        return self._session_store is not None

    @property
    def session_store(self) -> SessionStore:
        """Return the JWT session store."""
        return self._require_service(
            self._session_store,
            "session_store",
        )

    def set_session_store(self, store: SessionStore) -> None:
        """Set the session store (deferred initialisation).

        Args:
            store: Configured session store.

        Raises:
            RuntimeError: If the session store has already been set.
        """
        if self._session_store is not None:
            msg = "session_store is already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._session_store = store
        logger.info(
            API_APP_STARTUP,
            note="Session store configured",
        )

    @property
    def has_lockout_store(self) -> bool:
        """Check whether the lockout store is configured."""
        return self._lockout_store is not None

    @property
    def lockout_store(self) -> LockoutStore:
        """Return the account lockout store."""
        return self._require_service(
            self._lockout_store,
            "lockout_store",
        )

    def set_lockout_store(self, store: LockoutStore) -> None:
        """Set the lockout store (deferred initialisation).

        Args:
            store: Configured lockout store.

        Raises:
            RuntimeError: If the lockout store has already been set.
        """
        if self._lockout_store is not None:
            msg = "lockout_store is already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._lockout_store = store
        logger.info(
            API_APP_STARTUP,
            note="Lockout store configured",
        )

    @property
    def user_presence(self) -> UserPresence:
        """Return the user presence tracker (always available)."""
        return self._user_presence

    def set_auth_service(self, service: AuthService) -> None:
        """Set the auth service (deferred initialisation).

        Called once during startup after the JWT secret is resolved.

        Args:
            service: Fully configured auth service.

        Raises:
            RuntimeError: If the auth service was already configured.
        """
        if self._auth_service is not None:
            msg = "Auth service already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._auth_service = service
        logger.info(API_APP_STARTUP, note="Auth service configured")

    # ── Swappable provider services (hot-reload) ─────────────────

    @property
    def has_provider_registry(self) -> bool:
        """Check whether the provider registry is configured."""
        return self._provider_registry is not None

    @property
    def provider_registry(self) -> ProviderRegistry:
        """Return provider registry or raise 503."""
        return self._require_service(
            self._provider_registry,
            "provider_registry",
        )

    def swap_provider_registry(self, registry: ProviderRegistry) -> None:
        """Replace the provider registry (hot-reload).

        Unlike ``set_*`` methods, this does not guard against
        replacement -- it is designed for repeated hot-reload swaps.
        Atomic under asyncio's cooperative scheduling -- no ``await``
        points, so no coroutine can observe a partially-updated state.

        .. note::
            Not yet wired to a subscriber -- provided for the provider
            runtime CRUD feature (issue #451).

        Args:
            registry: New provider registry instance.
        """
        old_count = (
            len(self._provider_registry) if self._provider_registry is not None else 0
        )
        self._provider_registry = registry
        logger.info(
            SETTINGS_SERVICE_SWAPPED,
            service="provider_registry",
            old_provider_count=old_count,
            new_provider_count=len(registry),
        )

    @property
    def has_notification_dispatcher(self) -> bool:
        """Check whether the notification dispatcher is configured."""
        return self._notification_dispatcher is not None

    @property
    def notification_dispatcher(self) -> NotificationDispatcher:
        """Return notification dispatcher or raise 503."""
        return self._require_service(
            self._notification_dispatcher, "notification_dispatcher"
        )

    @property
    def ontology_service(self) -> OntologyService:
        """Return ontology service or raise 503."""
        return self._require_service(
            self._ontology_service,
            "ontology_service",
        )

    @property
    def has_ontology_service(self) -> bool:
        """Check whether the ontology service is configured."""
        return self._ontology_service is not None

    @property
    def drift_report_store(self) -> DriftReportStore | None:
        """Return the drift report store, or None if not configured."""
        return self._drift_report_store

    @property
    def drift_detection_service(self) -> DriftDetectionService | None:
        """Return the drift detection service, or None if not configured."""
        return self._drift_detection_service

    @property
    def ontology_sync_service(self) -> OntologyOrgMemorySync | None:
        """Return the ontology sync service, or None if not configured."""
        return self._ontology_sync_service

    def set_drift_report_store(self, store: DriftReportStore) -> None:
        """Set the drift report store (deferred initialisation).

        Args:
            store: Configured drift report store.

        Raises:
            RuntimeError: If the store was already configured.
        """
        if self._drift_report_store is not None:
            msg = "Drift report store already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._drift_report_store = store
        logger.info(API_APP_STARTUP, note="Drift report store configured")

    def set_drift_detection_service(
        self,
        service: DriftDetectionService,
    ) -> None:
        """Set the drift detection service (deferred initialisation).

        Args:
            service: Configured drift detection service.

        Raises:
            RuntimeError: If the service was already configured.
        """
        if self._drift_detection_service is not None:
            msg = "Drift detection service already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._drift_detection_service = service
        logger.info(API_APP_STARTUP, note="Drift detection service configured")

    def set_ontology_sync_service(
        self,
        service: OntologyOrgMemorySync,
    ) -> None:
        """Set the ontology sync service (deferred initialisation).

        Args:
            service: Configured ontology sync service.

        Raises:
            RuntimeError: If the service was already configured.
        """
        if self._ontology_sync_service is not None:
            msg = "Ontology sync service already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._ontology_sync_service = service
        logger.info(API_APP_STARTUP, note="Ontology sync service configured")

    @property
    def has_model_router(self) -> bool:
        """Check whether the model router is configured."""
        return self._model_router is not None

    @property
    def model_router(self) -> ModelRouter:
        """Return model router or raise 503."""
        return self._require_service(self._model_router, "model_router")

    def swap_model_router(self, router: ModelRouter) -> None:
        """Replace the model router (hot-reload).

        Unlike ``set_*`` methods, this does not guard against
        replacement -- it is designed for repeated hot-reload swaps.
        Atomic under asyncio's cooperative scheduling -- no ``await``
        points, so no coroutine can observe a partially-updated state.

        Args:
            router: New model router instance.
        """
        old_strategy = (
            self._model_router.strategy_name if self._model_router is not None else None
        )
        self._model_router = router
        logger.info(
            SETTINGS_SERVICE_SWAPPED,
            service="model_router",
            old_strategy=old_strategy,
            new_strategy=router.strategy_name,
        )

    # ── Backup service (deferred init) ────────────────────────────

    @property
    def has_backup_service(self) -> bool:
        """Check whether the backup service is configured."""
        return self._backup_service is not None

    @property
    def backup_service(self) -> BackupService:
        """Return backup service or raise 503."""
        return self._require_service(self._backup_service, "backup_service")

    def set_backup_service(self, service: BackupService) -> None:
        """Set the backup service (deferred initialisation).

        Supports late binding when the backup service is created
        after ``AppState`` construction.

        Args:
            service: Fully configured backup service.

        Raises:
            RuntimeError: If the backup service was already configured.
        """
        if self._backup_service is not None:
            msg = "Backup service already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._backup_service = service
        logger.info(API_APP_STARTUP, note="Backup service configured")

    def set_settings_service(self, settings_service: SettingsService) -> None:
        """Set settings service and create ConfigResolver + ProviderManagement.

        Called by the auto-wire Phase 2 in ``on_startup`` after
        persistence connects and migrations complete.  Also creates
        ``ConfigResolver`` and ``ProviderManagementService`` which
        depend on the settings service.

        Args:
            settings_service: Fully configured settings service.

        Raises:
            RuntimeError: If the settings service was already configured.
        """
        if self._settings_service is not None:
            msg = "Settings service already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        # Construct into locals first, then assign all at once to ensure
        # atomicity -- a failure in ProviderManagementService construction
        # won't leave AppState with a partial set of services.
        resolver = ConfigResolver(
            settings_service=settings_service,
            config=self.config,
        )
        management = ProviderManagementService(
            settings_service=settings_service,
            config_resolver=resolver,
            app_state=self,
            config=self.config,
        )
        org_mutations = OrgMutationService(
            settings_service=settings_service,
            config_resolver=resolver,
            budget_config_versions=(
                self._persistence.budget_config_versions
                if self._persistence is not None
                else None
            ),
            company_versions=(
                self._persistence.company_versions
                if self._persistence is not None
                else None
            ),
        )
        self._settings_service = settings_service
        self._config_resolver = resolver
        self._provider_management = management
        self._org_mutation_service = org_mutations
        logger.debug(
            API_APP_STARTUP,
            note="Created ConfigResolver, ProviderManagement, OrgMutationService",
        )
