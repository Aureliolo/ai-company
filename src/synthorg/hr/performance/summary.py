"""Pure functions for extracting API-friendly performance summaries.

Transforms :class:`AgentPerformanceSnapshot` into a flat
:class:`AgentPerformanceSummary` suitable for dashboard display.
"""

from typing import TYPE_CHECKING

from synthorg.api.dto import AgentPerformanceSummary
from synthorg.hr.enums import TrendDirection

if TYPE_CHECKING:
    from synthorg.hr.performance.models import (
        AgentPerformanceSnapshot,
        WindowMetrics,
    )

_WINDOW_7D = "7d"
_WINDOW_30D = "30d"
_SUCCESS_RATE_METRIC = "success_rate"


def _find_window(
    snapshot: AgentPerformanceSnapshot,
    label: str,
) -> WindowMetrics | None:
    """Find a window by its size label."""
    for w in snapshot.windows:
        if w.window_size == label:
            return w
    return None


def _primary_trend_direction(
    snapshot: AgentPerformanceSnapshot,
) -> TrendDirection:
    """Pick the primary trend direction from the snapshot.

    Prefers the ``success_rate`` trend.  Falls back to the first
    trend result, then ``INSUFFICIENT_DATA`` if no trends exist.
    """
    for trend in snapshot.trends:
        if trend.metric_name == _SUCCESS_RATE_METRIC:
            return trend.direction
    if snapshot.trends:
        return snapshot.trends[0].direction
    return TrendDirection.INSUFFICIENT_DATA


def _success_rate_to_percent(rate: float | None) -> float | None:
    """Convert a 0.0-1.0 success rate to a 0.0-100.0 percentage."""
    if rate is None:
        return None
    return round(rate * 100.0, 2)


def extract_performance_summary(
    snapshot: AgentPerformanceSnapshot,
    agent_name: str,
) -> AgentPerformanceSummary:
    """Flatten an ``AgentPerformanceSnapshot`` into an API-friendly summary.

    Args:
        snapshot: Full performance snapshot from
            :meth:`PerformanceTracker.get_snapshot`.
        agent_name: Agent display name for the response.

    Returns:
        A flat summary suitable for dashboard rendering.
    """
    w7 = _find_window(snapshot, _WINDOW_7D)
    w30 = _find_window(snapshot, _WINDOW_30D)

    # Total tasks = sum of data_point_count across all windows.
    # Use the largest window's count as the total (windows overlap in time,
    # so summing would double-count).  Fall back to 0 if no windows.
    tasks_total = max(
        (w.data_point_count for w in snapshot.windows),
        default=0,
    )

    # Prefer the 30d window for rate/average metrics, fall back to 7d.
    primary = w30 or w7

    return AgentPerformanceSummary(
        agent_name=agent_name,
        tasks_completed_total=tasks_total,
        tasks_completed_7d=w7.tasks_completed if w7 else 0,
        tasks_completed_30d=w30.tasks_completed if w30 else 0,
        avg_completion_time_seconds=(
            primary.avg_completion_time_seconds if primary else None
        ),
        success_rate_percent=_success_rate_to_percent(
            primary.success_rate if primary else None,
        ),
        cost_per_task_usd=primary.avg_cost_per_task if primary else None,
        quality_score=snapshot.overall_quality_score,
        collaboration_score=snapshot.overall_collaboration_score,
        trend_direction=_primary_trend_direction(snapshot),
        windows=snapshot.windows,
        trends=snapshot.trends,
    )
