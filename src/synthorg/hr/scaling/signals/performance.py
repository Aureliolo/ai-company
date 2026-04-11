"""Performance signal source -- reads trend data from tracker."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.models import ScalingSignal
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.hr.performance.models import AgentPerformanceSnapshot

logger = get_logger(__name__)

_SOURCE_NAME = NotBlankStr("performance")

# Map trend direction strings to numeric values for signal thresholds.
_TREND_MAP: dict[str, float] = {
    "improving": 1.0,
    "stable": 0.0,
    "declining": -1.0,
    "insufficient_data": 0.0,
}


class PerformanceSignalSource:
    """Read-only adapter over the performance tracker.

    Converts ``AgentPerformanceSnapshot`` trend data into
    aggregate scaling signals.
    """

    @property
    def name(self) -> NotBlankStr:
        """Source identifier."""
        return _SOURCE_NAME

    async def collect(
        self,
        agent_ids: tuple[NotBlankStr, ...],  # noqa: ARG002
        *,
        snapshots: dict[str, AgentPerformanceSnapshot] | None = None,
    ) -> tuple[ScalingSignal, ...]:
        """Collect performance trend signals.

        Args:
            agent_ids: Active agent IDs.
            snapshots: Performance snapshots keyed by agent_id.

        Returns:
            Performance signals: avg_quality_trend,
            declining_agent_count.
        """
        now = datetime.now(UTC)

        if not snapshots:
            return (
                ScalingSignal(
                    name=NotBlankStr("avg_quality_trend"),
                    value=0.0,
                    source=_SOURCE_NAME,
                    timestamp=now,
                ),
                ScalingSignal(
                    name=NotBlankStr("declining_agent_count"),
                    value=0.0,
                    source=_SOURCE_NAME,
                    timestamp=now,
                ),
            )

        trend_values: list[float] = []
        declining_count = 0

        for snapshot in snapshots.values():
            # Find quality_score trend in the trends tuple.
            quality_trend = next(
                (t for t in snapshot.trends if t.metric_name == "quality_score"),
                None,
            )
            if quality_trend is not None:
                direction = str(quality_trend.direction)
                value = _TREND_MAP.get(direction, 0.0)
                trend_values.append(value)
                if direction == "declining":
                    declining_count += 1
            else:
                trend_values.append(0.0)

        avg_trend = sum(trend_values) / len(trend_values) if trend_values else 0.0

        return (
            ScalingSignal(
                name=NotBlankStr("avg_quality_trend"),
                value=round(avg_trend, 4),
                source=_SOURCE_NAME,
                timestamp=now,
            ),
            ScalingSignal(
                name=NotBlankStr("declining_agent_count"),
                value=float(declining_count),
                source=_SOURCE_NAME,
                timestamp=now,
            ),
        )
