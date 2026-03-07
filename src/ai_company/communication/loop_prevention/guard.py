"""Delegation guard orchestrating all loop prevention mechanisms."""

from ai_company.communication.config import LoopPreventionConfig  # noqa: TC001
from ai_company.communication.loop_prevention.ancestry import check_ancestry
from ai_company.communication.loop_prevention.circuit_breaker import (
    DelegationCircuitBreaker,
)
from ai_company.communication.loop_prevention.dedup import (
    DelegationDeduplicator,
)
from ai_company.communication.loop_prevention.depth import (
    check_delegation_depth,
)
from ai_company.communication.loop_prevention.models import GuardCheckOutcome
from ai_company.communication.loop_prevention.rate_limit import (
    DelegationRateLimiter,
)
from ai_company.observability import get_logger
from ai_company.observability.events.delegation import (
    DELEGATION_LOOP_BLOCKED,
)

logger = get_logger(__name__)

_SUCCESS_MECHANISM = "all_passed"


class DelegationGuard:
    """Orchestrates all five loop prevention mechanisms.

    Checks run in order: ancestry, depth, dedup, rate_limit,
    circuit_breaker. Returns the first failure or an overall success.

    Args:
        config: Loop prevention configuration.
    """

    __slots__ = (
        "_circuit_breaker",
        "_config",
        "_deduplicator",
        "_rate_limiter",
    )

    def __init__(self, config: LoopPreventionConfig) -> None:
        self._config = config
        self._deduplicator = DelegationDeduplicator(
            window_seconds=config.dedup_window_seconds,
        )
        self._rate_limiter = DelegationRateLimiter(config.rate_limit)
        self._circuit_breaker = DelegationCircuitBreaker(
            config.circuit_breaker,
        )

    def check(
        self,
        delegation_chain: tuple[str, ...],
        delegator_id: str,
        delegatee_id: str,
        task_title: str,
    ) -> GuardCheckOutcome:
        """Run all loop prevention checks.

        Returns the first failing outcome, or a success outcome if
        all checks pass.

        Args:
            delegation_chain: Current delegation ancestry.
            delegator_id: ID of the delegating agent.
            delegatee_id: ID of the proposed delegatee.
            task_title: Title of the task being delegated.

        Returns:
            First failing outcome or an all-passed success.
        """
        checks = [
            check_ancestry(delegation_chain, delegatee_id),
            check_delegation_depth(delegation_chain, self._config.max_delegation_depth),
            self._deduplicator.check(delegator_id, delegatee_id, task_title),
            self._rate_limiter.check(delegator_id, delegatee_id),
            self._circuit_breaker.check(delegator_id, delegatee_id),
        ]
        for outcome in checks:
            if not outcome.passed:
                logger.info(
                    DELEGATION_LOOP_BLOCKED,
                    mechanism=outcome.mechanism,
                    delegator=delegator_id,
                    delegatee=delegatee_id,
                    message=outcome.message,
                )
                return outcome
        return GuardCheckOutcome(
            passed=True,
            mechanism=_SUCCESS_MECHANISM,
        )

    def record_delegation(
        self,
        delegator_id: str,
        delegatee_id: str,
        task_title: str,
    ) -> None:
        """Record a successful delegation in all stateful mechanisms.

        Args:
            delegator_id: ID of the delegating agent.
            delegatee_id: ID of the target agent.
            task_title: Title of the delegated task.
        """
        self._deduplicator.record(delegator_id, delegatee_id, task_title)
        self._rate_limiter.record(delegator_id, delegatee_id)
        self._circuit_breaker.record_bounce(delegator_id, delegatee_id)
