"""Tests for PointsPerSprintVelocityCalculator."""

import pytest

from synthorg.engine.workflow.sprint_velocity import VelocityRecord
from synthorg.engine.workflow.velocity_calculators.points_per_sprint import (
    PointsPerSprintVelocityCalculator,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType


def _make_record(
    sprint_number: int = 1,
    points_committed: float = 50.0,
    points_completed: float = 42.0,
) -> VelocityRecord:
    return VelocityRecord(
        sprint_id=f"sprint-{sprint_number}",
        sprint_number=sprint_number,
        story_points_committed=points_committed,
        story_points_completed=points_completed,
        duration_days=14,
        task_completion_count=10,
    )


class TestPointsPerSprintVelocityCalculator:
    """PointsPerSprintVelocityCalculator tests."""

    @pytest.mark.unit
    def test_calculator_type(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        assert calc.calculator_type is VelocityCalcType.POINTS_PER_SPRINT

    @pytest.mark.unit
    def test_primary_unit(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        assert calc.primary_unit == "pts/sprint"

    @pytest.mark.unit
    def test_compute_basic(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        record = _make_record(points_completed=42.0)
        metrics = calc.compute(record)
        assert metrics.primary_unit == "pts/sprint"
        assert metrics.primary_value == pytest.approx(42.0)

    @pytest.mark.unit
    def test_compute_secondary_completion_ratio(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        record = _make_record(points_committed=50.0, points_completed=40.0)
        metrics = calc.compute(record)
        assert metrics.secondary["completion_ratio"] == pytest.approx(0.8)

    @pytest.mark.unit
    def test_compute_zero_committed(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        record = _make_record(points_committed=0.0, points_completed=0.0)
        metrics = calc.compute(record)
        assert metrics.primary_value == 0.0
        assert metrics.secondary["completion_ratio"] == 0.0

    @pytest.mark.unit
    def test_rolling_average_basic(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=30.0),
            _make_record(sprint_number=2, points_completed=40.0),
            _make_record(sprint_number=3, points_completed=50.0),
        ]
        metrics = calc.rolling_average(records, window=3)
        # Average: (30 + 40 + 50) / 3 = 40.0
        assert metrics.primary_value == pytest.approx(40.0)
        assert metrics.primary_unit == "pts/sprint"

    @pytest.mark.unit
    def test_rolling_average_window_smaller_than_records(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        records = [
            _make_record(sprint_number=1, points_completed=10.0),
            _make_record(sprint_number=2, points_completed=20.0),
            _make_record(sprint_number=3, points_completed=30.0),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Last 2: (20 + 30) / 2 = 25.0
        assert metrics.primary_value == pytest.approx(25.0)

    @pytest.mark.unit
    def test_rolling_average_empty_records(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        metrics = calc.rolling_average([], window=3)
        assert metrics.primary_value == 0.0

    @pytest.mark.unit
    def test_rolling_average_secondary_completion_ratio(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        records = [
            _make_record(
                sprint_number=1,
                points_committed=50.0,
                points_completed=40.0,
            ),
            _make_record(
                sprint_number=2,
                points_committed=50.0,
                points_completed=50.0,
            ),
        ]
        metrics = calc.rolling_average(records, window=2)
        # Mean ratio: (0.8 + 1.0) / 2 = 0.9
        assert metrics.secondary["completion_ratio"] == pytest.approx(0.9)
        assert metrics.secondary["sprints_averaged"] == 2.0

    @pytest.mark.unit
    def test_rolling_average_zero_window(self) -> None:
        calc = PointsPerSprintVelocityCalculator()
        records = [_make_record(points_completed=42.0)]
        metrics = calc.rolling_average(records, window=0)
        assert metrics.primary_value == 0.0
