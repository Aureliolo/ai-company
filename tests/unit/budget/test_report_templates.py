"""Tests for automated report template models."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.budget.report_config import ReportPeriod
from synthorg.budget.report_templates import (
    AgentPerformanceSummary,
    ComprehensiveReport,
    DailyRiskPoint,
    DepartmentTaskSummary,
    PerformanceMetricsReport,
    RiskTrendsReport,
    TaskCompletionReport,
)


@pytest.mark.unit
class TestAgentPerformanceSummary:
    """Tests for AgentPerformanceSummary."""

    def test_construction(self) -> None:
        summary = AgentPerformanceSummary(
            agent_id="agent-1",
            tasks_completed=10,
            tasks_failed=1,
            average_quality_score=7.5,
            total_cost=5.0,
            total_risk_units=2.0,
        )
        assert summary.agent_id == "agent-1"
        assert summary.tasks_completed == 10

    def test_frozen(self) -> None:
        summary = AgentPerformanceSummary(agent_id="agent-1")
        with pytest.raises(Exception):  # noqa: B017, PT011
            summary.tasks_completed = 5  # type: ignore[misc]


@pytest.mark.unit
class TestPerformanceMetricsReport:
    """Tests for PerformanceMetricsReport."""

    def test_defaults(self) -> None:
        now = datetime.now(UTC)
        report = PerformanceMetricsReport(generated_at=now)
        assert report.agent_snapshots == ()
        assert report.total_tasks_completed == 0
        assert report.total_tasks_failed == 0

    def test_with_snapshots(self) -> None:
        now = datetime.now(UTC)
        report = PerformanceMetricsReport(
            agent_snapshots=(AgentPerformanceSummary(agent_id="a", tasks_completed=5),),
            total_tasks_completed=5,
            generated_at=now,
        )
        assert len(report.agent_snapshots) == 1


@pytest.mark.unit
class TestTaskCompletionReport:
    """Tests for TaskCompletionReport."""

    def test_completion_rate_computed(self) -> None:
        now = datetime.now(UTC)
        report = TaskCompletionReport(
            total_assigned=10,
            total_completed=7,
            total_failed=2,
            total_in_progress=1,
            generated_at=now,
        )
        assert report.completion_rate == 70.0

    def test_completion_rate_zero_assigned(self) -> None:
        now = datetime.now(UTC)
        report = TaskCompletionReport(generated_at=now)
        assert report.completion_rate == 0.0

    def test_department_breakdown(self) -> None:
        now = datetime.now(UTC)
        report = TaskCompletionReport(
            total_assigned=5,
            total_completed=3,
            by_department=(
                DepartmentTaskSummary(
                    department="engineering",
                    assigned=5,
                    completed=3,
                ),
            ),
            generated_at=now,
        )
        assert len(report.by_department) == 1


@pytest.mark.unit
class TestRiskTrendsReport:
    """Tests for RiskTrendsReport."""

    def test_construction(self) -> None:
        now = datetime.now(UTC)
        report = RiskTrendsReport(
            total_risk_units=5.0,
            risk_by_agent=(("agent-a", 3.0), ("agent-b", 2.0)),
            generated_at=now,
        )
        assert report.total_risk_units == 5.0

    def test_agent_ranking_must_be_descending(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="descending"):
            RiskTrendsReport(
                risk_by_agent=(("agent-a", 1.0), ("agent-b", 2.0)),
                generated_at=now,
            )

    def test_action_type_ranking_must_be_descending(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="descending"):
            RiskTrendsReport(
                risk_by_action_type=(("code:read", 1.0), ("code:write", 2.0)),
                generated_at=now,
            )

    def test_daily_trend(self) -> None:
        now = datetime.now(UTC)
        report = RiskTrendsReport(
            daily_risk_trend=(
                DailyRiskPoint(
                    date=now.date(),
                    total_risk_units=1.0,
                    record_count=5,
                ),
            ),
            generated_at=now,
        )
        assert len(report.daily_risk_trend) == 1


@pytest.mark.unit
class TestComprehensiveReport:
    """Tests for ComprehensiveReport."""

    def test_construction(self) -> None:
        now = datetime.now(UTC)
        report = ComprehensiveReport(
            period=ReportPeriod.DAILY,
            start=now - timedelta(days=1),
            end=now,
            generated_at=now,
        )
        assert report.period == ReportPeriod.DAILY
        assert report.spending is None
        assert report.performance is None
        assert report.task_completion is None
        assert report.risk_trends is None

    def test_frozen(self) -> None:
        now = datetime.now(UTC)
        report = ComprehensiveReport(
            period=ReportPeriod.DAILY,
            start=now - timedelta(days=1),
            end=now,
            generated_at=now,
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            report.period = ReportPeriod.WEEKLY  # type: ignore[misc]
