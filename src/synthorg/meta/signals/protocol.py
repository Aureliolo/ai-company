"""Protocol for signal aggregators.

Each aggregator wraps one existing subsystem and produces a typed
summary model for consumption by the rule engine and strategies.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from synthorg.core.types import NotBlankStr  # noqa: TC001

if TYPE_CHECKING:
    from datetime import datetime

    from synthorg.meta.models import (
        OrgBudgetSummary,
        OrgCoordinationSummary,
        OrgErrorSummary,
        OrgEvolutionSummary,
        OrgPerformanceSummary,
        OrgScalingSummary,
        OrgTelemetrySummary,
    )


@runtime_checkable
class SignalAggregator(Protocol):
    """Aggregates raw signals from a subsystem into a typed summary."""

    @property
    def domain(self) -> NotBlankStr:
        """Signal domain name (e.g. 'performance', 'budget')."""
        ...

    async def aggregate(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> (
        OrgPerformanceSummary
        | OrgBudgetSummary
        | OrgCoordinationSummary
        | OrgScalingSummary
        | OrgErrorSummary
        | OrgEvolutionSummary
        | OrgTelemetrySummary
    ):
        """Collect and aggregate signals for the time window.

        Args:
            since: Start of the observation window (UTC).
            until: End of the observation window (UTC).

        Returns:
            Domain-specific typed summary model.
        """
        ...
