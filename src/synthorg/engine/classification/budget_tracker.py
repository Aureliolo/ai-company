"""Per-classification-run LLM cost budget tracker.

Simple async-safe in-memory tracker that accumulates cost across
semantic detector invocations within a single classification run.
Not persisted -- one instance per ``classify_execution_errors``
call.  All check-and-reserve operations are guarded by an
``asyncio.Lock`` so concurrent semantic detectors (e.g. siblings in
a ``CompositeDetector``) cannot race through the admission gate
and overspend the budget.
"""

import asyncio

from synthorg.observability import get_logger
from synthorg.observability.events.classification import (
    DETECTOR_BUDGET_EXHAUSTED,
    DETECTOR_COST_INCURRED,
    INVALID_BUDGET,
    INVALID_COST,
)

logger = get_logger(__name__)


class ClassificationBudgetTracker:
    """Tracks LLM spend within a single classification run.

    Provides atomic check-and-reserve admission (``try_reserve``)
    plus settlement of the actual cost once the LLM call completes
    (``settle``).  A legacy split API (``can_spend`` + ``record``)
    is kept for backward compatibility but is implemented on top of
    the atomic primitives under the same lock.

    Args:
        budget_usd: Maximum allowed spend for this run.

    Raises:
        ValueError: If ``budget_usd`` is negative.
    """

    def __init__(self, budget_usd: float) -> None:
        if budget_usd < 0:
            msg = "budget_usd must be non-negative"
            logger.error(
                INVALID_BUDGET,
                budget_usd=budget_usd,
                reason=msg,
            )
            raise ValueError(msg)
        self._budget_usd = budget_usd
        self._spent_usd = 0.0
        self._lock = asyncio.Lock()

    async def try_reserve(self, estimated_cost: float) -> bool:
        """Atomically reserve budget for an upcoming LLM call.

        Acquires the internal lock, checks whether ``estimated_cost``
        fits within the remaining budget, and if so increments
        ``_spent_usd`` by the estimate.  Returns ``True`` when the
        reservation succeeded, ``False`` when the budget is
        exhausted.  The reservation MUST be paired with a call to
        :meth:`settle` once the actual cost is known so the
        difference between estimate and actual can be applied.

        Args:
            estimated_cost: Estimated cost for the next LLM call.

        Returns:
            True when the reservation was recorded, False when the
            call would exceed the remaining budget.

        Raises:
            ValueError: If ``estimated_cost`` is negative.
        """
        if estimated_cost < 0:
            msg = "estimated_cost must be non-negative"
            logger.warning(
                INVALID_COST,
                cost_usd=estimated_cost,
                kind="estimated",
                reason=msg,
            )
            raise ValueError(msg)
        async with self._lock:
            if self._spent_usd + estimated_cost > self._budget_usd:
                logger.info(
                    DETECTOR_BUDGET_EXHAUSTED,
                    spent_usd=self._spent_usd,
                    budget_usd=self._budget_usd,
                    estimated_cost=estimated_cost,
                )
                return False
            self._spent_usd += estimated_cost
            return True

    async def settle(
        self,
        estimated_cost: float,
        actual_cost: float,
    ) -> None:
        """Reconcile a reserved budget slot with the actual cost.

        Adds ``actual_cost - estimated_cost`` to ``_spent_usd``
        under the lock.  The delta may be negative (cheaper than
        expected) or positive (more expensive).  Call this from the
        ``finally`` of an LLM invocation that was previously gated
        via :meth:`try_reserve`.

        Args:
            estimated_cost: The cost that was reserved.
            actual_cost: The actual cost observed.

        Raises:
            ValueError: If ``actual_cost`` is negative.
        """
        if actual_cost < 0:
            msg = "actual_cost must be non-negative"
            logger.warning(
                INVALID_COST,
                cost_usd=actual_cost,
                kind="actual",
                reason=msg,
            )
            raise ValueError(msg)
        delta = actual_cost - estimated_cost
        async with self._lock:
            self._spent_usd += delta
            logger.debug(
                DETECTOR_COST_INCURRED,
                cost_usd=actual_cost,
                estimated_cost=estimated_cost,
                delta_usd=delta,
                total_spent_usd=self._spent_usd,
                remaining_usd=max(0.0, self._budget_usd - self._spent_usd),
            )

    async def release(self, estimated_cost: float) -> None:
        """Release a previously-reserved slot that never incurred cost.

        Use this when ``try_reserve`` succeeded but the provider
        call failed before any cost was incurred (e.g. rate-limiter
        acquisition error, immediate connection failure), so the
        reserved estimate should be refunded.

        Args:
            estimated_cost: The cost that was reserved and is being
                released.  Must be non-negative.

        Raises:
            ValueError: If ``estimated_cost`` is negative.
        """
        if estimated_cost < 0:
            msg = "estimated_cost must be non-negative"
            logger.warning(
                INVALID_COST,
                cost_usd=estimated_cost,
                kind="release",
                reason=msg,
            )
            raise ValueError(msg)
        async with self._lock:
            self._spent_usd = max(0.0, self._spent_usd - estimated_cost)

    async def record(self, actual_cost: float) -> None:
        """Record cost from a completed LLM call without a prior reserve.

        Provided for call sites that bypass ``try_reserve``.  Always
        acquires the lock before mutating ``_spent_usd``.

        Args:
            actual_cost: Actual cost of the completed call.

        Raises:
            ValueError: If ``actual_cost`` is negative.
        """
        if actual_cost < 0:
            msg = "actual_cost must be non-negative"
            logger.warning(
                INVALID_COST,
                cost_usd=actual_cost,
                kind="record",
                reason=msg,
            )
            raise ValueError(msg)
        async with self._lock:
            self._spent_usd += actual_cost
            logger.debug(
                DETECTOR_COST_INCURRED,
                cost_usd=actual_cost,
                total_spent_usd=self._spent_usd,
                remaining_usd=max(0.0, self._budget_usd - self._spent_usd),
            )

    @property
    def remaining_usd(self) -> float:
        """Remaining budget in USD.

        Returns an advisory snapshot -- concurrent callers may see
        stale values.  Use :meth:`try_reserve` for atomic admission.
        """
        return max(0.0, self._budget_usd - self._spent_usd)

    @property
    def total_spent_usd(self) -> float:
        """Total spent so far in USD (advisory snapshot)."""
        return self._spent_usd
