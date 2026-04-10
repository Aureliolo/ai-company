"""Unit tests for report strategy implementations."""

import json

import pytest

from synthorg.client.models import SimulationMetrics
from synthorg.client.protocols import ReportStrategy
from synthorg.client.report import (
    DetailedReport,
    JsonExportReport,
    MetricsOnlyReport,
    SummaryReport,
)

pytestmark = pytest.mark.unit


def _metrics() -> SimulationMetrics:
    return SimulationMetrics(
        total_requirements=20,
        total_tasks_created=15,
        tasks_accepted=10,
        tasks_rejected=3,
        tasks_reworked=2,
        avg_review_rounds=1.5,
        round_metrics=(
            {"round": 1, "accepted": 5},
            {"round": 2, "accepted": 5},
        ),
    )


class TestSummaryReport:
    def test_protocol_compatible(self) -> None:
        assert isinstance(SummaryReport(), ReportStrategy)

    async def test_summary_structure(self) -> None:
        report = await SummaryReport().generate_report(_metrics())
        assert report["format"] == "summary"
        assert report["totals"]["requirements"] == 20
        assert report["rates"]["acceptance_rate"] == pytest.approx(10 / 15)

    async def test_summary_has_no_per_round_detail(self) -> None:
        report = await SummaryReport().generate_report(_metrics())
        assert "per_round" not in report


class TestDetailedReport:
    def test_protocol_compatible(self) -> None:
        assert isinstance(DetailedReport(), ReportStrategy)

    async def test_detailed_includes_per_round(self) -> None:
        report = await DetailedReport().generate_report(_metrics())
        assert report["format"] == "detailed"
        assert "summary" in report
        assert len(report["per_round"]) == 2
        assert report["per_round"][0]["round"] == 1

    async def test_summary_narrative_text(self) -> None:
        report = await DetailedReport().generate_report(_metrics())
        assert "20 requirements" in report["summary"]
        assert "%" in report["summary"]


class TestMetricsOnlyReport:
    def test_protocol_compatible(self) -> None:
        assert isinstance(MetricsOnlyReport(), ReportStrategy)

    async def test_returns_raw_model_dump(self) -> None:
        report = await MetricsOnlyReport().generate_report(_metrics())
        assert report["total_requirements"] == 20
        assert report["total_tasks_created"] == 15
        # Computed fields are included in model_dump.
        assert "acceptance_rate" in report


class TestJsonExportReport:
    def test_protocol_compatible(self) -> None:
        assert isinstance(JsonExportReport(), ReportStrategy)

    async def test_envelope_structure(self) -> None:
        report = await JsonExportReport().generate_report(_metrics())
        assert report["format"] == "json_export"
        assert "schema_version" in report
        assert "exported_at" in report
        assert report["metrics"]["total_requirements"] == 20

    async def test_json_serializable(self) -> None:
        report = await JsonExportReport().generate_report(_metrics())
        encoded = json.dumps(report, default=str)
        assert "total_requirements" in encoded
