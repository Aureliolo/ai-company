"""Agent health aggregation service.

Derives a compact health verdict per agent from the existing
:class:`PerformanceTracker` snapshot:

- ``healthy`` when recent success rate is above
  :data:`_DEGRADED_THRESHOLD` (or no signal exists yet -- new agents
  default to healthy rather than degraded, since the degradation
  signal requires at least one completed task);
- ``degraded`` when recent success rate is between
  :data:`_UNAVAILABLE_THRESHOLD` and :data:`_DEGRADED_THRESHOLD`;
- ``unavailable`` when recent success rate is at or below
  :data:`_UNAVAILABLE_THRESHOLD`.

The "recent" window is the tightest one the tracker produced
(typically ``7d`` in standard config); the service picks the shortest
available window so health reacts quickly to regressions without
constantly redefining "recent" on its own.
"""

from typing import TYPE_CHECKING, Final, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001 -- Pydantic runtime
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_AGENT_HEALTH_COMPUTED

if TYPE_CHECKING:
    from synthorg.hr.performance.models import (
        AgentPerformanceSnapshot,
        WindowMetrics,
    )
    from synthorg.hr.performance.tracker import PerformanceTracker


logger = get_logger(__name__)


HealthStatus = Literal["healthy", "degraded", "unavailable"]

_DEGRADED_THRESHOLD: Final[float] = 0.8
_UNAVAILABLE_THRESHOLD: Final[float] = 0.5


class AgentHealthReport(BaseModel):
    """Compact health verdict derived from a performance snapshot.

    Attributes:
        agent_id: The agent being evaluated.
        status: ``"healthy"`` / ``"degraded"`` / ``"unavailable"``.
        computed_at: When this report was computed (mirrors
            ``AgentPerformanceSnapshot.computed_at``).
        recent_window: Window label that backed the verdict (e.g.
            ``"7d"``); ``None`` when no window had any data points.
        recent_success_rate: Success rate (0.0-1.0) in
            ``recent_window``; ``None`` when no signal is available.
        recent_task_count: Task count in ``recent_window``.
        recent_failed_count: Failed-task count in ``recent_window``.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr = Field(description="Agent being evaluated")
    status: HealthStatus = Field(description="Derived health verdict")
    computed_at: AwareDatetime = Field(description="When this report was computed")
    recent_window: NotBlankStr | None = Field(
        default=None,
        description="Window label backing the verdict",
    )
    recent_success_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Success rate in the recent window",
    )
    recent_task_count: int = Field(
        default=0,
        ge=0,
        description="Completed + failed task count in the recent window",
    )
    recent_failed_count: int = Field(
        default=0,
        ge=0,
        description="Failed-task count in the recent window",
    )


class AgentHealthService:
    """Derives :class:`AgentHealthReport` from performance snapshots.

    Constructor:
        performance_tracker: The tracker that holds rolling task-metric
            windows per agent.
    """

    __slots__ = ("_performance_tracker",)

    def __init__(
        self,
        *,
        performance_tracker: PerformanceTracker,
    ) -> None:
        """Initialise with the performance tracker dependency."""
        self._performance_tracker = performance_tracker

    async def get_agent_health(
        self,
        agent_id: NotBlankStr,
    ) -> AgentHealthReport:
        """Compute a compact health verdict for *agent_id*.

        Args:
            agent_id: Agent to evaluate.

        Returns:
            A health report with status + the window that backed it.
        """
        snapshot = await self._performance_tracker.get_snapshot(agent_id)
        report = _report_from_snapshot(agent_id, snapshot)
        logger.info(
            HR_AGENT_HEALTH_COMPUTED,
            agent_id=agent_id,
            status=report.status,
            recent_window=report.recent_window,
            recent_task_count=report.recent_task_count,
        )
        return report


def _report_from_snapshot(
    agent_id: NotBlankStr,
    snapshot: AgentPerformanceSnapshot,
) -> AgentHealthReport:
    """Collapse a full performance snapshot into a health report."""
    window = _pick_recent_window(snapshot.windows)
    if window is None or window.success_rate is None:
        return AgentHealthReport(
            agent_id=agent_id,
            status="healthy",
            computed_at=snapshot.computed_at,
        )
    task_count = window.tasks_completed + window.tasks_failed
    return AgentHealthReport(
        agent_id=agent_id,
        status=_verdict(window.success_rate),
        computed_at=snapshot.computed_at,
        recent_window=window.window_size,
        recent_success_rate=window.success_rate,
        recent_task_count=task_count,
        recent_failed_count=window.tasks_failed,
    )


def _pick_recent_window(
    windows: tuple[WindowMetrics, ...],
) -> WindowMetrics | None:
    """Return the window with the most data points (proxy for "recent").

    The tracker emits one window per configured rolling period (7d /
    30d / 90d / ...). We pick the one with the most data points so
    the verdict reflects the highest-signal window that actually has
    observations. When two windows tie, the *first* wins -- preserves
    the tracker's configured order.
    """
    candidates = [w for w in windows if w.data_point_count > 0]
    if not candidates:
        return None
    return max(candidates, key=lambda w: w.data_point_count)


def _verdict(success_rate: float) -> HealthStatus:
    """Map a success rate onto a health status."""
    if success_rate <= _UNAVAILABLE_THRESHOLD:
        return "unavailable"
    if success_rate < _DEGRADED_THRESHOLD:
        return "degraded"
    return "healthy"


__all__ = ["AgentHealthReport", "AgentHealthService", "HealthStatus"]
