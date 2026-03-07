"""Circuit breaker for delegation bounces between agent pairs."""

import time
from collections.abc import Callable  # noqa: TC003
from enum import StrEnum

from ai_company.communication.config import CircuitBreakerConfig  # noqa: TC001
from ai_company.communication.loop_prevention.models import GuardCheckOutcome
from ai_company.observability import get_logger
from ai_company.observability.events.delegation import (
    DELEGATION_LOOP_CIRCUIT_OPEN,
)

logger = get_logger(__name__)

_MECHANISM = "circuit_breaker"


class CircuitBreakerState(StrEnum):
    """State of the circuit breaker for an agent pair.

    Members:
        CLOSED: Normal operation, delegations allowed.
        OPEN: Blocked, cooldown period active.
    """

    CLOSED = "closed"
    OPEN = "open"


def _pair_key(a: str, b: str) -> tuple[str, str]:
    """Create a canonical sorted key for an agent pair."""
    return (min(a, b), max(a, b))


class _PairState:
    """Internal mutable state for a single agent pair."""

    __slots__ = ("bounce_count", "opened_at")

    def __init__(self) -> None:
        self.bounce_count: int = 0
        self.opened_at: float | None = None


class DelegationCircuitBreaker:
    """Tracks delegation bounces per sorted agent pair.

    After ``bounce_threshold`` bounces between the same pair, the
    circuit opens for ``cooldown_seconds``. While open, all delegation
    checks for that pair fail.

    Args:
        config: Circuit breaker configuration.
        clock: Monotonic clock function for deterministic testing.
    """

    __slots__ = ("_clock", "_config", "_pairs")

    def __init__(
        self,
        config: CircuitBreakerConfig,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._clock = clock
        self._pairs: dict[tuple[str, str], _PairState] = {}

    def _get_pair(
        self,
        delegator_id: str,
        delegatee_id: str,
    ) -> _PairState:
        key = _pair_key(delegator_id, delegatee_id)
        if key not in self._pairs:
            self._pairs[key] = _PairState()
        return self._pairs[key]

    def get_state(
        self,
        delegator_id: str,
        delegatee_id: str,
    ) -> CircuitBreakerState:
        """Get the circuit breaker state for an agent pair.

        Args:
            delegator_id: First agent ID.
            delegatee_id: Second agent ID.

        Returns:
            Current state of the circuit breaker.
        """
        pair = self._get_pair(delegator_id, delegatee_id)
        if pair.opened_at is not None:
            elapsed = self._clock() - pair.opened_at
            if elapsed < self._config.cooldown_seconds:
                return CircuitBreakerState.OPEN
            # Cooldown expired: reset
            pair.bounce_count = 0
            pair.opened_at = None
        return CircuitBreakerState.CLOSED

    def check(
        self,
        delegator_id: str,
        delegatee_id: str,
    ) -> GuardCheckOutcome:
        """Check whether delegation is allowed for this pair.

        Args:
            delegator_id: ID of the delegating agent.
            delegatee_id: ID of the target agent.

        Returns:
            Outcome with passed=False if circuit is open.
        """
        state = self.get_state(delegator_id, delegatee_id)
        if state is CircuitBreakerState.OPEN:
            logger.info(
                DELEGATION_LOOP_CIRCUIT_OPEN,
                delegator=delegator_id,
                delegatee=delegatee_id,
            )
            return GuardCheckOutcome(
                passed=False,
                mechanism=_MECHANISM,
                message=(
                    f"Circuit breaker open for pair "
                    f"({delegator_id!r}, {delegatee_id!r}); "
                    f"cooldown {self._config.cooldown_seconds}s"
                ),
            )
        return GuardCheckOutcome(passed=True, mechanism=_MECHANISM)

    def record_bounce(
        self,
        delegator_id: str,
        delegatee_id: str,
    ) -> None:
        """Record a delegation bounce for the pair.

        If the bounce count reaches the threshold, opens the circuit.

        Args:
            delegator_id: First agent ID.
            delegatee_id: Second agent ID.
        """
        pair = self._get_pair(delegator_id, delegatee_id)
        # If cooldown expired, get_state already reset
        self.get_state(delegator_id, delegatee_id)
        pair.bounce_count += 1
        if pair.bounce_count >= self._config.bounce_threshold:
            pair.opened_at = self._clock()
