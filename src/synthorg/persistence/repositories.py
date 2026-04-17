"""Repository protocols for operational data persistence.

Each entity type has its own protocol so that application code depends
only on abstract interfaces, never on a concrete backend.
"""

from collections.abc import Mapping, Sequence  # noqa: TC003
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import AwareDatetime  # noqa: TC002

from synthorg.api.auth.models import ApiKey, User  # noqa: TC001
from synthorg.api.guards import HumanRole  # noqa: TC001
from synthorg.budget.cost_record import CostRecord  # noqa: TC001
from synthorg.communication.message import Message  # noqa: TC001
from synthorg.core.enums import (
    ApprovalRiskLevel,  # noqa: TC001
    TaskStatus,  # noqa: TC001
)
from synthorg.core.task import Task  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.hr.persistence_protocol import (
    CollaborationMetricRepository,
    LifecycleEventRepository,
    TaskMetricRepository,
)
from synthorg.security.models import AuditEntry, AuditVerdictStr  # noqa: TC001
from synthorg.security.timeout.parked_context import ParkedContext  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.engine.agent_state import AgentRuntimeState

__all__ = [
    "AgentStateRepository",
    "ApiKeyRepository",
    "ArtifactRepository",
    "AuditRepository",
    "CheckpointRepository",
    "CollaborationMetricRepository",
    "ConnectionRepository",
    "ConnectionSecretRepository",
    "CostRecordRepository",
    "DecisionRepository",
    "DecisionRole",
    "HeartbeatRepository",
    "LifecycleEventRepository",
    "MessageRepository",
    "OAuthStateRepository",
    "ParkedContextRepository",
    "ProjectRepository",
    "SettingsRepository",
    "TaskMetricRepository",
    "TaskRepository",
    "UserRepository",
    "WebhookReceiptRepository",
]


@runtime_checkable
class TaskRepository(Protocol):
    """CRUD + query interface for Task persistence."""

    async def save(self, task: Task) -> None:
        """Persist a task (insert or update).

        Args:
            task: The task to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, task_id: NotBlankStr) -> Task | None:
        """Retrieve a task by its ID.

        Args:
            task_id: The task identifier.

        Returns:
            The task, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        assigned_to: NotBlankStr | None = None,
        project: NotBlankStr | None = None,
    ) -> tuple[Task, ...]:
        """List tasks with optional filters.

        Args:
            status: Filter by task status.
            assigned_to: Filter by assignee agent ID.
            project: Filter by project ID.

        Returns:
            Matching tasks as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, task_id: NotBlankStr) -> bool:
        """Delete a task by ID.

        Args:
            task_id: The task identifier.

        Returns:
            ``True`` if the task was deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class CostRecordRepository(Protocol):
    """Append-only persistence + query/aggregation for CostRecord."""

    async def save(self, record: CostRecord) -> None:
        """Persist a cost record (append-only).

        Args:
            record: The cost record to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def query(
        self,
        *,
        agent_id: NotBlankStr | None = None,
        task_id: NotBlankStr | None = None,
    ) -> tuple[CostRecord, ...]:
        """Query cost records with optional filters.

        Args:
            agent_id: Filter by agent identifier.
            task_id: Filter by task identifier.

        Returns:
            Matching cost records as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def aggregate(
        self,
        *,
        agent_id: NotBlankStr | None = None,
        task_id: NotBlankStr | None = None,
    ) -> float:
        """Sum total cost, optionally filtered by agent and/or task.

        Args:
            agent_id: Filter by agent identifier.
            task_id: Filter by task identifier.

        Returns:
            Total cost in the configured currency.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class MessageRepository(Protocol):
    """Write + history query interface for Message persistence."""

    async def save(self, message: Message) -> None:
        """Persist a message.

        Args:
            message: The message to persist.

        Raises:
            DuplicateRecordError: If a message with the same ID exists.
            PersistenceError: If the operation fails.
        """
        ...

    async def get_history(
        self,
        channel: NotBlankStr,
        *,
        limit: int | None = None,
    ) -> tuple[Message, ...]:
        """Retrieve message history for a channel.

        Args:
            channel: Channel name to query.
            limit: Maximum number of messages to return (newest first).

        Returns:
            Messages ordered by timestamp descending.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class ParkedContextRepository(Protocol):
    """CRUD interface for parked agent execution contexts."""

    async def save(self, context: ParkedContext) -> None:
        """Persist a parked context.

        Args:
            context: The parked context to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, parked_id: NotBlankStr) -> ParkedContext | None:
        """Retrieve a parked context by ID.

        Args:
            parked_id: The parked context identifier.

        Returns:
            The parked context, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_by_approval(self, approval_id: NotBlankStr) -> ParkedContext | None:
        """Retrieve a parked context by approval ID.

        Args:
            approval_id: The approval item identifier.

        Returns:
            The parked context, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_by_agent(self, agent_id: NotBlankStr) -> tuple[ParkedContext, ...]:
        """Retrieve all parked contexts for an agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            Parked contexts for the agent.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, parked_id: NotBlankStr) -> bool:
        """Delete a parked context by ID.

        Args:
            parked_id: The parked context identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class AuditRepository(Protocol):
    """Append-only persistence + query interface for AuditEntry.

    Audit entries are immutable records of security evaluations.
    No update or delete operations are provided to preserve audit
    integrity.
    """

    async def save(self, entry: AuditEntry) -> None:
        """Persist an audit entry (append-only).

        Args:
            entry: The audit entry to persist.

        Raises:
            DuplicateRecordError: If an entry with the same ID exists.
            QueryError: If the operation fails.
        """
        ...

    async def query(  # noqa: PLR0913
        self,
        *,
        agent_id: NotBlankStr | None = None,
        action_type: str | None = None,
        verdict: AuditVerdictStr | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        since: AwareDatetime | None = None,
        until: AwareDatetime | None = None,
        limit: int = 100,
    ) -> tuple[AuditEntry, ...]:
        """Query audit entries with optional filters.

        Filters are AND-combined. Results are ordered by timestamp
        descending (newest first).

        Args:
            agent_id: Filter by agent identifier.
            action_type: Filter by action type string.
            verdict: Filter by verdict string.
            risk_level: Filter by risk level.
            since: Only return entries at or after this timestamp.
            until: Only return entries at or before this timestamp.
            limit: Maximum number of entries to return (must be >= 1).

        Returns:
            Matching audit entries as a tuple.

        Raises:
            QueryError: If the operation fails, *limit* < 1, or
                *until* is earlier than *since*.
        """
        ...


@runtime_checkable
class UserRepository(Protocol):
    """CRUD interface for User persistence."""

    async def save(self, user: User) -> None:
        """Persist a user (insert or update).

        Args:
            user: The user to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, user_id: NotBlankStr) -> User | None:
        """Retrieve a user by ID.

        Args:
            user_id: The user identifier.

        Returns:
            The user, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_by_username(self, username: NotBlankStr) -> User | None:
        """Retrieve a user by username.

        Args:
            username: The login username.

        Returns:
            The user, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def list_users(self) -> tuple[User, ...]:
        """List all human users (excludes the system user).

        Returns:
            Human users as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def count(self) -> int:
        """Count the number of human users (excludes the system user).

        Returns:
            Human user count.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def count_by_role(self, role: HumanRole) -> int:
        """Count users with a specific role.

        Args:
            role: The role to filter by.

        Returns:
            Number of users with the given role.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, user_id: NotBlankStr) -> bool:
        """Delete a user by ID.

        Args:
            user_id: The user identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class ApiKeyRepository(Protocol):
    """CRUD interface for API key persistence."""

    async def save(self, key: ApiKey) -> None:
        """Persist an API key.

        Args:
            key: The API key to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, key_id: NotBlankStr) -> ApiKey | None:
        """Retrieve an API key by ID.

        Args:
            key_id: The key identifier.

        Returns:
            The API key, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_by_hash(self, key_hash: NotBlankStr) -> ApiKey | None:
        """Retrieve an API key by its hash.

        Args:
            key_hash: HMAC-SHA256 hex digest.

        Returns:
            The API key, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def list_by_user(self, user_id: NotBlankStr) -> tuple[ApiKey, ...]:
        """List API keys belonging to a user.

        Args:
            user_id: The owner user ID.

        Returns:
            API keys for the user.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, key_id: NotBlankStr) -> bool:
        """Delete an API key by ID.

        Args:
            key_id: The key identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class AgentStateRepository(Protocol):
    """CRUD + query interface for agent runtime state persistence.

    Provides a lightweight per-agent registry of execution state for
    dashboard queries, graceful shutdown discovery, and cross-restart
    recovery.
    """

    async def save(self, state: AgentRuntimeState) -> None:
        """Upsert an agent runtime state by ``agent_id``.

        Args:
            state: The agent runtime state to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, agent_id: NotBlankStr) -> AgentRuntimeState | None:
        """Retrieve an agent runtime state by agent ID.

        Args:
            agent_id: The agent identifier.

        Returns:
            The agent state, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_active(self) -> tuple[AgentRuntimeState, ...]:
        """Retrieve all non-idle agent states.

        Returns states where ``status != 'idle'``, ordered by
        ``last_activity_at`` descending (most recent first).

        Returns:
            Active agent states as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, agent_id: NotBlankStr) -> bool:
        """Delete an agent runtime state by agent ID.

        Args:
            agent_id: The agent identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class SettingsRepository(Protocol):
    """CRUD interface for namespaced settings persistence.

    Settings are stored as ``(namespace, key)`` composite-keyed
    string values with ``updated_at`` timestamps.
    """

    async def get(
        self,
        namespace: NotBlankStr,
        key: NotBlankStr,
    ) -> tuple[str, str] | None:
        """Retrieve a setting value and its timestamp.

        Args:
            namespace: Setting namespace.
            key: Setting key within the namespace.

        Returns:
            ``(value, updated_at)`` tuple, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_namespace(
        self,
        namespace: NotBlankStr,
    ) -> tuple[tuple[str, str, str], ...]:
        """Retrieve all settings in a namespace.

        Args:
            namespace: Setting namespace.

        Returns:
            Tuple of ``(key, value, updated_at)`` tuples, sorted by key.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_all(self) -> tuple[tuple[str, str, str, str], ...]:
        """Retrieve all settings across all namespaces.

        Returns:
            Tuple of ``(namespace, key, value, updated_at)`` tuples,
            sorted by namespace then key.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def set(
        self,
        namespace: NotBlankStr,
        key: NotBlankStr,
        value: str,
        updated_at: str,
        *,
        expected_updated_at: str | None = None,
    ) -> bool:
        """Upsert a setting value.

        Args:
            namespace: Setting namespace.
            key: Setting key within the namespace.
            value: Setting value as a string.
            updated_at: ISO 8601 timestamp of the change.
            expected_updated_at: When provided, the row is only
                updated if the current ``updated_at`` matches
                (atomic compare-and-swap).

        Returns:
            ``True`` if the write succeeded.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def set_many(
        self,
        items: Sequence[tuple[NotBlankStr, NotBlankStr, str, str]],
        *,
        expected_updated_at_map: (Mapping[tuple[str, str], str] | None) = None,
    ) -> bool:
        """Atomically upsert multiple settings in a single transaction.

        Each element of ``items`` is ``(namespace, key, value,
        updated_at)``.  ``expected_updated_at_map`` optionally supplies
        a compare-and-swap expected version per ``(namespace, key)``;
        keys absent from the map are upserted unconditionally.  Pass
        an empty string ``""`` in the map for first-write CAS
        semantics (the row must not exist yet).

        The whole operation is atomic: if any CAS check fails, the
        transaction rolls back and no rows are modified.

        Returns:
            ``True`` if every write succeeded.  ``False`` if any CAS
            check failed -- callers should re-read versions and retry
            if they need to recover.

        Raises:
            PersistenceError: On DB-level failures (not CAS misses).
        """
        ...

    async def delete(
        self,
        namespace: NotBlankStr,
        key: NotBlankStr,
    ) -> bool:
        """Delete a setting.

        Args:
            namespace: Setting namespace.
            key: Setting key within the namespace.

        Returns:
            ``True`` if the setting was deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete_namespace(self, namespace: NotBlankStr) -> int:
        """Delete all settings in a namespace.

        Args:
            namespace: Setting namespace.

        Returns:
            Number of settings deleted.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


# ArtifactRepository, ProjectRepository, DecisionRepository, DecisionRole,
# CheckpointRepository, and HeartbeatRepository live in separate modules
# to keep this file under the 800-line limit.  Re-exported here for
# backwards-compatible imports.
from synthorg.persistence.artifact_project_repos import (  # noqa: E402, I001
    ArtifactRepository as ArtifactRepository,  # noqa: PLC0414
    ProjectRepository as ProjectRepository,  # noqa: PLC0414
)
from synthorg.persistence.repositories_checkpoint import (  # noqa: E402
    CheckpointRepository as CheckpointRepository,  # noqa: PLC0414
    HeartbeatRepository as HeartbeatRepository,  # noqa: PLC0414
)
from synthorg.persistence.repositories_decisions import (  # noqa: E402
    DecisionRepository as DecisionRepository,  # noqa: PLC0414
    DecisionRole as DecisionRole,  # noqa: PLC0414
)
from synthorg.persistence.repositories_integrations import (  # noqa: E402
    ConnectionRepository as ConnectionRepository,  # noqa: PLC0414
    ConnectionSecretRepository as ConnectionSecretRepository,  # noqa: PLC0414
    OAuthStateRepository as OAuthStateRepository,  # noqa: PLC0414
    WebhookReceiptRepository as WebhookReceiptRepository,  # noqa: PLC0414
)
