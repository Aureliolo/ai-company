"""Tests for MultiDimensionalVelocityCalculator."""

import pytest

from synthorg.engine.workflow.sprint_velocity import VelocityRecord
from synthorg.engine.workflow.velocity_calculators.multi_dimensional import (
    MultiDimensionalVelocityCalculator,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType


def _make_record(
    sprint_number: int = 1,
    points_committed: float = 50.0,
    points_completed: float = 42.0,
    duration_days: int = 14,
    task_count: int | None = 15,
) -> VelocityRecord:
    return VelocityRecord(
        sprint_id=f"sprint-{sprint_number}",
        sprint_number=sprint_number,
        story_points_committed=points_committed,
        story_points_completed=points_completed,
        duration_days=duration_days,
        task_completion_count=task_count,
    )


class TestMultiDimensionalVelocityCalculator:
    """MultiDimensionalVelocityCalculator tests."""

    @pytest.mark.unit
    def test_calculator_type(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        assert calc.calculator_type is VelocityCalcType.MULTI_DIMENSIONAL

    @pytest.mark.unit
    def test_primary_unit(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        assert calc.primary_unit == "pts/sprint"

    @pytest.mark.unit
    def test_compute_basic(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        record = _make_record(
            points_committed=50.0,
            points_completed=42.0,
            duration_days=14,
            task_count=15,
        )
        metrics = calc.compute(record)
        assert metrics.primary_unit == "pts/sprint"
        assert metrics.primary_value == pytest.approx(42.0)

    @pytest.mark.unit
    def test_compute_secondary_pts_per_task(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        record = _make_record(points_completed=30.0, task_count=10)
        metrics = calc.compute(record)
        assert metrics.secondary["pts_per_task"] == pytest.approx(3.0)

    @pytest.mark.unit
    def test_compute_secondary_pts_per_day(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        record = _make_record(points_completed=42.0, duration_days=14)
        metrics = calc.compute(record)
        assert metrics.secondary["pts_per_day"] == pytest.approx(3.0)

    @pytest.mark.unit
    def test_compute_secondary_completion_ratio(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        record = _make_record(points_committed=50.0, points_completed=42.0)
        metrics = calc.compute(record)
        assert metrics.secondary["completion_ratio"] == pytest.approx(42.0 / 50.0)

    @pytest.mark.unit
    def test_compute_no_task_count(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        record = _make_record(points_completed=42.0, task_count=None)
        metrics = calc.compute(record)
        assert metrics.primary_value == pytest.approx(42.0)
        assert metrics.secondary["pts_per_task"] == 0.0
        # pts_per_day still computed.
        assert metrics.secondary["pts_per_day"] == pytest.approx(42.0 / 14)

    @pytest.mark.unit
    def test_compute_zero_task_count(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        record = _make_record(points_completed=42.0, task_count=0)
        metrics = calc.compute(record)
        assert metrics.secondary["pts_per_task"] == 0.0

    @pytest.mark.unit
    def test_compute_zero_committed(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        record = _make_record(points_committed=0.0, points_completed=0.0)
        metrics = calc.compute(record)
        assert metrics.secondary["completion_ratio"] == 0.0

    @pytest.mark.unit
    def test_rolling_average_basic(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        records = [
            _make_record(
                sprint_number=1,
                points_completed=30.0,
                duration_days=14,
                task_count=10,
            ),
            _make_record(
                sprint_number=2,
                points_completed=40.0,
                duration_days=14,
                task_count=10,
            ),
            _make_record(
                sprint_number=3,
                points_completed=50.0,
                duration_days=14,
                task_count=10,
            ),
        ]
        metrics = calc.rolling_average(records, window=3)
        # Primary: avg pts/sprint = 120/3 = 40.0
        assert metrics.primary_value == pytest.approx(40.0)
        assert metrics.primary_unit == "pts/sprint"

    @pytest.mark.unit
    def test_rolling_average_secondary_pts_per_day(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=28.0, duration_days=14),
            _make_record(sprint_number=2, points_completed=21.0, duration_days=7),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Weighted: 49 pts / 21 days = 2.333
        assert metrics.secondary["pts_per_day"] == pytest.approx(49.0 / 21)

    @pytest.mark.unit
    def test_rolling_average_secondary_pts_per_task(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=30.0, task_count=10),
            _make_record(sprint_number=2, points_completed=40.0, task_count=10),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Weighted: 70 pts / 20 tasks = 3.5
        assert metrics.secondary["pts_per_task"] == pytest.approx(3.5)

    @pytest.mark.unit
    def test_rolling_average_secondary_completion_ratio(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_committed=50.0, points_completed=40.0),
            _make_record(sprint_number=2, points_committed=50.0, points_completed=50.0),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Average: (40/50 + 50/50) / 2 = 0.9
        assert metrics.secondary["completion_ratio"] == pytest.approx(0.9)

    @pytest.mark.unit
    def test_rolling_average_empty_records(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        metrics = calc.rolling_average([], window=3)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_window_smaller_than_records(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=10.0),
            _make_record(sprint_number=2, points_completed=20.0),
            _make_record(sprint_number=3, points_completed=30.0),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Last 2: (20+30)/2 = 25
        assert metrics.primary_value == pytest.approx(25.0)

    @pytest.mark.unit
    def test_rolling_average_skips_none_task_count_for_pts_per_task(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=30.0, task_count=10),
            _make_record(sprint_number=2, points_completed=40.0, task_count=None),
            _make_record(sprint_number=3, points_completed=50.0, task_count=10),
        ]
        metrics = calc.rolling_average(records, window=3)
        # pts_per_task: only sprints 1+3 = 80 pts / 20 tasks = 4.0
        assert metrics.secondary["pts_per_task"] == pytest.approx(4.0)
        # pts_per_day still uses all 3.
        total_days = 14 * 3
        assert metrics.secondary["pts_per_day"] == pytest.approx(120.0 / total_days)

    @pytest.mark.unit
    def test_rolling_average_all_none_task_count(self) -> None:
        calc = MultiDimensionalVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=30.0, task_count=None),
            _make_record(sprint_number=2, points_completed=40.0, task_count=None),
        ]
        metrics = calc.rolling_average(records, window=2)
        assert metrics.secondary["pts_per_task"] == 0.0
