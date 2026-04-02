"""Budget velocity calculator -- points per currency unit consumed.

Measures cost efficiency as story points delivered per unit of budget
consumed.  Primary unit: ``pts/EUR``.
"""

from typing import TYPE_CHECKING

from synthorg.engine.workflow.velocity_types import (
    VelocityCalcType,
    VelocityMetrics,
)
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
    VELOCITY_BUDGET_NO_BUDGET_CONSUMED,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synthorg.engine.workflow.sprint_velocity import VelocityRecord

logger = get_logger(__name__)

_UNIT: str = "pts/EUR"


class BudgetVelocityCalculator:
    """Velocity calculator measuring points per currency unit consumed.

    Primary unit: ``pts/EUR`` (assumes the default display currency).

    When ``budget_consumed`` is ``None`` or zero, ``primary_value``
    is 0.0 and only ``pts_per_sprint`` appears in secondary metrics.
    When budget data is available, secondary metrics also include
    ``budget_consumed`` and ``completion_ratio``.
    """

    __slots__ = ()

    def compute(self, record: VelocityRecord) -> VelocityMetrics:
        """Compute points-per-EUR from a single velocity record.

        Args:
            record: A completed sprint's velocity record.

        Returns:
            Velocity metrics with ``pts/EUR`` as primary unit.
        """
        budget = record.budget_consumed
        if budget is None or budget == 0.0:
            logger.debug(
                VELOCITY_BUDGET_NO_BUDGET_CONSUMED,
                sprint_id=record.sprint_id,
                reason="none" if budget is None else "zero",
            )
            return VelocityMetrics(
                primary_value=0.0,
                primary_unit=_UNIT,
                secondary={
                    "pts_per_sprint": record.story_points_completed,
                },
            )
        pts_per_eur = record.story_points_completed / budget
        return VelocityMetrics(
            primary_value=pts_per_eur,
            primary_unit=_UNIT,
            secondary={
                "pts_per_sprint": record.story_points_completed,
                "budget_consumed": budget,
                "completion_ratio": record.completion_ratio,
            },
        )

    def rolling_average(
        self,
        records: Sequence[VelocityRecord],
        window: int,
    ) -> VelocityMetrics:
        """Compute rolling average of points-per-EUR.

        Uses the last *window* records.  Records where
        ``budget_consumed`` is ``None`` or ``<= 0.0`` are excluded
        from the average.

        Args:
            records: Ordered velocity records (oldest first).
            window: Number of recent sprints to average over.

        Returns:
            Averaged velocity metrics.
        """
        if not records or window < 1:
            return VelocityMetrics(
                primary_value=0.0,
                primary_unit=_UNIT,
            )
        recent = records[-window:]
        total_pts = 0.0
        total_budget = 0.0
        valid_count = 0
        for r in recent:
            budget = r.budget_consumed
            if budget is not None and budget > 0.0:
                total_pts += r.story_points_completed
                total_budget += budget
                valid_count += 1
        if total_budget == 0.0:
            return VelocityMetrics(
                primary_value=0.0,
                primary_unit=_UNIT,
            )
        return VelocityMetrics(
            primary_value=total_pts / total_budget,
            primary_unit=_UNIT,
            secondary={
                "total_budget_consumed": total_budget,
                "sprints_averaged": float(valid_count),
            },
        )

    @property
    def calculator_type(self) -> VelocityCalcType:
        """Return BUDGET."""
        return VelocityCalcType.BUDGET

    @property
    def primary_unit(self) -> str:
        """Return ``pts/EUR``."""
        return _UNIT
