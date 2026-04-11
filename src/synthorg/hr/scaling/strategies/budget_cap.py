"""Budget cap strategy.

Hard ceiling on spend: proposes pruning when projected burn
exceeds the safety margin, and emits HOLD to block hires
from lower-priority strategies.
"""

from datetime import UTC, datetime

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.enums import ScalingActionType, ScalingStrategyName
from synthorg.hr.scaling.models import ScalingContext, ScalingDecision
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_SCALING_STRATEGY_EVALUATED

logger = get_logger(__name__)

_NAME = NotBlankStr("budget_cap")
_ACTION_TYPES = frozenset(
    {ScalingActionType.PRUNE, ScalingActionType.HOLD, ScalingActionType.NO_OP},
)


class BudgetCapStrategy:
    """Budget-aware scaling strategy.

    Emits PRUNE when burn rate exceeds the safety margin.
    Emits HOLD (blocking hires) when burn is between headroom
    and safety margin. Emits nothing when under headroom.

    Args:
        safety_margin: Burn rate fraction above which to prune.
        headroom_fraction: Burn rate fraction below which hires
            are allowed.
    """

    def __init__(
        self,
        *,
        safety_margin: float = 0.90,
        headroom_fraction: float = 0.60,
    ) -> None:
        self._safety_margin = safety_margin
        self._headroom_fraction = headroom_fraction

    @property
    def name(self) -> NotBlankStr:
        """Strategy identifier."""
        return _NAME

    @property
    def action_types(self) -> frozenset[ScalingActionType]:
        """Action types this strategy can produce."""
        return _ACTION_TYPES

    async def evaluate(
        self,
        context: ScalingContext,
    ) -> tuple[ScalingDecision, ...]:
        """Evaluate budget signals and propose decisions.

        Args:
            context: Aggregated company state snapshot.

        Returns:
            PRUNE, HOLD, or empty tuple.
        """
        now = datetime.now(UTC)

        burn_signal = next(
            (s for s in context.budget_signals if s.name == "burn_rate_percent"),
            None,
        )
        if burn_signal is None:
            logger.debug(
                HR_SCALING_STRATEGY_EVALUATED,
                strategy="budget_cap",
                decisions=0,
                reason="no_burn_signal",
            )
            return ()

        burn_fraction = burn_signal.value / 100.0
        budget_signals = tuple(
            s for s in context.budget_signals if s.name == "burn_rate_percent"
        )

        if burn_fraction >= self._safety_margin:
            # Over budget -- prune cheapest agent + HOLD to block hires.
            decisions: list[ScalingDecision] = []
            target = context.agent_ids[-1] if context.agent_ids else None
            if target is not None:
                decisions.append(
                    ScalingDecision(
                        action_type=ScalingActionType.PRUNE,
                        source_strategy=ScalingStrategyName.BUDGET_CAP,
                        target_agent_id=target,
                        rationale=NotBlankStr(
                            f"burn rate {burn_fraction:.0%} exceeds "
                            f"safety margin {self._safety_margin:.0%}"
                        ),
                        confidence=1.0,
                        signals=budget_signals,
                        created_at=now,
                    ),
                )
            # Also emit HOLD to block hires from lower-priority strategies.
            decisions.append(
                ScalingDecision(
                    action_type=ScalingActionType.HOLD,
                    source_strategy=ScalingStrategyName.BUDGET_CAP,
                    rationale=NotBlankStr(
                        f"burn rate {burn_fraction:.0%} exceeds safety "
                        f"margin -- blocking all hires"
                    ),
                    confidence=1.0,
                    signals=budget_signals,
                    created_at=now,
                ),
            )
            logger.info(
                HR_SCALING_STRATEGY_EVALUATED,
                strategy="budget_cap",
                decisions=len(decisions),
                action="prune+hold",
                burn_fraction=burn_fraction,
            )
            return tuple(decisions)

        if burn_fraction > self._headroom_fraction:
            # Between headroom and safety -- block hires.
            decision = ScalingDecision(
                action_type=ScalingActionType.HOLD,
                source_strategy=ScalingStrategyName.BUDGET_CAP,
                rationale=NotBlankStr(
                    f"burn rate {burn_fraction:.0%} above headroom "
                    f"{self._headroom_fraction:.0%} -- blocking hires"
                ),
                confidence=1.0,
                signals=budget_signals,
                created_at=now,
            )
            logger.info(
                HR_SCALING_STRATEGY_EVALUATED,
                strategy="budget_cap",
                decisions=1,
                action="hold",
                burn_fraction=burn_fraction,
            )
            return (decision,)

        logger.info(
            HR_SCALING_STRATEGY_EVALUATED,
            strategy="budget_cap",
            decisions=0,
            burn_fraction=burn_fraction,
        )
        return ()
