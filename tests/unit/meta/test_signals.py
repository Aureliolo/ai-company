"""Unit tests for meta-loop signal aggregation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.meta.models import (
    OrgBudgetSummary,
    OrgCoordinationSummary,
    OrgErrorSummary,
    OrgEvolutionSummary,
    OrgPerformanceSummary,
    OrgScalingSummary,
    OrgSignalSnapshot,
    OrgTelemetrySummary,
)
from synthorg.meta.signals.budget import BudgetSignalAggregator
from synthorg.meta.signals.coordination import (
    CoordinationSignalAggregator,
)
from synthorg.meta.signals.errors import ErrorSignalAggregator
from synthorg.meta.signals.evolution import EvolutionSignalAggregator
from synthorg.meta.signals.performance import (
    PerformanceSignalAggregator,
)
from synthorg.meta.signals.scaling import ScalingSignalAggregator
from synthorg.meta.signals.snapshot import SnapshotBuilder
from synthorg.meta.signals.telemetry import TelemetrySignalAggregator

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────

_NOW = datetime.now(UTC)
_WEEK_AGO = _NOW - timedelta(days=7)


def _make_mock_tracker() -> MagicMock:
    """Create a mock PerformanceTracker."""
    tracker = MagicMock()
    # Mock get_snapshot to return a snapshot with windows and scores.
    snapshot = MagicMock()
    snapshot.overall_quality_score = 7.5
    snapshot.overall_collaboration_score = 6.0
    window = MagicMock()
    window.window_size = "7d"
    window.success_rate = 0.85
    snapshot.windows = (window,)
    snapshot.trends = ()
    tracker.get_snapshot = AsyncMock(return_value=snapshot)
    return tracker


# ── Performance aggregator ─────────────────────────────────────────


class TestPerformanceSignalAggregator:
    """Performance aggregator tests."""

    def test_domain_name(self) -> None:
        tracker = _make_mock_tracker()
        agg = PerformanceSignalAggregator(
            tracker=tracker,
            agent_ids_provider=list,
        )
        assert agg.domain == "performance"

    async def test_empty_org(self) -> None:
        tracker = _make_mock_tracker()
        agg = PerformanceSignalAggregator(
            tracker=tracker,
            agent_ids_provider=list,
        )
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert isinstance(result, OrgPerformanceSummary)
        assert result.agent_count == 0

    async def test_single_agent(self) -> None:
        tracker = _make_mock_tracker()
        agg = PerformanceSignalAggregator(
            tracker=tracker,
            agent_ids_provider=lambda: ["agent-1"],
        )
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert result.agent_count == 1
        assert result.avg_quality_score == 7.5
        assert result.avg_success_rate == 0.85
        assert result.avg_collaboration_score == 6.0

    async def test_multiple_agents_averaged(self) -> None:
        tracker = MagicMock()
        snapshot1 = MagicMock()
        snapshot1.overall_quality_score = 8.0
        snapshot1.overall_collaboration_score = 7.0
        window1 = MagicMock()
        window1.window_size = "7d"
        window1.success_rate = 0.90
        snapshot1.windows = (window1,)

        snapshot2 = MagicMock()
        snapshot2.overall_quality_score = 6.0
        snapshot2.overall_collaboration_score = 5.0
        window2 = MagicMock()
        window2.window_size = "7d"
        window2.success_rate = 0.80
        snapshot2.windows = (window2,)

        tracker.get_snapshot = AsyncMock(side_effect=[snapshot1, snapshot2])

        agg = PerformanceSignalAggregator(
            tracker=tracker,
            agent_ids_provider=lambda: ["agent-1", "agent-2"],
        )
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert result.agent_count == 2
        assert result.avg_quality_score == 7.0
        assert result.avg_success_rate == 0.85

    async def test_tracker_failure_returns_empty(self) -> None:
        tracker = MagicMock()
        tracker.get_snapshot = AsyncMock(side_effect=RuntimeError("tracker broken"))
        agg = PerformanceSignalAggregator(
            tracker=tracker,
            agent_ids_provider=lambda: ["agent-1"],
        )
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert result.agent_count == 0


# ── Other aggregators ──────────────────────────────────────────────


class TestBudgetSignalAggregator:
    """Budget aggregator tests."""

    def test_domain_name(self) -> None:
        agg = BudgetSignalAggregator(cost_record_provider=list)
        assert agg.domain == "budget"

    async def test_returns_budget_summary(self) -> None:
        agg = BudgetSignalAggregator(cost_record_provider=list)
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert isinstance(result, OrgBudgetSummary)


class TestCoordinationSignalAggregator:
    """Coordination aggregator tests."""

    async def test_returns_coordination_summary(self) -> None:
        agg = CoordinationSignalAggregator()
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert isinstance(result, OrgCoordinationSummary)


class TestScalingSignalAggregator:
    """Scaling aggregator tests."""

    async def test_returns_scaling_summary(self) -> None:
        agg = ScalingSignalAggregator()
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert isinstance(result, OrgScalingSummary)


class TestErrorSignalAggregator:
    """Error aggregator tests."""

    async def test_returns_error_summary(self) -> None:
        agg = ErrorSignalAggregator()
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert isinstance(result, OrgErrorSummary)


class TestEvolutionSignalAggregator:
    """Evolution aggregator tests."""

    async def test_returns_evolution_summary(self) -> None:
        agg = EvolutionSignalAggregator()
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert isinstance(result, OrgEvolutionSummary)


class TestTelemetrySignalAggregator:
    """Telemetry aggregator tests."""

    async def test_returns_telemetry_summary(self) -> None:
        agg = TelemetrySignalAggregator()
        result = await agg.aggregate(since=_WEEK_AGO, until=_NOW)
        assert isinstance(result, OrgTelemetrySummary)


# ── Snapshot builder ───────────────────────────────────────────────


class TestSnapshotBuilder:
    """SnapshotBuilder tests."""

    def _make_builder(self) -> SnapshotBuilder:
        """Create a builder with default aggregators."""
        tracker = _make_mock_tracker()
        return SnapshotBuilder(
            performance=PerformanceSignalAggregator(
                tracker=tracker,
                agent_ids_provider=lambda: ["agent-1"],
            ),
            budget=BudgetSignalAggregator(cost_record_provider=list),
            coordination=CoordinationSignalAggregator(),
            scaling=ScalingSignalAggregator(),
            errors=ErrorSignalAggregator(),
            evolution=EvolutionSignalAggregator(),
            telemetry=TelemetrySignalAggregator(),
        )

    async def test_build_returns_snapshot(self) -> None:
        builder = self._make_builder()
        snapshot = await builder.build(since=_WEEK_AGO)
        assert isinstance(snapshot, OrgSignalSnapshot)
        assert isinstance(snapshot.performance, OrgPerformanceSummary)
        assert isinstance(snapshot.budget, OrgBudgetSummary)
        assert isinstance(snapshot.coordination, OrgCoordinationSummary)
        assert isinstance(snapshot.scaling, OrgScalingSummary)
        assert isinstance(snapshot.errors, OrgErrorSummary)
        assert isinstance(snapshot.evolution, OrgEvolutionSummary)
        assert isinstance(snapshot.telemetry, OrgTelemetrySummary)

    async def test_build_with_explicit_until(self) -> None:
        builder = self._make_builder()
        snapshot = await builder.build(since=_WEEK_AGO, until=_NOW)
        assert snapshot.collected_at is not None

    async def test_build_parallel_execution(self) -> None:
        """All aggregators should run in parallel."""
        builder = self._make_builder()
        snapshot = await builder.build(since=_WEEK_AGO)
        # Performance aggregator should have been called.
        assert snapshot.performance.agent_count == 1
