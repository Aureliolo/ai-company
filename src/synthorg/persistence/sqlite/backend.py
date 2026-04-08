"""SQLite persistence backend implementation."""

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiosqlite
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
    PERSISTENCE_BACKEND_WAL_MODE_FAILED,
)
from synthorg.persistence.errors import PersistenceConnectionError
from synthorg.persistence.sqlite.agent_state_repo import (
    SQLiteAgentStateRepository,
)
from synthorg.persistence.sqlite.artifact_repo import (
    SQLiteArtifactRepository,
)
from synthorg.persistence.sqlite.audit_repository import (
    SQLiteAuditRepository,
)
from synthorg.persistence.sqlite.checkpoint_repo import (
    SQLiteCheckpointRepository,
)
from synthorg.persistence.sqlite.circuit_breaker_repo import (
    SQLiteCircuitBreakerStateRepository,
)
from synthorg.persistence.sqlite.decision_repo import (
    SQLiteDecisionRepository,
)
from synthorg.persistence.sqlite.heartbeat_repo import (
    SQLiteHeartbeatRepository,
)
from synthorg.persistence.sqlite.hr_repositories import (
    SQLiteCollaborationMetricRepository,
    SQLiteLifecycleEventRepository,
    SQLiteTaskMetricRepository,
)
from synthorg.persistence.sqlite.migrations import apply_schema
from synthorg.persistence.sqlite.parked_context_repo import (
    SQLiteParkedContextRepository,
)
from synthorg.persistence.sqlite.preset_repo import (
    SQLitePersonalityPresetRepository,
)
from synthorg.persistence.sqlite.project_cost_aggregate_repo import (
    SQLiteProjectCostAggregateRepository,
)
from synthorg.persistence.sqlite.project_repo import (
    SQLiteProjectRepository,
)
from synthorg.persistence.sqlite.repositories import (
    SQLiteCostRecordRepository,
    SQLiteMessageRepository,
    SQLiteTaskRepository,
)
from synthorg.persistence.sqlite.risk_override_repo import (
    SQLiteRiskOverrideRepository,
)
from synthorg.persistence.sqlite.settings_repo import (
    SQLiteSettingsRepository,
)
from synthorg.persistence.sqlite.ssrf_violation_repo import (
    SQLiteSsrfViolationRepository,
)
from synthorg.persistence.sqlite.user_repo import (
    SQLiteApiKeyRepository,
    SQLiteUserRepository,
)
from synthorg.persistence.sqlite.version_repo import SQLiteVersionRepository
from synthorg.persistence.sqlite.workflow_definition_repo import (
    SQLiteWorkflowDefinitionRepository,
)
from synthorg.persistence.sqlite.workflow_execution_repo import (
    SQLiteWorkflowExecutionRepository,
)

if TYPE_CHECKING:
    from synthorg.persistence.config import SQLiteConfig

logger = get_logger(__name__)


class SQLitePersistenceBackend:
    """SQLite implementation of the PersistenceBackend protocol.

    Uses a single ``aiosqlite.Connection`` with WAL mode enabled by
    default for file-based databases (in-memory databases do not
    support WAL).  Configurable via ``SQLiteConfig.wal_mode``.

    Args:
        config: SQLite-specific configuration.
    """

    def __init__(self, config: SQLiteConfig) -> None:
        self._config = config
        self._lifecycle_lock = asyncio.Lock()
        # Shared write lock for multi-statement transactions on the
        # single aiosqlite connection.  Repositories that perform
        # INSERT/UPDATE/DELETE + commit sequences should acquire this
        # lock around their critical section so one repo's rollback
        # cannot wipe another repo's in-flight changes.  Currently
        # injected into SQLiteDecisionRepository (the primary
        # audit-integrity-critical writer); broader rollout to other
        # repositories is tracked as a follow-up.
        self._shared_write_lock = asyncio.Lock()
        self._db: aiosqlite.Connection | None = None
        self._artifacts: SQLiteArtifactRepository | None = None
        self._projects: SQLiteProjectRepository | None = None
        self._tasks: SQLiteTaskRepository | None = None
        self._cost_records: SQLiteCostRecordRepository | None = None
        self._messages: SQLiteMessageRepository | None = None
        self._lifecycle_events: SQLiteLifecycleEventRepository | None = None
        self._task_metrics: SQLiteTaskMetricRepository | None = None
        self._collaboration_metrics: SQLiteCollaborationMetricRepository | None = None
        self._parked_contexts: SQLiteParkedContextRepository | None = None
        self._audit_entries: SQLiteAuditRepository | None = None
        self._users: SQLiteUserRepository | None = None
        self._api_keys: SQLiteApiKeyRepository | None = None
        self._checkpoints: SQLiteCheckpointRepository | None = None
        self._heartbeats: SQLiteHeartbeatRepository | None = None
        self._agent_states: SQLiteAgentStateRepository | None = None
        self._settings: SQLiteSettingsRepository | None = None
        self._custom_presets: SQLitePersonalityPresetRepository | None = None
        self._workflow_definitions: SQLiteWorkflowDefinitionRepository | None = None
        self._workflow_executions: SQLiteWorkflowExecutionRepository | None = None
        self._workflow_versions: SQLiteVersionRepository[WorkflowDefinition] | None = (
            None
        )
        self._identity_versions: SQLiteVersionRepository[AgentIdentity] | None = None
        self._evaluation_config_versions: (
            SQLiteVersionRepository[EvaluationConfig] | None
        ) = None
        self._budget_config_versions: SQLiteVersionRepository[BudgetConfig] | None = (
            None
        )
        self._company_versions: SQLiteVersionRepository[Company] | None = None
        self._role_versions: SQLiteVersionRepository[Role] | None = None
        self._decision_records: SQLiteDecisionRepository | None = None
        self._risk_overrides: SQLiteRiskOverrideRepository | None = None
        self._ssrf_violations: SQLiteSsrfViolationRepository | None = None
        self._circuit_breaker_state: SQLiteCircuitBreakerStateRepository | None = None
        self._project_cost_aggregates: SQLiteProjectCostAggregateRepository | None = (
            None
        )

    def _clear_state(self) -> None:
        """Reset connection and repository references to ``None``."""
        self._db = None
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

    async def connect(self) -> None:
        """Open the SQLite database and configure WAL mode."""
        async with self._lifecycle_lock:
            if self._db is not None:
                logger.debug(PERSISTENCE_BACKEND_ALREADY_CONNECTED)
                return

            logger.info(
                PERSISTENCE_BACKEND_CONNECTING,
                path=self._config.path,
            )
            try:
                self._db = await aiosqlite.connect(self._config.path)
                self._db.row_factory = aiosqlite.Row

                # Enable foreign key enforcement (off by default in SQLite).
                await self._db.execute("PRAGMA foreign_keys = ON")

                if self._config.wal_mode:
                    await self._configure_wal()

                self._create_repositories()
            except (sqlite3.Error, OSError) as exc:
                await self._cleanup_failed_connect(exc)

            logger.info(
                PERSISTENCE_BACKEND_CONNECTED,
                path=self._config.path,
            )

    async def _configure_wal(self) -> None:
        """Configure WAL journal mode and size limit.

        Must only be called when ``self._db`` is not ``None``.
        """
        assert self._db is not None  # noqa: S101
        cursor = await self._db.execute("PRAGMA journal_mode=WAL")
        row = await cursor.fetchone()
        actual_mode = row[0] if row else "unknown"
        if actual_mode != "wal" and self._config.path != ":memory:":
            logger.warning(
                PERSISTENCE_BACKEND_WAL_MODE_FAILED,
                requested="wal",
                actual=actual_mode,
            )
        # PRAGMA does not support parameterized queries;
        # journal_size_limit is validated as int >= 0 by Pydantic.
        limit = int(self._config.journal_size_limit)
        await self._db.execute(f"PRAGMA journal_size_limit={limit}")

    def get_db(self) -> aiosqlite.Connection:
        """Return the shared database connection.

        Raises:
            PersistenceConnectionError: If not yet connected.
        """
        if self._db is None:
            msg = "Database not connected"
            raise PersistenceConnectionError(msg)
        return self._db

    def _create_repositories(self) -> None:
        """Instantiate all repository objects from the active connection."""
        assert self._db is not None  # noqa: S101
        self._artifacts = SQLiteArtifactRepository(self._db)
        self._projects = SQLiteProjectRepository(self._db)
        self._tasks = SQLiteTaskRepository(self._db)
        self._cost_records = SQLiteCostRecordRepository(self._db)
        self._messages = SQLiteMessageRepository(self._db)
        self._lifecycle_events = SQLiteLifecycleEventRepository(self._db)
        self._task_metrics = SQLiteTaskMetricRepository(self._db)
        self._collaboration_metrics = SQLiteCollaborationMetricRepository(self._db)
        self._parked_contexts = SQLiteParkedContextRepository(self._db)
        self._audit_entries = SQLiteAuditRepository(self._db)
        self._users = SQLiteUserRepository(self._db)
        self._api_keys = SQLiteApiKeyRepository(self._db)
        self._checkpoints = SQLiteCheckpointRepository(self._db)
        self._heartbeats = SQLiteHeartbeatRepository(self._db)
        self._agent_states = SQLiteAgentStateRepository(self._db)
        self._settings = SQLiteSettingsRepository(self._db)
        self._custom_presets = SQLitePersonalityPresetRepository(self._db)
        self._workflow_definitions = SQLiteWorkflowDefinitionRepository(self._db)
        self._workflow_executions = SQLiteWorkflowExecutionRepository(self._db)

        def _ver_repo[T: BaseModel](
            table: str,
            model_cls: type[T],
        ) -> SQLiteVersionRepository[T]:
            assert self._db is not None  # noqa: S101
            return SQLiteVersionRepository(
                self._db,
                table_name=table,
                serialize_snapshot=lambda m: json.dumps(
                    m.model_dump(mode="json"),
                ),
                deserialize_snapshot=lambda s: model_cls.model_validate(
                    json.loads(s),
                ),
            )

        self._workflow_versions = _ver_repo(
            "workflow_definition_versions",
            WorkflowDefinition,
        )
        self._identity_versions = _ver_repo(
            "agent_identity_versions",
            AgentIdentity,
        )
        self._evaluation_config_versions = _ver_repo(
            "evaluation_config_versions",
            EvaluationConfig,
        )
        self._budget_config_versions = _ver_repo(
            "budget_config_versions",
            BudgetConfig,
        )
        self._company_versions = _ver_repo(
            "company_versions",
            Company,
        )
        self._role_versions = _ver_repo(
            "role_versions",
            Role,
        )
        self._decision_records = SQLiteDecisionRepository(
            self._db, write_lock=self._shared_write_lock
        )
        self._risk_overrides = SQLiteRiskOverrideRepository(
            self._db,
            write_lock=self._shared_write_lock,
        )
        self._ssrf_violations = SQLiteSsrfViolationRepository(
            self._db,
            write_lock=self._shared_write_lock,
        )
        self._circuit_breaker_state = SQLiteCircuitBreakerStateRepository(
            self._db,
            write_lock=self._shared_write_lock,
        )
        self._project_cost_aggregates = SQLiteProjectCostAggregateRepository(
            self._db,
            write_lock=self._shared_write_lock,
        )

    async def _cleanup_failed_connect(self, exc: sqlite3.Error | OSError) -> None:
        """Log failure, close partial connection, and raise.

        Raises:
            PersistenceConnectionError: Always.
        """
        logger.exception(
            PERSISTENCE_BACKEND_CONNECTION_FAILED,
            path=self._config.path,
            error=str(exc),
        )
        if self._db is not None:
            try:
                await self._db.close()
            except (sqlite3.Error, OSError) as cleanup_exc:
                logger.warning(
                    PERSISTENCE_BACKEND_DISCONNECT_ERROR,
                    path=self._config.path,
                    error=str(cleanup_exc),
                    error_type=type(cleanup_exc).__name__,
                    context="cleanup_after_connect_failure",
                )
        self._clear_state()
        msg = "Failed to connect to persistence backend"
        raise PersistenceConnectionError(msg) from exc

    async def disconnect(self) -> None:
        """Close the database connection."""
        async with self._lifecycle_lock:
            if self._db is None:
                return

            logger.info(PERSISTENCE_BACKEND_DISCONNECTING, path=self._config.path)
            try:
                await self._db.close()
                logger.info(
                    PERSISTENCE_BACKEND_DISCONNECTED,
                    path=self._config.path,
                )
            except (sqlite3.Error, OSError) as exc:
                logger.warning(
                    PERSISTENCE_BACKEND_DISCONNECT_ERROR,
                    path=self._config.path,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            finally:
                self._clear_state()

    async def health_check(self) -> bool:
        """Check database connectivity."""
        if self._db is None:
            return False
        try:
            cursor = await self._db.execute("SELECT 1")
            row = await cursor.fetchone()
            healthy = row is not None
        except (sqlite3.Error, aiosqlite.Error) as exc:
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
        """Apply the database schema.

        Raises:
            PersistenceConnectionError: If not connected.
            MigrationError: If schema application fails.
        """
        if self._db is None:
            msg = "Cannot migrate: not connected"
            logger.warning(PERSISTENCE_BACKEND_NOT_CONNECTED, error=msg)
            raise PersistenceConnectionError(msg)
        await apply_schema(self._db)

    @property
    def is_connected(self) -> bool:
        """Whether the backend has an active connection."""
        return self._db is not None

    @property
    def backend_name(self) -> NotBlankStr:
        """Human-readable backend identifier."""
        return NotBlankStr("sqlite")

    def _require_connected[T](self, repo: T | None, name: str) -> T:
        """Return *repo* or raise if the backend is not connected.

        Args:
            repo: Repository instance (``None`` when disconnected).
            name: Repository name for the error message.

        Raises:
            PersistenceConnectionError: If *repo* is ``None``.
        """
        if repo is None:
            msg = f"Not connected -- call connect() before accessing {name}"
            logger.warning(PERSISTENCE_BACKEND_NOT_CONNECTED, error=msg)
            raise PersistenceConnectionError(msg)
        return repo

    @property
    def tasks(self) -> SQLiteTaskRepository:
        """Repository for Task persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._tasks, "tasks")

    @property
    def cost_records(self) -> SQLiteCostRecordRepository:
        """Repository for CostRecord persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._cost_records, "cost_records")

    @property
    def messages(self) -> SQLiteMessageRepository:
        """Repository for Message persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._messages, "messages")

    @property
    def lifecycle_events(self) -> SQLiteLifecycleEventRepository:
        """Repository for AgentLifecycleEvent persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._lifecycle_events, "lifecycle_events")

    @property
    def task_metrics(self) -> SQLiteTaskMetricRepository:
        """Repository for TaskMetricRecord persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._task_metrics, "task_metrics")

    @property
    def collaboration_metrics(self) -> SQLiteCollaborationMetricRepository:
        """Repository for CollaborationMetricRecord persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._collaboration_metrics, "collaboration_metrics"
        )

    @property
    def parked_contexts(self) -> SQLiteParkedContextRepository:
        """Repository for ParkedContext persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._parked_contexts, "parked_contexts")

    @property
    def audit_entries(self) -> SQLiteAuditRepository:
        """Repository for AuditEntry persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._audit_entries, "audit_entries")

    @property
    def decision_records(self) -> SQLiteDecisionRepository:
        """Repository for DecisionRecord persistence (decisions drop-box).

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._decision_records, "decision_records")

    @property
    def users(self) -> SQLiteUserRepository:
        """Repository for User persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._users, "users")

    @property
    def api_keys(self) -> SQLiteApiKeyRepository:
        """Repository for ApiKey persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._api_keys, "api_keys")

    @property
    def checkpoints(self) -> SQLiteCheckpointRepository:
        """Repository for Checkpoint persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._checkpoints, "checkpoints")

    @property
    def heartbeats(self) -> SQLiteHeartbeatRepository:
        """Repository for Heartbeat persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._heartbeats, "heartbeats")

    @property
    def agent_states(self) -> SQLiteAgentStateRepository:
        """Repository for AgentRuntimeState persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._agent_states, "agent_states")

    @property
    def settings(self) -> SQLiteSettingsRepository:
        """Repository for namespaced settings persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._settings, "settings")

    @property
    def artifacts(self) -> SQLiteArtifactRepository:
        """Repository for Artifact persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._artifacts, "artifacts")

    @property
    def projects(self) -> SQLiteProjectRepository:
        """Repository for Project persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._projects, "projects")

    @property
    def project_cost_aggregates(
        self,
    ) -> SQLiteProjectCostAggregateRepository:
        """Repository for durable project cost aggregates.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._project_cost_aggregates,
            "project_cost_aggregates",
        )

    @property
    def custom_presets(self) -> SQLitePersonalityPresetRepository:
        """Repository for custom personality preset persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(self._custom_presets, "custom_presets")

    @property
    def workflow_definitions(self) -> SQLiteWorkflowDefinitionRepository:
        """Repository for workflow definition persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._workflow_definitions,
            "workflow_definitions",
        )

    @property
    def workflow_executions(self) -> SQLiteWorkflowExecutionRepository:
        """Repository for workflow execution persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._workflow_executions,
            "workflow_executions",
        )

    @property
    def workflow_versions(self) -> SQLiteVersionRepository[WorkflowDefinition]:
        """Repository for workflow definition version persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._workflow_versions,
            "workflow_versions",
        )

    @property
    def identity_versions(self) -> SQLiteVersionRepository[AgentIdentity]:
        """Repository for AgentIdentity version snapshot persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._identity_versions,
            "identity_versions",
        )

    @property
    def evaluation_config_versions(
        self,
    ) -> SQLiteVersionRepository[EvaluationConfig]:
        """Repository for EvaluationConfig version snapshot persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._evaluation_config_versions,
            "evaluation_config_versions",
        )

    @property
    def budget_config_versions(
        self,
    ) -> SQLiteVersionRepository[BudgetConfig]:
        """Repository for BudgetConfig version snapshot persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._budget_config_versions,
            "budget_config_versions",
        )

    @property
    def company_versions(
        self,
    ) -> SQLiteVersionRepository[Company]:
        """Repository for Company version snapshot persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._company_versions,
            "company_versions",
        )

    @property
    def role_versions(
        self,
    ) -> SQLiteVersionRepository[Role]:
        """Repository for Role version snapshot persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._role_versions,
            "role_versions",
        )

    @property
    def risk_overrides(self) -> SQLiteRiskOverrideRepository:
        """Repository for risk tier override persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._risk_overrides,
            "risk_overrides",
        )

    @property
    def ssrf_violations(self) -> SQLiteSsrfViolationRepository:
        """Repository for SSRF violation record persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._ssrf_violations,
            "ssrf_violations",
        )

    @property
    def circuit_breaker_state(self) -> SQLiteCircuitBreakerStateRepository:
        """Repository for circuit breaker state persistence.

        Raises:
            PersistenceConnectionError: If not connected.
        """
        return self._require_connected(
            self._circuit_breaker_state,
            "circuit_breaker_state",
        )

    async def get_setting(self, key: NotBlankStr) -> str | None:
        """Retrieve a setting value by key from the ``_system`` namespace.

        Delegates to ``self.settings`` (the ``SettingsRepository``).

        Raises:
            PersistenceConnectionError: If not connected.
        """
        result = await self.settings.get(NotBlankStr("_system"), key)
        return result[0] if result is not None else None

    async def set_setting(self, key: NotBlankStr, value: str) -> None:
        """Store a setting value (upsert) in the ``_system`` namespace.

        Delegates to ``self.settings`` (the ``SettingsRepository``).

        Raises:
            PersistenceConnectionError: If not connected.
        """
        updated_at = datetime.now(UTC).isoformat()
        await self.settings.set(
            NotBlankStr("_system"),
            key,
            value,
            updated_at,
        )
