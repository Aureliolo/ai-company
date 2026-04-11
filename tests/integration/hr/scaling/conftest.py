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


def make_context(
    *,
    agent_ids: tuple[NotBlankStr, ...] = AGENT_IDS,
    workload_signals: tuple[ScalingSignal, ...] = (),
    budget_signals: tuple[ScalingSignal, ...] = (),
    performance_signals: tuple[ScalingSignal, ...] = (),
    skill_signals: tuple[ScalingSignal, ...] = (),
) -> ScalingContext:
    """Create a ScalingContext."""
    return ScalingContext(
        agent_ids=agent_ids,
        workload_signals=workload_signals,
        budget_signals=budget_signals,
        performance_signals=performance_signals,
        skill_signals=skill_signals,
        evaluated_at=NOW,
    )
