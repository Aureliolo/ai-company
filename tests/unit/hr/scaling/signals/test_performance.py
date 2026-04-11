"""Tests for performance signal source."""

from datetime import UTC, datetime

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.enums import TrendDirection
from synthorg.hr.performance.models import (
    AgentPerformanceSnapshot,
    TrendResult,
)
from synthorg.hr.scaling.signals.performance import PerformanceSignalSource

_AGENT_IDS = (NotBlankStr("a1"), NotBlankStr("a2"))
_NOW = datetime(2026, 4, 11, 12, 0, 0, tzinfo=UTC)


def _make_snapshot(
    agent_id: str,
    quality_direction: TrendDirection = TrendDirection.STABLE,
) -> AgentPerformanceSnapshot:
    trends = (
        TrendResult(
            metric_name=NotBlankStr("quality_score"),
            window_size=NotBlankStr("7d"),
            direction=quality_direction,
            slope=0.0,
            data_point_count=10,
        ),
    )
    return AgentPerformanceSnapshot(
        agent_id=NotBlankStr(agent_id),
        computed_at=_NOW,
        trends=trends,
    )


@pytest.mark.unit
class TestPerformanceSignalSource:
    """PerformanceSignalSource signal collection."""

    async def test_no_snapshots_returns_zeros(self) -> None:
        source = PerformanceSignalSource()
        signals = await source.collect(_AGENT_IDS, snapshots=None)
        by_name = {s.name: s.value for s in signals}
        assert by_name["avg_quality_trend"] == 0.0
        assert by_name["declining_agent_count"] == 0.0

    async def test_all_stable(self) -> None:
        source = PerformanceSignalSource()
        snapshots = {
            "a1": _make_snapshot("a1", TrendDirection.STABLE),
            "a2": _make_snapshot("a2", TrendDirection.STABLE),
        }
        signals = await source.collect(_AGENT_IDS, snapshots=snapshots)
        by_name = {s.name: s.value for s in signals}
        assert by_name["avg_quality_trend"] == 0.0
        assert by_name["declining_agent_count"] == 0.0

    async def test_mixed_trends(self) -> None:
        source = PerformanceSignalSource()
        snapshots = {
            "a1": _make_snapshot("a1", TrendDirection.IMPROVING),
            "a2": _make_snapshot("a2", TrendDirection.DECLINING),
        }
        signals = await source.collect(_AGENT_IDS, snapshots=snapshots)
        by_name = {s.name: s.value for s in signals}
        # (1.0 + -1.0) / 2 = 0.0
        assert by_name["avg_quality_trend"] == 0.0
        assert by_name["declining_agent_count"] == 1.0

    async def test_all_declining(self) -> None:
        source = PerformanceSignalSource()
        snapshots = {
            "a1": _make_snapshot("a1", TrendDirection.DECLINING),
            "a2": _make_snapshot("a2", TrendDirection.DECLINING),
        }
        signals = await source.collect(_AGENT_IDS, snapshots=snapshots)
        by_name = {s.name: s.value for s in signals}
        assert by_name["avg_quality_trend"] == -1.0
        assert by_name["declining_agent_count"] == 2.0

    async def test_snapshot_without_quality_trend(self) -> None:
        source = PerformanceSignalSource()
        snapshot = AgentPerformanceSnapshot(
            agent_id=NotBlankStr("a1"),
            computed_at=_NOW,
            trends=(),
        )
        signals = await source.collect(_AGENT_IDS, snapshots={"a1": snapshot})
        by_name = {s.name: s.value for s in signals}
        assert by_name["avg_quality_trend"] == 0.0

    async def test_source_name(self) -> None:
        source = PerformanceSignalSource()
        assert source.name == "performance"
