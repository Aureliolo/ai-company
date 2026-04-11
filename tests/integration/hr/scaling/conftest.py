"""Shared fixtures for scaling integration tests."""

from datetime import UTC, datetime

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.models import ScalingContext, ScalingSignal

NOW = datetime(2026, 4, 11, 12, 0, 0, tzinfo=UTC)

AGENT_IDS = tuple(NotBlankStr(f"agent-{i:03d}") for i in range(1, 6))


def make_signal(
    *,
    name: str = "avg_utilization",
    value: float = 0.75,
    threshold: float | None = None,
    source: str = "workload",
    timestamp: datetime | None = None,
) -> ScalingSignal:
    """Create a ScalingSignal."""
    return ScalingSignal(
        name=NotBlankStr(name),
        value=value,
        threshold=threshold,
        source=NotBlankStr(source),
        timestamp=timestamp or NOW,
    )


def make_context(  # noqa: PLR0913
    *,
    active_agent_count: int | None = None,
    agent_ids: tuple[NotBlankStr, ...] = AGENT_IDS,
    workload_signals: tuple[ScalingSignal, ...] = (),
    budget_signals: tuple[ScalingSignal, ...] = (),
    performance_signals: tuple[ScalingSignal, ...] = (),
    skill_signals: tuple[ScalingSignal, ...] = (),
) -> ScalingContext:
    """Create a ScalingContext.

    ``active_agent_count`` defaults to ``len(agent_ids)`` to keep the
    invariant satisfied when only the IDs are customized.
    """
    count = active_agent_count if active_agent_count is not None else len(agent_ids)
    return ScalingContext(
        active_agent_count=count,
        agent_ids=agent_ids,
        workload_signals=workload_signals,
        budget_signals=budget_signals,
        performance_signals=performance_signals,
        skill_signals=skill_signals,
        evaluated_at=NOW,
    )
