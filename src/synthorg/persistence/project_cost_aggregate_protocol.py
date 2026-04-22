"""Repository protocol for durable per-project cost aggregates.

Lives under ``persistence/`` (not ``budget/``) because every durable
feature that ``PersistenceBackend`` exposes must define its repository
Protocol in ``persistence/<domain>_protocol.py`` per project convention.

The value object (:class:`ProjectCostAggregate`) stays in
``budget/project_cost_aggregate`` because budget code consumes it.

The currency-aware invariant described in CLAUDE.md (cost-bearing
aggregations must reject mixed-currency increments via
``MixedCurrencyAggregationError``) is a separate follow-up: it requires
a schema column migration, a model field, and caller updates in
``CostTracker`` / ``BudgetEnforcer``. This protocol tracks the current
non-currency-aware surface; once the follow-up lands, a ``currency``
parameter will be added to ``increment`` here and the schema column
will be enforced at the repo boundary.
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
    concurrent cost recordings do not lose updates.
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
    ) -> ProjectCostAggregate:
        """Atomically increment the project's cost aggregate.

        Creates a new aggregate row on the first call for a project.
        Subsequent calls increment the existing totals.

        Returns:
            The updated aggregate after the increment.
        """
        ...
