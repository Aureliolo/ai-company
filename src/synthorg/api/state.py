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
from synthorg.client.simulation_state import ClientSimulationState  # noqa: TC001
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
from synthorg.hr.scaling.service import ScalingService  # noqa: TC001
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
    from synthorg.engine.workflow.webhook_bridge import WebhookEventBridge
    from synthorg.integrations.connections.catalog import ConnectionCatalog
    from synthorg.integrations.health.prober import HealthProberService
    from synthorg.integrations.mcp_catalog.installations import (
        McpInstallationRepository,
    )
    from synthorg.integrations.mcp_catalog.service import CatalogService
    from synthorg.integrations.oauth.token_manager import OAuthTokenManager
    from synthorg.integrations.tunnel.ngrok_adapter import NgrokAdapter

    # Imported under TYPE_CHECKING so the optional ``synthorg[distributed]``
    # extra is not required at runtime for deployments that do not use the
    # distributed task queue.
    from synthorg.workers.claim import JetStreamTaskQueue

logger = get_logger(__name__)


class AppState:
    """Typed application state container.

    Service fields accept ``None`` for dev/test mode. Property
    accessors raise ``ServiceUnavailableError`` (503) when missing.
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
        "_client_simulation_state",
        "_config_resolver",
        "_connection_catalog",
        "_coordination_metrics_store",
        "_coordinator",
        "_cost_tracker",
        "_delegation_record_store",
        "_distributed_task_queue",
        "_drift_detection_service",
        "_drift_report_store",
        "_fine_tune_orchestrator",
        "_health_prober_service",
        "_lockout_store",
        "_mcp_catalog_service",
        "_mcp_installations_repo",
        "_meeting_orchestrator",
        "_meeting_scheduler",
        "_message_bus",
        "_model_router",
        "_notification_dispatcher",
        "_oauth_token_manager",
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
        "_scaling_service",
        "_session_store",
        "_settings_service",
        "_task_engine",
        "_ticket_store",
        "_tool_invocation_tracker",
        "_trust_service",
        "_tunnel_provider",
        "_user_presence",
        "_webhook_event_bridge",
        "_webhook_replay_protector",
        "approval_store",
        "config",
        "startup_time",
    )

    def __init__(  # noqa: PLR0913, PLR0915
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
        connection_catalog: ConnectionCatalog | None = None,
        oauth_token_manager: OAuthTokenManager | None = None,
        health_prober_service: HealthProberService | None = None,
        tunnel_provider: NgrokAdapter | None = None,
        webhook_event_bridge: WebhookEventBridge | None = None,
        mcp_catalog_service: CatalogService | None = None,
        mcp_installations_repo: McpInstallationRepository | None = None,
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
        self._connection_catalog = connection_catalog
        self._oauth_token_manager = oauth_token_manager
        self._health_prober_service = health_prober_service
        self._tunnel_provider = tunnel_provider
        self._webhook_event_bridge = webhook_event_bridge
        self._webhook_replay_protector: object | None = None
        self._mcp_catalog_service = mcp_catalog_service
        self._mcp_installations_repo = mcp_installations_repo
        self._prometheus_collector: PrometheusCollector | None = None
        self._fine_tune_orchestrator: FineTuneOrchestrator | None = None
        self._config_resolver: ConfigResolver | None = None
        self._provider_management: ProviderManagementService | None = None
        self._org_mutation_service: OrgMutationService | None = None
        self._init_derived_services(
            settings_service=settings_service,
            config=config,
            persistence=persistence,
        )
        self._review_gate_service: ReviewGateService | None = None
        self._scaling_service: ScalingService | None = None
        self._client_simulation_state: ClientSimulationState | None = None
        self._approval_timeout_scheduler: ApprovalTimeoutScheduler | None = None
        self._session_store: SessionStore | None = None
        self._lockout_store: LockoutStore | None = None
        self._ticket_store = WsTicketStore()
        self._user_presence = UserPresence()
        self.startup_time = startup_time

    def _init_derived_services(
        self,
        *,
        settings_service: SettingsService | None,
        config: RootConfig,
        persistence: PersistenceBackend | None,
    ) -> None:
        """Build services that depend on other injected services.

        Constructs into locals first, then assigns atomically so a
        failure in any constructor leaves AppState unchanged.
        """
        if settings_service is None:
            return
        resolver = ConfigResolver(
            settings_service=settings_service,
            config=config,
        )
        management = ProviderManagementService(
            settings_service=settings_service,
            config_resolver=resolver,
            app_state=self,
            config=config,
        )
        org_mutations = OrgMutationService(
            settings_service=settings_service,
            config_resolver=resolver,
            budget_config_versions=(
                persistence.budget_config_versions if persistence is not None else None
            ),
            company_versions=(
                persistence.company_versions if persistence is not None else None
            ),
        )
        self._config_resolver = resolver
        self._provider_management = management
        self._org_mutation_service = org_mutations

    def _set_once(self, attr: str, value: object, label: str) -> None:
        """Set a private attribute once; raise if already configured."""
        if getattr(self, attr) is not None:
            msg = f"{label} already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        setattr(self, attr, value)
        logger.info(API_APP_STARTUP, note=f"{label} configured")

    def _require_service[T](self, service: T | None, name: str) -> T:
        """Return *service* or raise 503 if not configured."""
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
        """Attach the Prometheus collector (once-only)."""
        self._set_once("_prometheus_collector", collector, "Prometheus collector")

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
        """Attach the task engine (once-only)."""
        self._set_once("_task_engine", engine, "Task engine")

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
        """Attach the review gate service (once-only)."""
        self._set_once("_review_gate_service", service, "Review gate service")

    @property
    def scaling_service(self) -> ScalingService | None:
        """Return scaling service, or None if not configured."""
        return self._scaling_service

    def set_scaling_service(self, service: ScalingService) -> None:
        """Attach the scaling service (once-only)."""
        self._set_once("_scaling_service", service, "Scaling service")

    @property
    def has_client_simulation_state(self) -> bool:
        """Check whether client simulation state is configured."""
        return self._client_simulation_state is not None

    @property
    def client_simulation_state(self) -> ClientSimulationState:
        """Return client simulation state or raise 503."""
        return self._require_service(
            self._client_simulation_state,
            "client_simulation_state",
        )

    def set_client_simulation_state(
        self,
        state: ClientSimulationState,
    ) -> None:
        """Attach the client simulation runtime state (once-only)."""
        self._set_once(
            "_client_simulation_state",
            state,
            "Client simulation state",
        )

    @property
    def approval_timeout_scheduler(self) -> ApprovalTimeoutScheduler | None:
        """Return approval timeout scheduler, or None if not configured."""
        return self._approval_timeout_scheduler

    def set_approval_timeout_scheduler(
        self,
        scheduler: ApprovalTimeoutScheduler,
    ) -> None:
        """Attach the approval timeout scheduler (once-only)."""
        self._set_once(
            "_approval_timeout_scheduler",
            scheduler,
            "Approval timeout scheduler",
        )

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
        """Attach the fine-tune orchestrator (once-only)."""
        self._set_once(
            "_fine_tune_orchestrator",
            orchestrator,
            "Fine-tune orchestrator",
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
        """Attach the session store (once-only)."""
        self._set_once("_session_store", store, "Session store")

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
        """Attach the lockout store (once-only)."""
        self._set_once("_lockout_store", store, "Lockout store")

    @property
    def user_presence(self) -> UserPresence:
        """Return the user presence tracker (always available)."""
        return self._user_presence

    def set_auth_service(self, service: AuthService) -> None:
        """Attach the auth service (once-only)."""
        self._set_once("_auth_service", service, "Auth service")

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
        """Attach the drift report store (once-only)."""
        self._set_once("_drift_report_store", store, "Drift report store")

    def set_drift_detection_service(
        self,
        service: DriftDetectionService,
    ) -> None:
        """Attach the drift detection service (once-only)."""
        self._set_once(
            "_drift_detection_service",
            service,
            "Drift detection service",
        )

    def set_ontology_sync_service(
        self,
        service: OntologyOrgMemorySync,
    ) -> None:
        """Attach the ontology sync service (once-only)."""
        self._set_once(
            "_ontology_sync_service",
            service,
            "Ontology sync service",
        )

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
        """Attach the backup service (once-only)."""
        self._set_once("_backup_service", service, "Backup service")

    # -- Integration services ─────────────────────────────────────

    @property
    def has_connection_catalog(self) -> bool:
        """Check whether the connection catalog is configured."""
        return self._connection_catalog is not None

    @property
    def connection_catalog(self) -> ConnectionCatalog:
        """Return connection catalog or raise 503."""
        return self._require_service(
            self._connection_catalog,
            "connection_catalog",
        )

    @property
    def has_tunnel_provider(self) -> bool:
        """Check whether the tunnel provider is configured."""
        return self._tunnel_provider is not None

    @property
    def tunnel_provider(self) -> NgrokAdapter:
        """Return tunnel provider or raise 503."""
        return self._require_service(
            self._tunnel_provider,
            "tunnel_provider",
        )

    @property
    def oauth_token_manager(self) -> OAuthTokenManager | None:
        """Return OAuth token manager, or None if not configured."""
        return self._oauth_token_manager

    @property
    def health_prober_service(self) -> HealthProberService | None:
        """Return health prober service, or None if not configured."""
        return self._health_prober_service

    @property
    def webhook_event_bridge(self) -> WebhookEventBridge | None:
        """Return webhook event bridge, or None if not configured."""
        return self._webhook_event_bridge

    @property
    def mcp_catalog_service(self) -> CatalogService:
        """Return MCP catalog service or raise 503.

        The bundled MCP catalog is a stateless static loader with
        no dependencies, so it is always wired in ``create_app``.
        """
        return self._require_service(
            self._mcp_catalog_service,
            "mcp_catalog_service",
        )

    def set_mcp_catalog_service(self, service: CatalogService) -> None:
        """Attach the MCP catalog service (once-only)."""
        self._set_once("_mcp_catalog_service", service, "MCP catalog service")

    @property
    def has_mcp_installations_repo(self) -> bool:
        """Check whether the MCP installations repository is configured."""
        return self._mcp_installations_repo is not None

    @property
    def mcp_installations_repo(self) -> McpInstallationRepository:
        """Return the MCP installations repository or raise 503."""
        return self._require_service(
            self._mcp_installations_repo,
            "mcp_installations_repo",
        )

    def set_mcp_installations_repo(
        self,
        repo: McpInstallationRepository,
    ) -> None:
        """Attach the MCP installations repository (once-only)."""
        self._set_once(
            "_mcp_installations_repo",
            repo,
            "MCP installations repository",
        )

    def set_settings_service(self, settings_service: SettingsService) -> None:
        """Set settings service and rebuild derived services."""
        if self._settings_service is not None:
            msg = "Settings service already configured"
            logger.error(API_APP_STARTUP, error=msg)
            raise RuntimeError(msg)
        self._init_derived_services(
            settings_service=settings_service,
            config=self.config,
            persistence=self._persistence,
        )
        self._settings_service = settings_service
        logger.info(API_APP_STARTUP, note="Settings service configured")
