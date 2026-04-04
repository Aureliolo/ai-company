"""Tests for automated reporting configuration models."""

import pytest

from synthorg.budget.report_config import (
    AutomatedReportingConfig,
    ReportPeriod,
    ReportScheduleConfig,
    ReportTemplateName,
)


@pytest.mark.unit
class TestReportPeriod:
    """Tests for ReportPeriod enum."""

    def test_values(self) -> None:
        assert ReportPeriod.DAILY.value == "daily"
        assert ReportPeriod.WEEKLY.value == "weekly"
        assert ReportPeriod.MONTHLY.value == "monthly"


@pytest.mark.unit
class TestReportTemplateName:
    """Tests for ReportTemplateName enum."""

    def test_values(self) -> None:
        assert ReportTemplateName.SPENDING_SUMMARY.value == "spending_summary"
        assert ReportTemplateName.PERFORMANCE_METRICS.value == "performance_metrics"
        assert ReportTemplateName.TASK_COMPLETION.value == "task_completion"
        assert ReportTemplateName.RISK_TRENDS.value == "risk_trends"
        assert ReportTemplateName.COMPREHENSIVE.value == "comprehensive"


@pytest.mark.unit
class TestReportScheduleConfig:
    """Tests for ReportScheduleConfig."""

    def test_defaults(self) -> None:
        cfg = ReportScheduleConfig()
        assert cfg.enabled is False
        assert cfg.periods == ()
        assert cfg.templates == (ReportTemplateName.COMPREHENSIVE,)

    def test_duplicate_periods_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"[Dd]uplicate"):
            ReportScheduleConfig(
                periods=(ReportPeriod.DAILY, ReportPeriod.DAILY),
            )

    def test_duplicate_templates_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"[Dd]uplicate"):
            ReportScheduleConfig(
                templates=(
                    ReportTemplateName.COMPREHENSIVE,
                    ReportTemplateName.COMPREHENSIVE,
                ),
            )

    def test_frozen(self) -> None:
        cfg = ReportScheduleConfig()
        with pytest.raises(Exception):  # noqa: B017, PT011
            cfg.enabled = True  # type: ignore[misc]


@pytest.mark.unit
class TestAutomatedReportingConfig:
    """Tests for AutomatedReportingConfig."""

    def test_defaults(self) -> None:
        cfg = AutomatedReportingConfig()
        assert cfg.retention_days == 90
        assert isinstance(cfg.schedule, ReportScheduleConfig)

    def test_retention_bounds(self) -> None:
        with pytest.raises(ValueError, match=r"retention_days"):
            AutomatedReportingConfig(retention_days=0)
        with pytest.raises(ValueError, match=r"retention_days"):
            AutomatedReportingConfig(retention_days=366)

    def test_valid_retention(self) -> None:
        cfg = AutomatedReportingConfig(retention_days=30)
        assert cfg.retention_days == 30
