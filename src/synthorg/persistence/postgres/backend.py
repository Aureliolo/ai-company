"""Postgres persistence backend implementation.

Implements the ``PersistenceBackend`` protocol on top of psycopg 3 and
``psycopg_pool.AsyncConnectionPool``.  Repositories are instantiated
per-backend on ``connect()`` and receive the shared pool; each pool
checkout is an independent transaction, so the Postgres backend does
not need the ``shared_write_lock`` workaround that the SQLite backend
uses to serialize writes across a single in-process connection.

The schema uses native Postgres types (JSONB, TIMESTAMPTZ, BIGINT,
BOOLEAN) -- see ``src/synthorg/persistence/postgres/schema.sql``.  At
the Python level, the protocol surface is identical to the SQLite
backend: callers get Pydantic models back either way.
"""

import asyncio
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from synthorg.budget.config import BudgetConfig
from synthorg.core.agent import AgentIdentity
from synthorg.core.company import Company
from synthorg.core.role import Role
from synthorg.core.types import NotBlankStr
from synthorg.engine.workflow.definition import WorkflowDefinition
from synthorg.hr.evaluation.config import EvaluationConfig
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_BACKEND_ALREADY_CONNECTED,
    PERSISTENCE_BACKEND_CONNECTED,
    PERSISTENCE_BACKEND_CONNECTING,
    PERSISTENCE_BACKEND_CONNECTION_FAILED,
    PERSISTENCE_BACKEND_DISCONNECT_ERROR,
    PERSISTENCE_BACKEND_DISCONNECTED,
    PERSISTENCE_BACKEND_DISCONNECTING,
    PERSISTENCE_BACKEND_HEALTH_CHECK,
    PERSISTENCE_BACKEND_NOT_CONNECTED,
)
from synthorg.persistence import atlas
from synthorg.persistence.config import PostgresConfig  # noqa: TC001
from synthorg.persistence.errors import PersistenceConnectionError
from synthorg.persistence.postgres.agent_state_repo import (
    PostgresAgentStateRepository,
)
from synthorg.persistence.postgres.artifact_repo import PostgresArtifactRepository
from synthorg.persistence.postgres.audit_repository import PostgresAuditRepository
from synthorg.persistence.postgres.checkpoint_repo import (
    PostgresCheckpointRepository,
)
from synthorg.persistence.postgres.circuit_breaker_repo import (
    PostgresCircuitBreakerStateRepository,
)
from synthorg.persistence.postgres.decision_repo import PostgresDecisionRepository
from synthorg.persistence.postgres.heartbeat_repo import (
    PostgresHeartbeatRepository,
)
from synthorg.persistence.postgres.hr_repositories import (
    PostgresCollaborationMetricRepository,
    PostgresLifecycleEventRepository,
    PostgresTaskMetricRepository,
)
from synthorg.persistence.postgres.parked_context_repo import (
    PostgresParkedContextRepository,
)
from synthorg.persistence.postgres.preset_repo import (
    PostgresPersonalityPresetRepository,
)
from synthorg.persistence.postgres.project_cost_aggregate_repo import (
    PostgresProjectCostAggregateRepository,
)
from synthorg.persistence.postgres.project_repo import PostgresProjectRepository
from synthorg.persistence.postgres.repositories import (
    PostgresCostRecordRepository,
    PostgresMessageRepository,
    PostgresTaskRepository,
)
from synthorg.persistence.postgres.risk_override_repo import (
    PostgresRiskOverrideRepository,
)
from synthorg.persistence.postgres.settings_repo import PostgresSettingsRepository
from synthorg.persistence.postgres.ssrf_violation_repo import (
    PostgresSsrfViolationRepository,
)
from synthorg.persistence.postgres.user_repo import (
    PostgresApiKeyRepository,
    PostgresUserRepository,
)
from synthorg.persistence.postgres.version_repo import PostgresVersionRepository
from synthorg.persistence.postgres.workflow_definition_repo import (
    PostgresWorkflowDefinitionRepository,
)
from synthorg.persistence.postgres.workflow_execution_repo import (
    PostgresWorkflowExecutionRepository,
)

if TYPE_CHECKING:
    from synthorg.hr.persistence_protocol import (
        CollaborationMetricRepository,
        LifecycleEventRepository,
        TaskMetricRepository,
    )
    from synthorg.persistence.circuit_breaker_repo import (
        CircuitBreakerStateRepository,
    )
    from synthorg.persistence.preset_repository import PersonalityPresetRepository
    from synthorg.persistence.repositories import (
        AgentStateRepository,
        ApiKeyRepository,
        ArtifactRepository,
        AuditRepository,
        CheckpointRepository,
        CostRecordRepository,
        DecisionRepository,
        HeartbeatRepository,
        MessageRepository,
        ParkedContextRepository,
        ProjectRepository,
        SettingsRepository,
        TaskRepository,
        UserRepository,
    )
    from synthorg.persistence.risk_override_repo import RiskOverrideRepository
    from synthorg.persistence.ssrf_violation_repo import SsrfViolationRepository
    from synthorg.persistence.version_repo import VersionRepository
    from synthorg.persistence.workflow_definition_repo import (
        WorkflowDefinitionRepository,
    )
    from synthorg.persistence.workflow_execution_repo import (
        WorkflowExecutionRepository,
    )

logger = get_logger(__name__)


def _build_conninfo(config: PostgresConfig) -> str:
    """Build a libpq conninfo string from a ``PostgresConfig``.

    Uses ``psycopg.conninfo.make_conninfo`` for correct escaping of
    special characters (spaces, backslashes, equals signs) inside
    credentials and identifiers.

    ``connect_timeout`` is rounded up to a whole number of seconds
    because libpq accepts only integer seconds (with a minimum of 2);
    truncating a sub-second value via ``int()`` would round 0.5 down
    to 0 which libpq interprets as "wait indefinitely", silently
    turning a short configured timeout into no timeout at all.
    """
    connect_timeout = max(2, math.ceil(config.connect_timeout_seconds))
    return psycopg.conninfo.make_conninfo(
        host=config.host,
        port=config.port,
        dbname=config.database,
        user=config.username,
        password=config.password.get_secret_value(),
        sslmode=config.ssl_mode,
        application_name=config.application_name,
        connect_timeout=connect_timeout,
    )


class PostgresPersistenceBackend:
    """Postgres implementation of the ``PersistenceBackend`` protocol.

    Uses a ``psycopg_pool.AsyncConnectionPool`` for connection
    management.  Each repository method acquires a connection from the
    pool for the duration of its critical section, so writes are
    isolated per-connection transaction.  There is no shared write
    lock -- unlike SQLite, Postgres per-connection transactions do not
    share a single in-process connection.

    Args:
        config: Postgres-specific configuration.
    """

    def __init__(self, config: PostgresConfig) -> None:
        self._config = config
        self._lifecycle_lock = asyncio.Lock()
        self._pool: AsyncConnectionPool | None = None
        # Repository attributes -- instantiated in Phase 3 ports.
        self._artifacts: ArtifactRepository | None = None
        self._projects: ProjectRepository | None = None
        self._tasks: TaskRepository | None = None
        self._cost_records: CostRecordRepository | None = None
        self._messages: MessageRepository | None = None
        self._lifecycle_events: LifecycleEventRepository | None = None
        self._task_metrics: TaskMetricRepository | None = None
        self._collaboration_metrics: CollaborationMetricRepository | None = None
        self._parked_contexts: ParkedContextRepository | None = None
        self._audit_entries: AuditRepository | None = None
        self._users: UserRepository | None = None
        self._api_keys: ApiKeyRepository | None = None
        self._checkpoints: CheckpointRepository | None = None
        self._heartbeats: HeartbeatRepository | None = None
        self._agent_states: AgentStateRepository | None = None
        self._settings: SettingsRepository | None = None
        self._custom_presets: PersonalityPresetRepository | None = None
        self._workflow_definitions: WorkflowDefinitionRepository | None = None
        self._workflow_executions: WorkflowExecutionRepository | None = None
        self._workflow_versions: VersionRepository[WorkflowDefinition] | None = None
        self._identity_versions: VersionRepository[AgentIdentity] | None = None
        self._evaluation_config_versions: VersionRepository[EvaluationConfig] | None = (
            None
        )
        self._budget_config_versions: VersionRepository[BudgetConfig] | None = None
        self._company_versions: VersionRepository[Company] | None = None
        self._role_versions: VersionRepository[Role] | None = None
        self._decision_records: DecisionRepository | None = None
        self._risk_overrides: RiskOverrideRepository | None = None
        self._ssrf_violations: SsrfViolationRepository | None = None
        self._circuit_breaker_state: CircuitBreakerStateRepository | None = None
        self._project_cost_aggregates: PostgresProjectCostAggregateRepository | None = (
            None
        )

    def _clear_state(self) -> None:
        """Reset pool and repository references to ``None``."""
        self._pool = None
        self._artifacts = None
        self._projects = None
        self._tasks = None
        self._cost_records = None
        self._messages = None
        self._lifecycle_events = None
        self._task_metrics = None
        self._collaboration_metrics = None
        self._parked_contexts = None
        self._audit_entries = None
        self._users = None
        self._api_keys = None
        self._checkpoints = None
        self._heartbeats = None
        self._agent_states = None
        self._settings = None
        self._custom_presets = None
        self._workflow_definitions = None
        self._workflow_executions = None
        self._workflow_versions = None
        self._identity_versions = None
        self._evaluation_config_versions = None
        self._budget_config_versions = None
        self._company_versions = None
        self._role_versions = None
        self._decision_records = None
        self._risk_overrides = None
        self._ssrf_violations = None
        self._circuit_breaker_state = None
        self._project_cost_aggregates = None

    async def _configure_connection(
        self,
        conn: psycopg.AsyncConnection[object],
    ) -> None:
        """Apply per-connection session parameters.

        Called by the pool for every new connection it creates.  Sets
        ``statement_timeout`` to the configured limit so runaway
        queries are killed server-side.  ``SET`` opens an implicit
        transaction in Postgres, so we commit before returning the
        connection to the pool -- psycopg's configure callback
        contract requires the connection be idle on return.
        """
        if self._config.statement_timeout_ms > 0:
            await conn.execute(
                sql.SQL("SET SESSION statement_timeout = {}").format(
                    sql.Literal(self._config.statement_timeout_ms)
                )
            )
            await conn.commit()

    async def connect(self) -> None:
        """Open the pool and instantiate repositories."""
        async with self._lifecycle_lock:
            if self._pool is not None:
                logger.debug(PERSISTENCE_BACKEND_ALREADY_CONNECTED)
                return

            logger.info(
                PERSISTENCE_BACKEND_CONNECTING,
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
            )

            pool: AsyncConnectionPool | None = None
            try:
                conninfo = _build_conninfo(self._config)
                pool = AsyncConnectionPool(
                    conninfo,
                    min_size=self._config.pool_min_size,
                    max_size=self._config.pool_max_size,
                    open=False,
                    configure=self._configure_connection,
                )
                await pool.open(
                    wait=True,
                    timeout=self._config.pool_timeout_seconds,
                )
                self._pool = pool
                self._create_repositories()
            except (psycopg.Error, OSError, TimeoutError) as exc:
                await self._cleanup_failed_connect(exc, pool)

            logger.info(
                PERSISTENCE_BACKEND_CONNECTED,
                host=self._config.host,
                database=self._config.database,
            )

    async def _cleanup_failed_connect(
        self,
        exc: BaseException,
        pool: AsyncConnectionPool | None,
    ) -> None:
        """Log failure, close partial pool, and raise.

        Raises:
            PersistenceConnectionError: Always.
        """
        logger.exception(
            PERSISTENCE_BACKEND_CONNECTION_FAILED,
            host=self._config.host,
            database=self._config.database,
            error=str(exc),
        )
        if pool is not None:
            try:
                await pool.close()
            except (psycopg.Error, OSError) as cleanup_exc:
                logger.warning(
                    PERSISTENCE_BACKEND_DISCONNECT_ERROR,
                    host=self._config.host,
                    error=str(cleanup_exc),
                    error_type=type(cleanup_exc).__name__,
                    context="cleanup_after_connect_failure",
                )
        self._clear_state()
        msg = "Failed to connect to postgres backend"
        raise PersistenceConnectionError(msg) from exc

    def _create_repositories(self) -> None:
        """Instantiate all repository objects from the active pool."""
        assert self._pool is not None  # noqa: S101
        pool = self._pool

        # Core domain repositories.
        self._artifacts = PostgresArtifactRepository(pool)
        self._projects = PostgresProjectRepository(pool)
        self._tasks = PostgresTaskRepository(pool)
        self._cost_records = PostgresCostRecordRepository(pool)
        self._messages = PostgresMessageRepository(pool)

        # HR repositories.
        self._lifecycle_events = PostgresLifecycleEventRepository(pool)
        self._task_metrics = PostgresTaskMetricRepository(pool)
        self._collaboration_metrics = PostgresCollaborationMetricRepository(pool)

        # Operational + security repositories.
        self._parked_contexts = PostgresParkedContextRepository(pool)
        self._audit_entries = PostgresAuditRepository(pool)
        self._users = PostgresUserRepository(pool)
        self._api_keys = PostgresApiKeyRepository(pool)
        self._checkpoints = PostgresCheckpointRepository(pool)
        self._heartbeats = PostgresHeartbeatRepository(pool)
        self._agent_states = PostgresAgentStateRepository(pool)
        self._settings = PostgresSettingsRepository(pool)
        self._custom_presets = PostgresPersonalityPresetRepository(pool)

        # Workflow repositories.
        self._workflow_definitions = PostgresWorkflowDefinitionRepository(pool)
        self._workflow_executions = PostgresWorkflowExecutionRepository(pool)

        # Generic version repositories (one per versioned entity type).
        def _ver_repo[T: BaseModel](
            table: str,
            model_cls: type[T],
        ) -> PostgresVersionRepository[T]:
            def _deserialize(d: object) -> T:
                return model_cls.model_validate(d)

            return PostgresVersionRepository(
                pool=pool,
                table_name=NotBlankStr(table),
                serialize_snapshot=lambda m: m.model_dump(mode="json"),
                deserialize_snapshot=_deserialize,
            )

        self._workflow_versions = _ver_repo(
            "workflow_definition_versions", WorkflowDefinition
        )
        self._identity_versions = _ver_repo("agent_identity_versions", AgentIdentity)
        self._evaluation_config_versions = _ver_repo(
            "evaluation_config_versions", EvaluationConfig
        )
        self._budget_config_versions = _ver_repo("budget_config_versions", BudgetConfig)
        self._company_versions = _ver_repo("company_versions", Company)
        self._role_versions = _ver_repo("role_versions", Role)

        # Append-only / security repositories.  Postgres per-connection
        # transactions handle isolation without the SQLite shared
        # write_lock workaround.
        self._decision_records = PostgresDecisionRepository(pool)
        self._risk_overrides = PostgresRiskOverrideRepository(pool)
        self._ssrf_violations = PostgresSsrfViolationRepository(pool)
        self._circuit_breaker_state = PostgresCircuitBreakerStateRepository(pool)
        self._project_cost_aggregates = PostgresProjectCostAggregateRepository(pool)

    def get_db(self) -> AsyncConnectionPool:
        """Return the shared connection pool.

        Raises:
            PersistenceConnectionError: If not yet connected.
        """
        if self._pool is None:
            msg = "Postgres backend not connected"
            logger.warning(PERSISTENCE_BACKEND_NOT_CONNECTED, error=msg)
            raise PersistenceConnectionError(msg)
        return self._pool

    async def disconnect(self) -> None:
        """Close the connection pool."""
        async with self._lifecycle_lock:
            if self._pool is None:
                return

            logger.info(
                PERSISTENCE_BACKEND_DISCONNECTING,
                host=self._config.host,
                database=self._config.database,
            )
            try:
                await self._pool.close()
                logger.info(
                    PERSISTENCE_BACKEND_DISCONNECTED,
                    host=self._config.host,
                    database=self._config.database,
                )
            except (psycopg.Error, OSError) as exc:
                logger.warning(
                    PERSISTENCE_BACKEND_DISCONNECT_ERROR,
                    host=self._config.host,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            finally:
                self._clear_state()

    async def health_check(self) -> bool:
        """Check database connectivity via ``SELECT 1``.

        Bounded by ``pool_timeout_seconds`` so the probe cannot hang
        indefinitely when the pool is exhausted or the server is
        unreachable -- a stuck health check would otherwise block
        orchestration loops that poll backend readiness.  The timeout
        covers the full probe: waiting for a pool connection checkout
        AND executing the query, whichever takes longer.

        Pool state is captured into a local reference while holding
        ``_lifecycle_lock`` so ``disconnect()`` cannot close the pool
        out from under us after the ``None`` check passes.
        """
        async with self._lifecycle_lock:
            pool = self._pool
        if pool is None:
            return False
        try:
            async with asyncio.timeout(self._config.pool_timeout_seconds):
                async with (
                    pool.connection() as conn,
                    conn.cursor() as cur,
                ):
                    await cur.execute("SELECT 1")
                    row = await cur.fetchone()
                    healthy = row is not None
        except (psycopg.Error, OSError, TimeoutError) as exc:
            logger.warning(
                PERSISTENCE_BACKEND_HEALTH_CHECK,
                healthy=False,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return False
        logger.debug(PERSISTENCE_BACKEND_HEALTH_CHECK, healthy=healthy)
        return healthy

    async def migrate(self) -> None:
        """Apply pending schema migrations via Atlas CLI.

        If migration fails, the pool is closed and backend state is
        cleared so callers cannot continue against a backend whose
        schema is in an indeterminate state (partially applied, or
        rolled back by Atlas).  They must reconnect explicitly.

        Raises:
            PersistenceConnectionError: If not connected.
            MigrationError: If migration application fails.
        """
        async with self._lifecycle_lock:
            if self._pool is None:
                msg = "Cannot migrate: postgres backend not connected"
                logger.warning(PERSISTENCE_BACKEND_NOT_CONNECTED, error=msg)
                raise PersistenceConnectionError(msg)
            db_url = atlas.to_postgres_url(self._config)
            try:
                await atlas.migrate_apply(db_url, backend="postgres")
            except BaseException:
                pool = self._pool
                if pool is not None:
                    try:
                        await pool.close()
                    except (psycopg.Error, OSError) as cleanup_exc:
                        logger.warning(
                            PERSISTENCE_BACKEND_DISCONNECT_ERROR,
                            host=self._config.host,
                            error=str(cleanup_exc),
                            error_type=type(cleanup_exc).__name__,
                            context="cleanup_after_migration_failure",
                        )
                self._clear_state()
                raise

    @property
    def is_connected(self) -> bool:
        """Whether the backend has an open pool."""
        return self._pool is not None

    @property
    def backend_name(self) -> NotBlankStr:
        """Human-readable backend identifier."""
        return NotBlankStr("postgres")

    def _require_connected[T](self, repo: T | None, name: str) -> T:
        """Return *repo* or raise if the backend is not connected.

        Args:
            repo: Repository instance (``None`` when disconnected or
                not yet ported).
            name: Repository name for the error message.

        Raises:
            PersistenceConnectionError: If *repo* is ``None``.
        """
        if repo is None:
            if self._pool is None:
                msg = f"Not connected -- call connect() before accessing {name}"
            else:
                msg = (
                    f"Postgres {name} repository is not yet implemented "
                    f"(Phase 3 port pending)"
                )
            logger.warning(PERSISTENCE_BACKEND_NOT_CONNECTED, error=msg)
            raise PersistenceConnectionError(msg)
        return repo

    @property
    def tasks(self) -> TaskRepository:
        """Repository for Task persistence."""
        return self._require_connected(self._tasks, "tasks")

    @property
    def cost_records(self) -> CostRecordRepository:
        """Repository for CostRecord persistence."""
        return self._require_connected(self._cost_records, "cost_records")

    @property
    def messages(self) -> MessageRepository:
        """Repository for Message persistence."""
        return self._require_connected(self._messages, "messages")

    @property
    def lifecycle_events(self) -> LifecycleEventRepository:
        """Repository for AgentLifecycleEvent persistence."""
        return self._require_connected(self._lifecycle_events, "lifecycle_events")

    @property
    def task_metrics(self) -> TaskMetricRepository:
        """Repository for TaskMetricRecord persistence."""
        return self._require_connected(self._task_metrics, "task_metrics")

    @property
    def collaboration_metrics(self) -> CollaborationMetricRepository:
        """Repository for CollaborationMetricRecord persistence."""
        return self._require_connected(
            self._collaboration_metrics, "collaboration_metrics"
        )

    @property
    def parked_contexts(self) -> ParkedContextRepository:
        """Repository for ParkedContext persistence."""
        return self._require_connected(self._parked_contexts, "parked_contexts")

    @property
    def audit_entries(self) -> AuditRepository:
        """Repository for AuditEntry persistence."""
        return self._require_connected(self._audit_entries, "audit_entries")

    @property
    def decision_records(self) -> DecisionRepository:
        """Repository for DecisionRecord persistence."""
        return self._require_connected(self._decision_records, "decision_records")

    @property
    def users(self) -> UserRepository:
        """Repository for User persistence."""
        return self._require_connected(self._users, "users")

    @property
    def api_keys(self) -> ApiKeyRepository:
        """Repository for ApiKey persistence."""
        return self._require_connected(self._api_keys, "api_keys")

    @property
    def checkpoints(self) -> CheckpointRepository:
        """Repository for Checkpoint persistence."""
        return self._require_connected(self._checkpoints, "checkpoints")

    @property
    def heartbeats(self) -> HeartbeatRepository:
        """Repository for Heartbeat persistence."""
        return self._require_connected(self._heartbeats, "heartbeats")

    @property
    def agent_states(self) -> AgentStateRepository:
        """Repository for AgentRuntimeState persistence."""
        return self._require_connected(self._agent_states, "agent_states")

    @property
    def settings(self) -> SettingsRepository:
        """Repository for namespaced settings persistence."""
        return self._require_connected(self._settings, "settings")

    @property
    def artifacts(self) -> ArtifactRepository:
        """Repository for Artifact persistence."""
        return self._require_connected(self._artifacts, "artifacts")

    @property
    def projects(self) -> ProjectRepository:
        """Repository for Project persistence."""
        return self._require_connected(self._projects, "projects")

    @property
    def custom_presets(self) -> PersonalityPresetRepository:
        """Repository for custom personality preset persistence."""
        return self._require_connected(self._custom_presets, "custom_presets")

    @property
    def workflow_definitions(self) -> WorkflowDefinitionRepository:
        """Repository for workflow definition persistence."""
        return self._require_connected(
            self._workflow_definitions, "workflow_definitions"
        )

    @property
    def workflow_executions(self) -> WorkflowExecutionRepository:
        """Repository for workflow execution persistence."""
        return self._require_connected(self._workflow_executions, "workflow_executions")

    @property
    def workflow_versions(self) -> VersionRepository[WorkflowDefinition]:
        """Repository for workflow definition version persistence."""
        return self._require_connected(self._workflow_versions, "workflow_versions")

    @property
    def identity_versions(self) -> VersionRepository[AgentIdentity]:
        """Repository for AgentIdentity version snapshot persistence."""
        return self._require_connected(self._identity_versions, "identity_versions")

    @property
    def evaluation_config_versions(
        self,
    ) -> VersionRepository[EvaluationConfig]:
        """Repository for EvaluationConfig version snapshot persistence."""
        return self._require_connected(
            self._evaluation_config_versions, "evaluation_config_versions"
        )

    @property
    def budget_config_versions(self) -> VersionRepository[BudgetConfig]:
        """Repository for BudgetConfig version snapshot persistence."""
        return self._require_connected(
            self._budget_config_versions, "budget_config_versions"
        )

    @property
    def company_versions(self) -> VersionRepository[Company]:
        """Repository for Company version snapshot persistence."""
        return self._require_connected(self._company_versions, "company_versions")

    @property
    def role_versions(self) -> VersionRepository[Role]:
        """Repository for Role version snapshot persistence."""
        return self._require_connected(self._role_versions, "role_versions")

    @property
    def risk_overrides(self) -> RiskOverrideRepository:
        """Repository for risk tier override persistence."""
        return self._require_connected(self._risk_overrides, "risk_overrides")

    @property
    def ssrf_violations(self) -> SsrfViolationRepository:
        """Repository for SSRF violation record persistence."""
        return self._require_connected(self._ssrf_violations, "ssrf_violations")

    @property
    def circuit_breaker_state(self) -> CircuitBreakerStateRepository:
        """Repository for circuit breaker state persistence."""
        return self._require_connected(
            self._circuit_breaker_state, "circuit_breaker_state"
        )

    @property
    def project_cost_aggregates(self) -> PostgresProjectCostAggregateRepository:
        """Repository for durable project cost aggregates.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._project_cost_aggregates,
            "project_cost_aggregates",
        )

    async def get_setting(self, key: NotBlankStr) -> str | None:
        """Retrieve a setting value by key from the ``_system`` namespace.

        Delegates to ``self.settings`` (the ``SettingsRepository``).

        Raises:
            PersistenceConnectionError: If not connected or settings
                repository is not yet ported.
        """
        result = await self.settings.get(NotBlankStr("_system"), key)
        return result[0] if result is not None else None

    async def set_setting(self, key: NotBlankStr, value: str) -> None:
        """Store a setting value (upsert) in the ``_system`` namespace.

        Delegates to ``self.settings`` (the ``SettingsRepository``).

        Raises:
            PersistenceConnectionError: If not connected or settings
                repository is not yet ported.
        """
        updated_at = datetime.now(UTC)
        await self.settings.set(
            NotBlankStr("_system"),
            key,
            value,
            updated_at.isoformat(),
        )


# Public re-export for convenience.
__all__ = ["PostgresPersistenceBackend", "dict_row"]
