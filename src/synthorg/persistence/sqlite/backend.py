"""SQLite persistence backend implementation."""

import asyncio
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiosqlite

from synthorg.core.types import NotBlankStr
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
from synthorg.persistence.sqlite.audit_repository import (
    SQLiteAuditRepository,
)
from synthorg.persistence.sqlite.checkpoint_repo import (
    SQLiteCheckpointRepository,
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
from synthorg.persistence.sqlite.repositories import (
    SQLiteCostRecordRepository,
    SQLiteMessageRepository,
    SQLiteTaskRepository,
)
from synthorg.persistence.sqlite.settings_repo import (
    SQLiteSettingsRepository,
)
from synthorg.persistence.sqlite.user_repo import (
    SQLiteApiKeyRepository,
    SQLiteUserRepository,
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
        self._db: aiosqlite.Connection | None = None
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

    def _clear_state(self) -> None:
        """Reset connection and repository references to ``None``."""
        self._db = None
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

    def _create_repositories(self) -> None:
        """Instantiate all repository objects from the active connection."""
        assert self._db is not None  # noqa: S101
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
