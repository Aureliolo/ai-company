"""Repository protocol for durable per-project cost aggregates.

Lives under ``persistence/`` (not ``budget/``) because every durable
feature that ``PersistenceBackend`` exposes must define its repository
Protocol in ``persistence/<domain>_protocol.py`` per project convention.

The value object (:class:`ProjectCostAggregate`) stays in
``budget/project_cost_aggregate`` because budget code consumes it.
"""

from typing import Protocol, runtime_checkable

from synthorg.budget.project_cost_aggregate import (
    ProjectCostAggregate,  # noqa: TC001
)
from synthorg.core.types import NotBlankStr  # noqa: TC001


@runtime_checkable
class ProjectCostAggregateRepository(Protocol):
    """Repository for durable per-project cost aggregates.

    Implementations must provide atomic increment semantics so
    concurrent cost recordings do not lose updates, and enforce the
    same-currency invariant so a project's totals cannot silently mix
    currencies.
    """

    async def get(
        self,
        project_id: NotBlankStr,
    ) -> ProjectCostAggregate | None:
        """Retrieve the aggregate for a project.

        Returns:
            The aggregate, or ``None`` if no costs have been recorded.
        """
        ...

    async def increment(
        self,
        project_id: NotBlankStr,
        cost: float,
        input_tokens: int,
        output_tokens: int,
        *,
        currency: NotBlankStr,
    ) -> ProjectCostAggregate:
        """Atomically increment the project's cost aggregate.

        Creates a new aggregate row on the first call for a project.
        Subsequent calls increment the existing totals. Implementations
        MUST raise ``MixedCurrencyAggregationError`` when *currency*
        differs from the aggregate's persisted currency.

        Raises:
            MixedCurrencyAggregationError: If *currency* differs from
                the aggregate's existing currency.
        """
        ...
