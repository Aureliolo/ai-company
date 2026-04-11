"""Conflict resolver guard.

Priority-ordered resolution of competing scaling decisions.
Budget cap HOLD decisions block hires from lower-priority
strategies.
"""

from typing import TYPE_CHECKING

from synthorg.hr.scaling.enums import ScalingActionType, ScalingStrategyName
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_SCALING_GUARD_APPLIED

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.scaling.models import ScalingDecision

logger = get_logger(__name__)

# Default priority: lower number = higher priority.
DEFAULT_PRIORITY: dict[str, int] = {
    ScalingStrategyName.BUDGET_CAP.value: 0,
    ScalingStrategyName.PERFORMANCE_PRUNING.value: 1,
    ScalingStrategyName.SKILL_GAP.value: 2,
    ScalingStrategyName.WORKLOAD.value: 3,
}

_LOWEST_PRIORITY = 999


class ConflictResolver:
    """Resolves conflicts between competing scaling decisions.

    Lower priority numbers win when decisions conflict on the same
    target (priority 0 beats priority 1, etc). Budget HOLD decisions
    block HIRE decisions from lower-priority strategies.

    Args:
        priority: Strategy name to priority mapping (lower = higher).
            Keys must be the string values of ``ScalingStrategyName``
            members (e.g. ``"workload"``).
    """

    def __init__(
        self,
        *,
        priority: dict[str, int] | None = None,
    ) -> None:
        self._priority = priority or DEFAULT_PRIORITY

    @property
    def name(self) -> NotBlankStr:
        """Guard identifier."""
        return "conflict_resolver"

    def _priority_for(self, decision: ScalingDecision) -> int:
        """Return the priority rank for a decision's strategy."""
        return self._priority.get(decision.source_strategy.value, _LOWEST_PRIORITY)

    async def filter(
        self,
        decisions: tuple[ScalingDecision, ...],
    ) -> tuple[ScalingDecision, ...]:
        """Resolve conflicts and return filtered decisions.

        Args:
            decisions: Incoming decisions from all strategies.

        Returns:
            Filtered decisions with conflicts resolved.
        """
        if not decisions:
            return ()

        # Find the highest-priority HOLD (if any) -- this blocks
        # HIRE decisions from lower-priority strategies.
        hold_priority = min(
            (
                self._priority_for(d)
                for d in decisions
                if d.action_type == ScalingActionType.HOLD
            ),
            default=_LOWEST_PRIORITY + 1,
        )

        # Single-pass deduplication: keep the best decision per
        # target agent_id; non-targeted decisions pass through.
        best_by_agent: dict[str, ScalingDecision] = {}
        non_targeted: list[ScalingDecision] = []

        for decision in decisions:
            # Skip HOLD decisions themselves (control signals).
            if decision.action_type == ScalingActionType.HOLD:
                continue

            # Block HIRE from lower-priority strategies when HOLD is active.
            if (
                decision.action_type == ScalingActionType.HIRE
                and self._priority_for(decision) > hold_priority
            ):
                logger.info(
                    HR_SCALING_GUARD_APPLIED,
                    guard="conflict_resolver",
                    action="blocked_hire",
                    strategy=decision.source_strategy.value,
                    reason="hold_from_higher_priority",
                )
                continue

            if decision.target_agent_id is None:
                non_targeted.append(decision)
                continue

            key = str(decision.target_agent_id)
            existing = best_by_agent.get(key)
            if existing is None or self._priority_for(decision) < self._priority_for(
                existing
            ):
                best_by_agent[key] = decision

        final = tuple(non_targeted) + tuple(best_by_agent.values())

        logger.info(
            HR_SCALING_GUARD_APPLIED,
            guard="conflict_resolver",
            input_count=len(decisions),
            output_count=len(final),
        )
        return final
