"""Tests for BudgetVelocityCalculator."""

import pytest

from synthorg.engine.workflow.sprint_velocity import VelocityRecord
from synthorg.engine.workflow.velocity_calculator import VelocityCalculator
from synthorg.engine.workflow.velocity_calculators.budget import (
    BudgetVelocityCalculator,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType


def _make_record(
    sprint_number: int = 1,
    points_committed: float = 50.0,
    points_completed: float = 42.0,
    budget_consumed: float | None = 10.0,
) -> VelocityRecord:
    return VelocityRecord(
        sprint_id=f"sprint-{sprint_number}",
        sprint_number=sprint_number,
        story_points_committed=points_committed,
        story_points_completed=points_completed,
        duration_days=14,
        task_completion_count=10,
        budget_consumed=budget_consumed,
    )


class TestBudgetVelocityCalculatorProtocol:
    """Verify BudgetVelocityCalculator satisfies the protocol."""

    @pytest.mark.unit
    def test_is_protocol_instance(self) -> None:
        calc = BudgetVelocityCalculator()
        assert isinstance(calc, VelocityCalculator)


class TestBudgetVelocityCalculator:
    """BudgetVelocityCalculator tests."""

    @pytest.mark.unit
    def test_calculator_type(self) -> None:
        calc = BudgetVelocityCalculator()
        assert calc.calculator_type is VelocityCalcType.BUDGET

    @pytest.mark.unit
    def test_primary_unit(self) -> None:
        calc = BudgetVelocityCalculator()
        assert calc.primary_unit == "pts/USD"

    @pytest.mark.unit
    def test_compute_basic(self) -> None:
        calc = BudgetVelocityCalculator()
        record = _make_record(points_completed=42.0, budget_consumed=10.0)
        metrics = calc.compute(record)
        assert metrics.primary_unit == "pts/USD"
        assert metrics.primary_value == pytest.approx(4.2)

    @pytest.mark.unit
    def test_compute_zero_budget(self) -> None:
        calc = BudgetVelocityCalculator()
        record = _make_record(points_completed=42.0, budget_consumed=0.0)
        metrics = calc.compute(record)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_compute_none_budget(self) -> None:
        calc = BudgetVelocityCalculator()
        record = _make_record(points_completed=42.0, budget_consumed=None)
        metrics = calc.compute(record)
        assert metrics.primary_value == 0.0
        assert metrics.secondary["pts_per_sprint"] == 42.0

    @pytest.mark.unit
    def test_compute_includes_secondary(self) -> None:
        calc = BudgetVelocityCalculator()
        record = _make_record(
            points_committed=50.0,
            points_completed=40.0,
            budget_consumed=10.0,
        )
        metrics = calc.compute(record)
        assert metrics.secondary["pts_per_sprint"] == 40.0
        assert metrics.secondary["budget_consumed"] == 10.0
        assert metrics.secondary["completion_ratio"] == pytest.approx(0.8)

    @pytest.mark.unit
    def test_rolling_average_basic(self) -> None:
        calc = BudgetVelocityCalculator()
        records = [
            _make_record(
                sprint_number=1,
                points_completed=30.0,
                budget_consumed=10.0,
            ),
            _make_record(
                sprint_number=2,
                points_completed=40.0,
                budget_consumed=20.0,
            ),
            _make_record(
                sprint_number=3,
                points_completed=50.0,
                budget_consumed=10.0,
            ),
        ]
        metrics = calc.rolling_average(records, window=3)
        # Total: 120 pts / 40 USD = 3.0
        assert metrics.primary_value == pytest.approx(3.0)
        assert metrics.primary_unit == "pts/USD"

    @pytest.mark.unit
    def test_rolling_average_skips_none_budget(self) -> None:
        calc = BudgetVelocityCalculator()
        records = [
            _make_record(
                sprint_number=1,
                points_completed=30.0,
                budget_consumed=10.0,
            ),
            _make_record(
                sprint_number=2,
                points_completed=40.0,
                budget_consumed=None,
            ),
            _make_record(
                sprint_number=3,
                points_completed=50.0,
                budget_consumed=10.0,
            ),
        ]
        metrics = calc.rolling_average(records, window=3)
        # Only sprint 1 and 3: 80 pts / 20 USD = 4.0
        assert metrics.primary_value == pytest.approx(4.0)

    @pytest.mark.unit
    def test_rolling_average_skips_zero_budget(self) -> None:
        calc = BudgetVelocityCalculator()
        records = [
            _make_record(
                sprint_number=1,
                points_completed=30.0,
                budget_consumed=10.0,
            ),
            _make_record(
                sprint_number=2,
                points_completed=40.0,
                budget_consumed=0.0,
            ),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Only sprint 1: 30 pts / 10 USD = 3.0
        assert metrics.primary_value == pytest.approx(3.0)

    @pytest.mark.unit
    def test_rolling_average_all_none_budget(self) -> None:
        calc = BudgetVelocityCalculator()
        records = [
            _make_record(sprint_number=1, budget_consumed=None),
            _make_record(sprint_number=2, budget_consumed=None),
        ]
        metrics = calc.rolling_average(records, window=2)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_empty_records(self) -> None:
        calc = BudgetVelocityCalculator()
        metrics = calc.rolling_average([], window=3)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_window_smaller_than_records(self) -> None:
        calc = BudgetVelocityCalculator()
        records = [
            _make_record(
                sprint_number=1,
                points_completed=10.0,
                budget_consumed=5.0,
            ),
            _make_record(
                sprint_number=2,
                points_completed=20.0,
                budget_consumed=5.0,
            ),
            _make_record(
                sprint_number=3,
                points_completed=30.0,
                budget_consumed=5.0,
            ),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Last 2: 50 pts / 10 USD = 5.0
        assert metrics.primary_value == pytest.approx(5.0)

    @pytest.mark.unit
    def test_rolling_average_zero_window(self) -> None:
        calc = BudgetVelocityCalculator()
        records = [_make_record(budget_consumed=10.0)]
        metrics = calc.rolling_average(records, window=0)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_sprints_averaged_counts_valid_only(self) -> None:
        calc = BudgetVelocityCalculator()
        records = [
            _make_record(
                sprint_number=1,
                points_completed=30.0,
                budget_consumed=10.0,
            ),
            _make_record(
                sprint_number=2,
                points_completed=40.0,
                budget_consumed=None,
            ),
            _make_record(
                sprint_number=3,
                points_completed=50.0,
                budget_consumed=10.0,
            ),
        ]
        metrics = calc.rolling_average(records, window=3)
        # 3 records in window, but only 2 have valid budget
        assert metrics.secondary["sprints_averaged"] == 2.0
