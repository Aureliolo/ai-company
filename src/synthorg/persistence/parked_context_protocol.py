"""ParkedContext repository protocol."""

from typing import Protocol, runtime_checkable

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.security.timeout.parked_context import ParkedContext  # noqa: TC001


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
