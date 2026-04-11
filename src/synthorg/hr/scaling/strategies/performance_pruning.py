"""Performance pruning strategy.

Wraps existing PruningPolicy implementations and coordinates
with the evolution system to defer pruning agents under active
adaptation.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.enums import ScalingActionType, ScalingStrategyName
from synthorg.hr.scaling.models import ScalingContext, ScalingDecision
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_SCALING_STRATEGY_EVALUATED

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from synthorg.hr.performance.models import AgentPerformanceSnapshot
    from synthorg.hr.pruning.policy import PruningPolicy

    EvolutionChecker = Callable[[NotBlankStr], Awaitable[bool]]

logger = get_logger(__name__)

_NAME = NotBlankStr("performance_pruning")
_ACTION_TYPES = frozenset({ScalingActionType.PRUNE})


class PerformancePruningStrategy:
    """Wraps existing pruning policies as a scaling strategy.

    Evaluates each agent through the configured ``PruningPolicy``
    and emits PRUNE decisions for eligible agents.

    When ``defer_during_evolution`` is True, agents with recent
    evolution adaptations are skipped.

    Args:
        policy: Pruning policy to delegate to.
        evolution_checker: Optional async callable that returns True
            if an agent has recent evolution adaptations. Signature:
            ``async def(agent_id: NotBlankStr) -> bool``.
        defer_during_evolution: Whether to defer pruning during
            active evolution.
    """

    def __init__(
        self,
        *,
        policy: PruningPolicy,
        evolution_checker: EvolutionChecker | None = None,
        defer_during_evolution: bool = True,
    ) -> None:
        self._policy = policy
        self._evolution_checker = evolution_checker
        self._defer_during_evolution = defer_during_evolution

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
        *,
        snapshots: dict[str, AgentPerformanceSnapshot] | None = None,
    ) -> tuple[ScalingDecision, ...]:
        """Evaluate agents through the pruning policy.

        Args:
            context: Aggregated company state snapshot.
            snapshots: Performance snapshots keyed by agent_id.

        Returns:
            PRUNE decisions for eligible agents.
        """
        if snapshots is None:
            return ()

        now = datetime.now(UTC)
        decisions: list[ScalingDecision] = []

        for agent_id in context.agent_ids:
            agent_key = str(agent_id)
            snapshot = snapshots.get(agent_key)
            if snapshot is None:
                continue

            # Check evolution deferral.
            if self._defer_during_evolution and self._evolution_checker is not None:
                is_adapting = await self._evolution_checker(agent_id)
                if is_adapting:
                    logger.debug(
                        HR_SCALING_STRATEGY_EVALUATED,
                        strategy="performance_pruning",
                        agent_id=agent_key,
                        reason="deferred_evolution_active",
                    )
                    continue

            evaluation = await self._policy.evaluate(agent_id, snapshot)
            if evaluation.eligible:
                decisions.append(
                    ScalingDecision(
                        action_type=ScalingActionType.PRUNE,
                        source_strategy=ScalingStrategyName.PERFORMANCE_PRUNING,
                        target_agent_id=agent_id,
                        rationale=NotBlankStr(
                            "; ".join(str(r) for r in evaluation.reasons)
                            or "performance below threshold"
                        ),
                        confidence=0.8,
                        created_at=now,
                    ),
                )

        logger.info(
            HR_SCALING_STRATEGY_EVALUATED,
            strategy="performance_pruning",
            decisions=len(decisions),
            agents_evaluated=len(context.agent_ids),
        )
        return tuple(decisions)
