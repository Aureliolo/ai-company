"""Per-classification-run LLM cost budget tracker.

Simple in-memory tracker that accumulates cost across semantic
detector invocations within a single classification run.  Not
persisted -- one instance per ``classify_execution_errors`` call.
"""

from synthorg.observability import get_logger
from synthorg.observability.events.classification import (
    DETECTOR_BUDGET_EXHAUSTED,
    DETECTOR_COST_INCURRED,
)

logger = get_logger(__name__)


class ClassificationBudgetTracker:
    """Tracks LLM spend within a single classification run.

    Args:
        budget_usd: Maximum allowed spend for this run.
    """

    def __init__(self, budget_usd: float) -> None:
        if budget_usd < 0:
            msg = "budget_usd must be non-negative"
            raise ValueError(msg)
        self._budget_usd = budget_usd
        self._spent_usd = 0.0

    def can_spend(self, estimated_cost: float) -> bool:
        """Check whether the estimated cost fits the remaining budget.

        Args:
            estimated_cost: Estimated cost for the next LLM call.

        Returns:
            True if the call can proceed within budget.
        """
        if estimated_cost < 0:
            msg = "estimated_cost must be non-negative"
            raise ValueError(msg)
        if self._spent_usd + estimated_cost > self._budget_usd:
            logger.info(
                DETECTOR_BUDGET_EXHAUSTED,
                spent_usd=self._spent_usd,
                budget_usd=self._budget_usd,
                estimated_cost=estimated_cost,
            )
            return False
        return True

    def record(self, actual_cost: float) -> None:
        """Record cost from a completed LLM call.

        Args:
            actual_cost: Actual cost of the completed call.
        """
        if actual_cost < 0:
            msg = "actual_cost must be non-negative"
            raise ValueError(msg)
        self._spent_usd += actual_cost
        logger.debug(
            DETECTOR_COST_INCURRED,
            cost_usd=actual_cost,
            total_spent_usd=self._spent_usd,
            remaining_usd=self.remaining_usd,
        )

    @property
    def remaining_usd(self) -> float:
        """Remaining budget in USD."""
        return max(0.0, self._budget_usd - self._spent_usd)

    @property
    def total_spent_usd(self) -> float:
        """Total spent so far in USD."""
        return self._spent_usd
