"""Scaling context builder -- aggregates signals into a frozen context."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from synthorg.hr.scaling.models import ScalingContext, ScalingSignal
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.hr.scaling.signals.budget import BudgetSignalSource
    from synthorg.hr.scaling.signals.performance import (
        PerformanceSignalSource,
    )
    from synthorg.hr.scaling.signals.skill import SkillSignalSource
    from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

logger = get_logger(__name__)


class ScalingContextBuilder:
    """Assembles a ``ScalingContext`` from signal sources.

    Each source is optional -- missing sources produce empty signal
    tuples in the context.

    Args:
        workload_source: Workload signal source.
        budget_source: Budget signal source.
        performance_source: Performance signal source.
        skill_source: Skill signal source.
    """

    def __init__(
        self,
        *,
        workload_source: WorkloadSignalSource | None = None,
        budget_source: BudgetSignalSource | None = None,
        performance_source: PerformanceSignalSource | None = None,
        skill_source: SkillSignalSource | None = None,
    ) -> None:
        self._workload = workload_source
        self._budget = budget_source
        self._performance = performance_source
        self._skill = skill_source

    async def build(
        self,
        *,
        agent_ids: tuple[NotBlankStr, ...],
        workload_kwargs: dict[str, Any] | None = None,
        budget_kwargs: dict[str, Any] | None = None,
        performance_kwargs: dict[str, Any] | None = None,
        skill_kwargs: dict[str, Any] | None = None,
    ) -> ScalingContext:
        """Build a frozen scaling context from all signal sources.

        Args:
            agent_ids: IDs of all active agents.
            workload_kwargs: Extra kwargs for workload source.
            budget_kwargs: Extra kwargs for budget source.
            performance_kwargs: Extra kwargs for performance source.
            skill_kwargs: Extra kwargs for skill source.

        Returns:
            Frozen ``ScalingContext`` with all collected signals.
        """
        workload_signals: tuple[ScalingSignal, ...] = ()
        budget_signals: tuple[ScalingSignal, ...] = ()
        performance_signals: tuple[ScalingSignal, ...] = ()
        skill_signals: tuple[ScalingSignal, ...] = ()

        if self._workload is not None:
            workload_signals = await self._workload.collect(
                agent_ids,
                **(workload_kwargs or {}),
            )

        if self._budget is not None:
            budget_signals = await self._budget.collect(
                agent_ids,
                **(budget_kwargs or {}),
            )

        if self._performance is not None:
            performance_signals = await self._performance.collect(
                agent_ids,
                **(performance_kwargs or {}),
            )

        if self._skill is not None:
            skill_signals = await self._skill.collect(
                agent_ids,
                **(skill_kwargs or {}),
            )

        return ScalingContext(
            active_agent_count=len(agent_ids),
            agent_ids=agent_ids,
            workload_signals=workload_signals,
            budget_signals=budget_signals,
            performance_signals=performance_signals,
            skill_signals=skill_signals,
            evaluated_at=datetime.now(UTC),
        )
