"""Tests for budget signal source."""

from datetime import UTC, datetime

import pytest

from synthorg.budget.enums import BudgetAlertLevel
from synthorg.budget.spending_summary import (
    PeriodSpending,
    SpendingSummary,
)
from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.signals.budget import BudgetSignalSource

_AGENT_IDS = (NotBlankStr("a1"),)
_START = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
_END = datetime(2026, 4, 30, 23, 59, 59, tzinfo=UTC)


def _make_summary(
    *,
    used_percent: float = 50.0,
    alert: BudgetAlertLevel = BudgetAlertLevel.NORMAL,
) -> SpendingSummary:
    return SpendingSummary(
        period=PeriodSpending(
            total_cost=100.0,
            currency="EUR",
            record_count=10,
            start=_START,
            end=_END,
        ),
        budget_total_monthly=1000.0,
        budget_used_percent=used_percent,
        alert_level=alert,
    )


@pytest.mark.unit
class TestBudgetSignalSource:
    """BudgetSignalSource signal collection."""

    async def test_no_summary_fails_closed_returns_max_burn_and_hard_stop(
        self,
    ) -> None:
        source = BudgetSignalSource()
        signals = await source.collect(_AGENT_IDS, summary=None)
        by_name = {s.name: s.value for s in signals}
        # Fail-closed: assume maximum burn and hard-stop alert when summary unavailable
        assert by_name["burn_rate_percent"] == 100.0
        assert by_name["alert_level"] == 3.0

    @pytest.mark.parametrize(
        ("used_percent", "alert_level_enum", "expected_alert_value"),
        [
            (30.0, BudgetAlertLevel.NORMAL, 0.0),
            (70.0, BudgetAlertLevel.WARNING, 1.0),
            (90.0, BudgetAlertLevel.CRITICAL, 2.0),
            (100.0, BudgetAlertLevel.HARD_STOP, 3.0),
        ],
        ids=[
            "normal-alert-level",
            "warning-alert-level",
            "critical-alert-level",
            "hard-stop-alert-level",
        ],
    )
    async def test_alert_level_mapping(
        self,
        used_percent: float,
        alert_level_enum: BudgetAlertLevel,
        expected_alert_value: float,
    ) -> None:
        source = BudgetSignalSource()
        summary = _make_summary(used_percent=used_percent, alert=alert_level_enum)
        signals = await source.collect(_AGENT_IDS, summary=summary)
        by_name = {s.name: s.value for s in signals}
        assert by_name["burn_rate_percent"] == used_percent
        assert by_name["alert_level"] == expected_alert_value

    async def test_source_name(self) -> None:
        source = BudgetSignalSource()
        assert source.name == "budget"

    async def test_signal_source_field(self) -> None:
        source = BudgetSignalSource()
        summary = _make_summary()
        signals = await source.collect(_AGENT_IDS, summary=summary)
        assert all(s.source == "budget" for s in signals)
