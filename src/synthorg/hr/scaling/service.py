"""Scaling service -- orchestrates the scaling pipeline.

Trigger -> build context -> strategies (parallel) -> merge ->
guards (sequential) -> execute.
"""

import asyncio
from collections import deque
from typing import TYPE_CHECKING, Any

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.hr.scaling.enums import (
    ScalingOutcome,
)
from synthorg.hr.scaling.models import (  # noqa: TC001
    ScalingActionRecord,
    ScalingDecision,
)
from synthorg.observability import get_logger
from synthorg.observability.events.hr import (
    HR_SCALING_CYCLE_COMPLETE,
    HR_SCALING_CYCLE_STARTED,
    HR_SCALING_DECISIONS_MERGED,
    HR_SCALING_EXECUTED,
    HR_SCALING_EXECUTION_FAILED,
    HR_SCALING_STRATEGY_EVALUATED,
)

if TYPE_CHECKING:
    from synthorg.hr.scaling.config import ScalingConfig
    from synthorg.hr.scaling.context import ScalingContextBuilder
    from synthorg.hr.scaling.protocols import (
        ScalingGuard,
        ScalingStrategy,
        ScalingTrigger,
    )

logger = get_logger(__name__)

_MAX_HISTORY = 100


class ScalingService:
    """Orchestrates the scaling pipeline.

    Pipeline:
    1. Check trigger (skip if not ready).
    2. Build ScalingContext via context_builder.
    3. Run all strategies in parallel (asyncio.TaskGroup).
    4. Merge + deduplicate decisions.
    5. Apply guard chain sequentially.
    6. Return filtered decisions.

    Execution of approved decisions (calling HiringService /
    OffboardingService) is handled by the caller or a separate
    execution step.

    Args:
        strategies: Enabled scaling strategies.
        trigger: Optional trigger (None = always evaluate).
        guard: Guard chain to filter decisions.
        context_builder: Builds ScalingContext from signals.
        config: Scaling configuration.
    """

    def __init__(
        self,
        *,
        strategies: tuple[ScalingStrategy, ...],
        trigger: ScalingTrigger | None = None,
        guard: ScalingGuard,
        context_builder: ScalingContextBuilder,
        config: ScalingConfig,
    ) -> None:
        self._strategies = strategies
        self._trigger = trigger
        self._guard = guard
        self._context_builder = context_builder
        self._config = config
        self._recent_decisions: deque[ScalingDecision] = deque(
            maxlen=_MAX_HISTORY,
        )
        self._recent_actions: deque[ScalingActionRecord] = deque(
            maxlen=_MAX_HISTORY,
        )

    async def evaluate(
        self,
        *,
        agent_ids: tuple[NotBlankStr, ...],
        context_kwargs: dict[str, Any] | None = None,
    ) -> tuple[ScalingDecision, ...]:
        """Run the evaluation pipeline.

        Args:
            agent_ids: Active agent IDs.
            context_kwargs: Extra kwargs passed to context builder.

        Returns:
            Filtered scaling decisions ready for execution.
        """
        if not self._config.enabled:
            return ()

        logger.info(HR_SCALING_CYCLE_STARTED, agent_count=len(agent_ids))

        # 1. Build context.
        context = await self._context_builder.build(
            agent_ids=agent_ids,
            **(context_kwargs or {}),
        )

        # 2. Run strategies in parallel.
        all_decisions: list[ScalingDecision] = []

        async with asyncio.TaskGroup() as tg:
            results: list[asyncio.Task[tuple[ScalingDecision, ...]]] = []
            for strategy in self._strategies:

                async def _run(
                    s: ScalingStrategy = strategy,
                ) -> tuple[ScalingDecision, ...]:
                    return await s.evaluate(context)

                results.append(tg.create_task(_run()))

        for task in results:
            decisions = task.result()
            logger.info(
                HR_SCALING_STRATEGY_EVALUATED,
                strategy=str(decisions[0].source_strategy if decisions else "unknown"),
                decisions=len(decisions),
            )
            all_decisions.extend(decisions)

        logger.info(
            HR_SCALING_DECISIONS_MERGED,
            total_decisions=len(all_decisions),
        )

        # 3. Apply guard chain.
        filtered = await self._guard.filter(tuple(all_decisions))

        # 4. Record decisions.
        for decision in filtered:
            self._recent_decisions.append(decision)

        logger.info(
            HR_SCALING_CYCLE_COMPLETE,
            input_decisions=len(all_decisions),
            output_decisions=len(filtered),
        )
        return filtered

    def record_action(self, record: ScalingActionRecord) -> None:
        """Record an executed scaling action.

        Args:
            record: The action record to store.
        """
        self._recent_actions.append(record)
        if record.outcome == ScalingOutcome.EXECUTED:
            logger.info(
                HR_SCALING_EXECUTED,
                decision_id=str(record.decision_id),
                outcome=record.outcome.value,
            )
        elif record.outcome == ScalingOutcome.FAILED:
            logger.warning(
                HR_SCALING_EXECUTION_FAILED,
                decision_id=str(record.decision_id),
                reason=str(record.reason),
            )

    def get_recent_decisions(self) -> tuple[ScalingDecision, ...]:
        """Get recent scaling decisions.

        Returns:
            Recent decisions (most recent last).
        """
        return tuple(self._recent_decisions)

    def get_recent_actions(self) -> tuple[ScalingActionRecord, ...]:
        """Get recent scaling action records.

        Returns:
            Recent action records (most recent last).
        """
        return tuple(self._recent_actions)
