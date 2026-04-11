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
    ScalingStrategyName.BUDGET_CAP: 0,
    ScalingStrategyName.PERFORMANCE_PRUNING: 1,
    ScalingStrategyName.SKILL_GAP: 2,
    ScalingStrategyName.WORKLOAD: 3,
}


class ConflictResolver:
    """Resolves conflicts between competing scaling decisions.

    Higher-priority strategies win when decisions conflict on the
    same target. Budget HOLD decisions block HIRE decisions from
    lower-priority strategies.

    Args:
        priority: Strategy name to priority mapping (lower = higher).
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
        return "conflict_resolver"  # type: ignore[return-value]

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

        # Check for any HOLD decisions -- these block all HIREs
        # from lower-priority strategies.
        has_hold = any(d.action_type == ScalingActionType.HOLD for d in decisions)
        hold_priority = min(
            (
                self._priority.get(str(d.source_strategy), 999)
                for d in decisions
                if d.action_type == ScalingActionType.HOLD
            ),
            default=999,
        )

        result: list[ScalingDecision] = []
        for decision in decisions:
            # Skip HOLD decisions themselves (they're control signals).
            if decision.action_type == ScalingActionType.HOLD:
                continue

            # If there's a HOLD, block HIRE from lower-priority strategies.
            if has_hold and decision.action_type == ScalingActionType.HIRE:
                strategy_priority = self._priority.get(
                    str(decision.source_strategy),
                    999,
                )
                if strategy_priority > hold_priority:
                    logger.info(
                        HR_SCALING_GUARD_APPLIED,
                        guard="conflict_resolver",
                        action="blocked_hire",
                        strategy=str(decision.source_strategy),
                        reason="hold_from_higher_priority",
                    )
                    continue

            result.append(decision)

        # Deduplicate: if multiple strategies target the same agent
        # for different actions, keep the highest-priority one.
        seen_agents: dict[str, ScalingDecision] = {}
        final: list[ScalingDecision] = []
        for decision in result:
            key = str(decision.target_agent_id) if decision.target_agent_id else None
            if key is None:
                final.append(decision)
                continue
            existing = seen_agents.get(key)
            if existing is None:
                seen_agents[key] = decision
                final.append(decision)
            else:
                existing_pri = self._priority.get(
                    str(existing.source_strategy),
                    999,
                )
                new_pri = self._priority.get(
                    str(decision.source_strategy),
                    999,
                )
                if new_pri < existing_pri:
                    final.remove(existing)
                    seen_agents[key] = decision
                    final.append(decision)

        logger.info(
            HR_SCALING_GUARD_APPLIED,
            guard="conflict_resolver",
            input_count=len(decisions),
            output_count=len(final),
        )
        return tuple(final)
