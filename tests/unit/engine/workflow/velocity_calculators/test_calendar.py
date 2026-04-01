"""Tests for CalendarVelocityCalculator."""

import pytest

from synthorg.engine.workflow.sprint_velocity import VelocityRecord
from synthorg.engine.workflow.velocity_calculators.calendar import (
    CalendarVelocityCalculator,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType


def _make_record(
    sprint_number: int = 1,
    points_completed: float = 42.0,
    duration_days: int = 14,
    task_count: int | None = 15,
) -> VelocityRecord:
    return VelocityRecord(
        sprint_id=f"sprint-{sprint_number}",
        sprint_number=sprint_number,
        story_points_committed=50.0,
        story_points_completed=points_completed,
        duration_days=duration_days,
        task_completion_count=task_count,
    )


class TestCalendarVelocityCalculator:
    """CalendarVelocityCalculator tests."""

    @pytest.mark.unit
    def test_calculator_type(self) -> None:
        calc = CalendarVelocityCalculator()
        assert calc.calculator_type is VelocityCalcType.CALENDAR

    @pytest.mark.unit
    def test_primary_unit(self) -> None:
        calc = CalendarVelocityCalculator()
        assert calc.primary_unit == "pts/day"

    @pytest.mark.unit
    def test_compute_basic(self) -> None:
        calc = CalendarVelocityCalculator()
        record = _make_record(points_completed=42.0, duration_days=14)
        metrics = calc.compute(record)
        assert metrics.primary_unit == "pts/day"
        assert metrics.primary_value == pytest.approx(42.0 / 14)

    @pytest.mark.unit
    def test_compute_single_day(self) -> None:
        calc = CalendarVelocityCalculator()
        record = _make_record(points_completed=10.0, duration_days=1)
        metrics = calc.compute(record)
        assert metrics.primary_value == pytest.approx(10.0)

    @pytest.mark.unit
    def test_compute_includes_secondary(self) -> None:
        calc = CalendarVelocityCalculator()
        record = _make_record(points_completed=42.0, duration_days=14)
        metrics = calc.compute(record)
        assert metrics.secondary["pts_per_sprint"] == 42.0
        assert metrics.secondary["duration_days"] == 14.0

    @pytest.mark.unit
    def test_compute_zero_points(self) -> None:
        calc = CalendarVelocityCalculator()
        record = _make_record(points_completed=0.0, duration_days=14)
        metrics = calc.compute(record)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_basic(self) -> None:
        calc = CalendarVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=28.0, duration_days=14),
            _make_record(sprint_number=2, points_completed=21.0, duration_days=7),
            _make_record(sprint_number=3, points_completed=42.0, duration_days=14),
        ]
        metrics = calc.rolling_average(records, window=3)
        # Total: 91 pts / 35 days = 2.6 pts/day
        assert metrics.primary_value == pytest.approx(91.0 / 35)
        assert metrics.primary_unit == "pts/day"

    @pytest.mark.unit
    def test_rolling_average_window_smaller_than_records(self) -> None:
        calc = CalendarVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=14.0, duration_days=7),
            _make_record(sprint_number=2, points_completed=28.0, duration_days=14),
            _make_record(sprint_number=3, points_completed=42.0, duration_days=14),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Last 2: 70 pts / 28 days = 2.5
        assert metrics.primary_value == pytest.approx(70.0 / 28)

    @pytest.mark.unit
    def test_rolling_average_empty_records(self) -> None:
        calc = CalendarVelocityCalculator()
        metrics = calc.rolling_average([], window=3)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_includes_secondary(self) -> None:
        calc = CalendarVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=28.0, duration_days=14),
            _make_record(sprint_number=2, points_completed=14.0, duration_days=7),
        ]
        metrics = calc.rolling_average(records, window=2)
        assert metrics.secondary["total_days"] == 21.0
        assert metrics.secondary["sprints_averaged"] == 2.0

    @pytest.mark.unit
    def test_rolling_average_mixed_durations_weighted(self) -> None:
        """Verify duration-weighted averaging: a 14-day sprint weighs 2x a 7-day."""
        calc = CalendarVelocityCalculator()
        records = [
            # 2 pts/day for 14 days
            _make_record(sprint_number=1, points_completed=28.0, duration_days=14),
            # 4 pts/day for 7 days
            _make_record(sprint_number=2, points_completed=28.0, duration_days=7),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Weighted: 56 pts / 21 days = 2.667 pts/day
        assert metrics.primary_value == pytest.approx(56.0 / 21)
