"""Rate limit guard.

Hard cap on the number of scaling actions per rolling window.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_SCALING_GUARD_APPLIED

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.scaling.models import ScalingDecision

logger = get_logger(__name__)


class RateLimitGuard:
    """Global rate limits on scaling actions.

    Drops decisions that would exceed the daily cap for their
    action type.

    Args:
        max_hires_per_day: Maximum hire decisions per 24h window.
        max_prunes_per_day: Maximum prune decisions per 24h window.
    """

    def __init__(
        self,
        *,
        max_hires_per_day: int = 3,
        max_prunes_per_day: int = 1,
    ) -> None:
        self._limits: dict[str, int] = {
            ScalingActionType.HIRE: max_hires_per_day,
            ScalingActionType.PRUNE: max_prunes_per_day,
        }
        self._history: dict[str, list[datetime]] = {}
        self._lock = asyncio.Lock()

    @property
    def name(self) -> NotBlankStr:
        """Guard identifier."""
        return "rate_limit"  # type: ignore[return-value]

    async def filter(
        self,
        decisions: tuple[ScalingDecision, ...],
    ) -> tuple[ScalingDecision, ...]:
        """Filter decisions through rate limit enforcement.

        Args:
            decisions: Incoming decisions.

        Returns:
            Decisions that don't exceed the daily cap.
        """
        now = datetime.now(UTC)
        cutoff = now.timestamp() - 86400
        result: list[ScalingDecision] = []

        async with self._lock:
            for decision in decisions:
                action = str(decision.action_type)
                limit = self._limits.get(action)
                if limit is None:
                    result.append(decision)
                    continue

                # Prune old entries.
                history = self._history.get(action, [])
                history = [t for t in history if t.timestamp() > cutoff]
                self._history[action] = history

                if len(history) >= limit:
                    logger.info(
                        HR_SCALING_GUARD_APPLIED,
                        guard="rate_limit",
                        action="dropped",
                        action_type=action,
                        count=len(history),
                        limit=limit,
                    )
                    continue

                result.append(decision)

        return tuple(result)

    async def record_action(self, decision: ScalingDecision) -> None:
        """Record that an action was executed for rate tracking.

        Args:
            decision: The decision that was executed.
        """
        async with self._lock:
            action = str(decision.action_type)
            history = self._history.setdefault(action, [])
            history.append(datetime.now(UTC))
