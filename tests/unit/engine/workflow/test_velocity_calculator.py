"""Tests for VelocityCalculator protocol conformance."""

from collections.abc import Sequence

import pytest

from synthorg.engine.workflow.sprint_velocity import VelocityRecord
from synthorg.engine.workflow.velocity_calculator import VelocityCalculator
from synthorg.engine.workflow.velocity_types import (
    VelocityCalcType,
    VelocityMetrics,
)


class _StubCalculator:
    """Minimal stub implementing the VelocityCalculator protocol."""

    def compute(self, record: VelocityRecord) -> VelocityMetrics:
        return VelocityMetrics(
            primary_value=record.story_points_completed,
            primary_unit="pts/sprint",
        )

    def rolling_average(
        self,
        records: Sequence[VelocityRecord],
        window: int,
    ) -> VelocityMetrics:
        recent = records[-window:] if records else []
        total = sum(r.story_points_completed for r in recent)
        avg = total / len(recent) if recent else 0.0
        return VelocityMetrics(
            primary_value=avg,
            primary_unit="pts/sprint",
        )

    @property
    def calculator_type(self) -> VelocityCalcType:
        return VelocityCalcType.POINTS_PER_SPRINT

    @property
    def primary_unit(self) -> str:
        return "pts/sprint"


class TestVelocityCalculatorProtocol:
    """Protocol conformance tests."""

    @pytest.mark.unit
    def test_stub_is_instance(self) -> None:
        stub = _StubCalculator()
        assert isinstance(stub, VelocityCalculator)

    @pytest.mark.unit
    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(VelocityCalculator, "__protocol_attrs__")

    @pytest.mark.unit
    def test_compute_returns_metrics(self) -> None:
        stub = _StubCalculator()
        record = VelocityRecord(
            sprint_id="sprint-1",
            sprint_number=1,
            story_points_committed=50.0,
            story_points_completed=42.0,
            duration_days=14,
        )
        result = stub.compute(record)
        assert result.primary_value == 42.0
        assert result.primary_unit == "pts/sprint"

    @pytest.mark.unit
    def test_rolling_average_returns_metrics(self) -> None:
        stub = _StubCalculator()
        records = [
            VelocityRecord(
                sprint_id=f"sprint-{i}",
                sprint_number=i,
                story_points_committed=50.0,
                story_points_completed=float(40 + i),
                duration_days=14,
            )
            for i in range(1, 4)
        ]
        result = stub.rolling_average(records, window=3)
        assert result.primary_value == pytest.approx(42.0)

    @pytest.mark.unit
    def test_calculator_type(self) -> None:
        stub = _StubCalculator()
        assert stub.calculator_type is VelocityCalcType.POINTS_PER_SPRINT

    @pytest.mark.unit
    def test_primary_unit(self) -> None:
        stub = _StubCalculator()
        assert stub.primary_unit == "pts/sprint"
