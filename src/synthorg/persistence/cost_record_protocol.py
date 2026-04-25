"""CostRecord repository protocol."""

from typing import Protocol, runtime_checkable

from synthorg.budget.cost_record import CostRecord  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001


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
