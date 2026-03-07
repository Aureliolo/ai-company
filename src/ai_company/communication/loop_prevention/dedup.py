"""Delegation deduplication within a time window."""

import time
from collections.abc import Callable  # noqa: TC003

from ai_company.communication.loop_prevention.models import GuardCheckOutcome
from ai_company.observability import get_logger
from ai_company.observability.events.delegation import (
    DELEGATION_LOOP_DEDUP_BLOCKED,
)

logger = get_logger(__name__)

_MECHANISM = "dedup"


class DelegationDeduplicator:
    """Rejects duplicate (delegator, delegatee, task_title) within a window.

    Args:
        window_seconds: Duration of the dedup window.
        clock: Monotonic clock function for deterministic testing.
    """

    __slots__ = ("_clock", "_records", "_window_seconds")

    def __init__(
        self,
        window_seconds: int = 60,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window_seconds = window_seconds
        self._clock = clock
        self._records: dict[tuple[str, str, str], float] = {}

    def check(
        self,
        delegator_id: str,
        delegatee_id: str,
        task_title: str,
    ) -> GuardCheckOutcome:
        """Check for duplicate delegation within the window.

        Args:
            delegator_id: ID of the delegating agent.
            delegatee_id: ID of the target agent.
            task_title: Title of the task being delegated.

        Returns:
            Outcome with passed=False if a duplicate exists.
        """
        key = (delegator_id, delegatee_id, task_title)
        recorded_at = self._records.get(key)
        if recorded_at is not None:
            elapsed = self._clock() - recorded_at
            if elapsed < self._window_seconds:
                logger.info(
                    DELEGATION_LOOP_DEDUP_BLOCKED,
                    delegator=delegator_id,
                    delegatee=delegatee_id,
                    task_title=task_title,
                    elapsed=elapsed,
                    window=self._window_seconds,
                )
                return GuardCheckOutcome(
                    passed=False,
                    mechanism=_MECHANISM,
                    message=(
                        f"Duplicate delegation "
                        f"({delegator_id!r} -> {delegatee_id!r}, "
                        f"{task_title!r}) within "
                        f"{self._window_seconds}s window"
                    ),
                )
        return GuardCheckOutcome(passed=True, mechanism=_MECHANISM)

    def record(
        self,
        delegator_id: str,
        delegatee_id: str,
        task_title: str,
    ) -> None:
        """Record a delegation for future dedup checks.

        Args:
            delegator_id: ID of the delegating agent.
            delegatee_id: ID of the target agent.
            task_title: Title of the task being delegated.
        """
        key = (delegator_id, delegatee_id, task_title)
        self._records[key] = self._clock()
