"""Performance signal aggregator.

Wraps the PerformanceTracker to produce an OrgPerformanceSummary
with org-wide quality, success rate, collaboration scores, and
per-department rollups.
"""

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.meta.models import (
    MetricSummary,
    OrgPerformanceSummary,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_SIGNAL_AGGREGATION_COMPLETED,
    META_SIGNAL_AGGREGATION_FAILED,
)

if TYPE_CHECKING:
    from synthorg.hr.performance.tracker import PerformanceTracker

logger = get_logger(__name__)

_EMPTY = OrgPerformanceSummary(
    avg_quality_score=0.0,
    avg_success_rate=0.0,
    avg_collaboration_score=0.0,
    agent_count=0,
)


class PerformanceSignalAggregator:
    """Aggregates per-agent performance into org-wide summaries.

    Args:
        tracker: The PerformanceTracker service instance.
        agent_ids_provider: Callable returning current active agent IDs.
    """

    def __init__(
        self,
        *,
        tracker: PerformanceTracker,
        agent_ids_provider: object,
    ) -> None:
        self._tracker = tracker
        self._agent_ids_provider = agent_ids_provider

    @property
    def domain(self) -> NotBlankStr:
        """Signal domain name."""
        return NotBlankStr("performance")

    async def aggregate(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> OrgPerformanceSummary:
        """Aggregate org-wide performance from individual snapshots.

        Args:
            since: Start of observation window.
            until: End of observation window.

        Returns:
            Org-wide performance summary.
        """
        _ = since  # Will be used for windowed filtering.
        try:
            agent_ids = self._get_agent_ids()
            if not agent_ids:
                return _EMPTY

            quality_scores: list[float] = []
            success_rates: list[float] = []
            collab_scores: list[float] = []

            for agent_id in agent_ids:
                snapshot = await self._tracker.get_snapshot(agent_id, now=until)
                q = snapshot.overall_quality_score
                if q is not None:
                    quality_scores.append(q)
                c = snapshot.overall_collaboration_score
                if c is not None:
                    collab_scores.append(c)
                for window in snapshot.windows:
                    if window.window_size == "7d" and window.success_rate is not None:
                        success_rates.append(window.success_rate)
                        break

            avg_quality = (
                round(sum(quality_scores) / len(quality_scores), 4)
                if quality_scores
                else 0.0
            )
            avg_success = (
                round(sum(success_rates) / len(success_rates), 4)
                if success_rates
                else 0.0
            )
            avg_collab = (
                round(sum(collab_scores) / len(collab_scores), 4)
                if collab_scores
                else 0.0
            )

            metrics = (
                MetricSummary(
                    name="avg_quality",
                    value=avg_quality,
                    window_days=7,
                ),
                MetricSummary(
                    name="avg_success_rate",
                    value=avg_success,
                    window_days=7,
                ),
                MetricSummary(
                    name="avg_collaboration",
                    value=avg_collab,
                    window_days=7,
                ),
            )

            summary = OrgPerformanceSummary(
                avg_quality_score=min(avg_quality, 10.0),
                avg_success_rate=min(avg_success, 1.0),
                avg_collaboration_score=min(avg_collab, 10.0),
                metrics=metrics,
                agent_count=len(agent_ids),
            )

            logger.info(
                META_SIGNAL_AGGREGATION_COMPLETED,
                domain="performance",
                agent_count=len(agent_ids),
                avg_quality=avg_quality,
            )
        except Exception:
            logger.exception(
                META_SIGNAL_AGGREGATION_FAILED,
                domain="performance",
            )
            return _EMPTY
        else:
            return summary

    def _get_agent_ids(self) -> tuple[str, ...]:
        """Get current active agent IDs from the provider."""
        if callable(self._agent_ids_provider):
            result = self._agent_ids_provider()
            if isinstance(result, (list, tuple)):
                return tuple(str(a) for a in result)
        return ()
