"""Tests for velocity calculation types and metrics models."""

import pytest

from synthorg.engine.workflow.velocity_types import (
    VelocityCalcType,
    VelocityMetrics,
)


class TestVelocityCalcType:
    """VelocityCalcType enum tests."""

    @pytest.mark.unit
    def test_has_five_members(self) -> None:
        assert len(VelocityCalcType) == 5

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "member",
        [
            "task_driven",
            "calendar",
            "multi_dimensional",
            "budget",
            "points_per_sprint",
        ],
    )
    def test_member_values(self, member: str) -> None:
        assert member in [m.value for m in VelocityCalcType]

    @pytest.mark.unit
    def test_is_str_enum(self) -> None:
        assert isinstance(VelocityCalcType.TASK_DRIVEN, str)


class TestVelocityMetrics:
    """VelocityMetrics model tests."""

    @pytest.mark.unit
    def test_basic_construction(self) -> None:
        metrics = VelocityMetrics(
            primary_value=2.8,
            primary_unit="pts/task",
        )
        assert metrics.primary_value == 2.8
        assert metrics.primary_unit == "pts/task"
        assert metrics.secondary == {}

    @pytest.mark.unit
    def test_with_secondary_metrics(self) -> None:
        metrics = VelocityMetrics(
            primary_value=42.0,
            primary_unit="pts/sprint",
            secondary={"pts_per_day": 3.0, "completion_ratio": 0.93},
        )
        assert metrics.secondary["pts_per_day"] == 3.0
        assert metrics.secondary["completion_ratio"] == 0.93

    @pytest.mark.unit
    def test_frozen(self) -> None:
        metrics = VelocityMetrics(
            primary_value=1.0,
            primary_unit="pts/task",
        )
        with pytest.raises(Exception, match="frozen"):
            metrics.primary_value = 2.0  # type: ignore[misc]

    @pytest.mark.unit
    def test_primary_value_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            VelocityMetrics(primary_value=-1.0, primary_unit="pts/task")

    @pytest.mark.unit
    def test_primary_unit_not_blank(self) -> None:
        with pytest.raises(ValueError, match="string_too_short"):
            VelocityMetrics(primary_value=1.0, primary_unit="")

    @pytest.mark.unit
    def test_rejects_nan(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            VelocityMetrics(
                primary_value=float("nan"),
                primary_unit="pts/task",
            )

    @pytest.mark.unit
    def test_rejects_inf(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            VelocityMetrics(
                primary_value=float("inf"),
                primary_unit="pts/task",
            )

    @pytest.mark.unit
    def test_zero_primary_value(self) -> None:
        metrics = VelocityMetrics(
            primary_value=0.0,
            primary_unit="pts/task",
        )
        assert metrics.primary_value == 0.0
