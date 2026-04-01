"""Tests for TaskDrivenVelocityCalculator."""

import pytest

from synthorg.engine.workflow.sprint_velocity import VelocityRecord
from synthorg.engine.workflow.velocity_calculators.task_driven import (
    TaskDrivenVelocityCalculator,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType


def _make_record(
    sprint_number: int = 1,
    points_completed: float = 42.0,
    task_count: int | None = 15,
) -> VelocityRecord:
    return VelocityRecord(
        sprint_id=f"sprint-{sprint_number}",
        sprint_number=sprint_number,
        story_points_committed=50.0,
        story_points_completed=points_completed,
        duration_days=14,
        task_completion_count=task_count,
    )


class TestTaskDrivenVelocityCalculator:
    """TaskDrivenVelocityCalculator tests."""

    @pytest.mark.unit
    def test_calculator_type(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        assert calc.calculator_type is VelocityCalcType.TASK_DRIVEN

    @pytest.mark.unit
    def test_primary_unit(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        assert calc.primary_unit == "pts/task"

    @pytest.mark.unit
    def test_compute_basic(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        record = _make_record(points_completed=42.0, task_count=15)
        metrics = calc.compute(record)
        assert metrics.primary_unit == "pts/task"
        assert metrics.primary_value == pytest.approx(42.0 / 15)

    @pytest.mark.unit
    def test_compute_zero_tasks(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        record = _make_record(points_completed=42.0, task_count=0)
        metrics = calc.compute(record)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_compute_none_task_count(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        record = _make_record(points_completed=42.0, task_count=None)
        metrics = calc.compute(record)
        assert metrics.primary_value == 0.0
        assert metrics.secondary["pts_per_sprint"] == 42.0

    @pytest.mark.unit
    def test_compute_includes_secondary(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        record = _make_record(points_completed=30.0, task_count=10)
        metrics = calc.compute(record)
        assert metrics.secondary["pts_per_sprint"] == 30.0
        assert metrics.secondary["task_count"] == 10.0

    @pytest.mark.unit
    def test_rolling_average_basic(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=30.0, task_count=10),
            _make_record(sprint_number=2, points_completed=40.0, task_count=10),
            _make_record(sprint_number=3, points_completed=50.0, task_count=10),
        ]
        metrics = calc.rolling_average(records, window=3)
        # Total: 120 pts / 30 tasks = 4.0
        assert metrics.primary_value == pytest.approx(4.0)
        assert metrics.primary_unit == "pts/task"

    @pytest.mark.unit
    def test_rolling_average_window_smaller_than_records(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=10.0, task_count=5),
            _make_record(sprint_number=2, points_completed=20.0, task_count=5),
            _make_record(sprint_number=3, points_completed=30.0, task_count=5),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Last 2: 50 pts / 10 tasks = 5.0
        assert metrics.primary_value == pytest.approx(5.0)

    @pytest.mark.unit
    def test_rolling_average_empty_records(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        metrics = calc.rolling_average([], window=3)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_skips_none_task_count(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=30.0, task_count=10),
            _make_record(sprint_number=2, points_completed=40.0, task_count=None),
            _make_record(sprint_number=3, points_completed=50.0, task_count=10),
        ]
        metrics = calc.rolling_average(records, window=3)
        # Only sprint 1 and 3: 80 pts / 20 tasks = 4.0
        assert metrics.primary_value == pytest.approx(4.0)

    @pytest.mark.unit
    def test_rolling_average_all_none_task_count(self) -> None:
        calc = TaskDrivenVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=30.0, task_count=None),
            _make_record(sprint_number=2, points_completed=40.0, task_count=None),
        ]
        metrics = calc.rolling_average(records, window=2)
        assert metrics.primary_value == 0.0
