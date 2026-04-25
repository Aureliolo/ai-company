"""AgentState repository protocol."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from synthorg.core.types import NotBlankStr  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.engine.agent_state import AgentRuntimeState


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
