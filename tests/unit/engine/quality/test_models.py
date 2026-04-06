"""Tests for step-level quality signal models."""

import pytest
from pydantic import ValidationError

from synthorg.engine.quality.models import (
    AccuracyEffortRatio,
    StepQuality,
    StepQualitySignal,
)


@pytest.mark.unit
class TestStepQuality:
    """StepQuality enum values."""

    def test_values(self) -> None:
        assert StepQuality.CORRECT.value == "correct"
        assert StepQuality.NEUTRAL.value == "neutral"
        assert StepQuality.INCORRECT.value == "incorrect"

    def test_member_count(self) -> None:
        assert len(StepQuality) == 3


@pytest.mark.unit
class TestStepQualitySignal:
    """StepQualitySignal frozen model validation."""

    def test_valid_signal(self) -> None:
        signal = StepQualitySignal(
            quality=StepQuality.CORRECT,
            confidence=0.7,
            reason="Step completed with tool calls",
            step_index=0,
            turn_range=(1, 3),
        )
        assert signal.quality == StepQuality.CORRECT
        assert signal.confidence == 0.7
        assert signal.step_index == 0
        assert signal.turn_range == (1, 3)

    def test_frozen(self) -> None:
        signal = StepQualitySignal(
            quality=StepQuality.NEUTRAL,
            confidence=0.5,
            reason="Exploratory",
            step_index=0,
            turn_range=(1, 1),
        )
        with pytest.raises(ValidationError):
            signal.quality = StepQuality.CORRECT  # type: ignore[misc]

    def test_confidence_lower_bound(self) -> None:
        signal = StepQualitySignal(
            quality=StepQuality.CORRECT,
            confidence=0.0,
            reason="test",
            step_index=0,
            turn_range=(1, 1),
        )
        assert signal.confidence == 0.0

    def test_confidence_upper_bound(self) -> None:
        signal = StepQualitySignal(
            quality=StepQuality.CORRECT,
            confidence=1.0,
            reason="test",
            step_index=0,
            turn_range=(1, 1),
        )
        assert signal.confidence == 1.0

    def test_confidence_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StepQualitySignal(
                quality=StepQuality.CORRECT,
                confidence=-0.1,
                reason="test",
                step_index=0,
                turn_range=(1, 1),
            )

    def test_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StepQualitySignal(
                quality=StepQuality.CORRECT,
                confidence=1.1,
                reason="test",
                step_index=0,
                turn_range=(1, 1),
            )

    def test_negative_step_index_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StepQualitySignal(
                quality=StepQuality.CORRECT,
                confidence=0.5,
                reason="test",
                step_index=-1,
                turn_range=(1, 1),
            )

    def test_turn_range_start_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError, match="turn_range start must be >= 1"):
            StepQualitySignal(
                quality=StepQuality.CORRECT,
                confidence=0.5,
                reason="test",
                step_index=0,
                turn_range=(0, 1),
            )

    def test_turn_range_end_before_start_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"turn_range end.*must be >= start"):
            StepQualitySignal(
                quality=StepQuality.CORRECT,
                confidence=0.5,
                reason="test",
                step_index=0,
                turn_range=(3, 1),
            )

    def test_single_turn_range(self) -> None:
        signal = StepQualitySignal(
            quality=StepQuality.NEUTRAL,
            confidence=0.5,
            reason="single turn",
            step_index=0,
            turn_range=(5, 5),
        )
        assert signal.turn_range == (5, 5)

    def test_nan_confidence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StepQualitySignal(
                quality=StepQuality.CORRECT,
                confidence=float("nan"),
                reason="test",
                step_index=0,
                turn_range=(1, 1),
            )


@pytest.mark.unit
class TestAccuracyEffortRatio:
    """AccuracyEffortRatio frozen model validation."""

    def test_valid_ratio(self) -> None:
        ratio = AccuracyEffortRatio(
            accuracy=0.8,
            effort=1.0,
            correct_steps=4,
            neutral_steps=1,
            incorrect_steps=0,
            total_steps=5,
        )
        assert ratio.accuracy == 0.8
        assert ratio.effort == 1.0
        assert ratio.ratio == 0.8
        assert ratio.total_steps == 5

    def test_computed_ratio(self) -> None:
        ratio = AccuracyEffortRatio(
            accuracy=0.6,
            effort=1.5,
            correct_steps=3,
            neutral_steps=1,
            incorrect_steps=1,
            total_steps=5,
        )
        assert ratio.ratio == pytest.approx(0.4)

    def test_frozen(self) -> None:
        ratio = AccuracyEffortRatio(
            accuracy=0.5,
            effort=1.0,
            correct_steps=1,
            neutral_steps=1,
            incorrect_steps=0,
            total_steps=2,
        )
        with pytest.raises(ValidationError):
            ratio.accuracy = 0.9  # type: ignore[misc]

    def test_step_count_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="do not sum to total_steps"):
            AccuracyEffortRatio(
                accuracy=0.5,
                effort=1.0,
                correct_steps=2,
                neutral_steps=1,
                incorrect_steps=0,
                total_steps=5,
            )

    def test_zero_total_steps_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AccuracyEffortRatio(
                accuracy=0.0,
                effort=1.0,
                correct_steps=0,
                neutral_steps=0,
                incorrect_steps=0,
                total_steps=0,
            )

    def test_zero_effort_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AccuracyEffortRatio(
                accuracy=0.5,
                effort=0.0,
                correct_steps=1,
                neutral_steps=0,
                incorrect_steps=0,
                total_steps=1,
            )

    def test_all_correct(self) -> None:
        ratio = AccuracyEffortRatio(
            accuracy=1.0,
            effort=1.0,
            correct_steps=3,
            neutral_steps=0,
            incorrect_steps=0,
            total_steps=3,
        )
        assert ratio.ratio == 1.0

    def test_all_incorrect(self) -> None:
        ratio = AccuracyEffortRatio(
            accuracy=0.0,
            effort=1.0,
            correct_steps=0,
            neutral_steps=0,
            incorrect_steps=3,
            total_steps=3,
        )
        assert ratio.ratio == 0.0

    def test_high_effort_reduces_ratio(self) -> None:
        ratio = AccuracyEffortRatio(
            accuracy=0.8,
            effort=2.0,
            correct_steps=4,
            neutral_steps=1,
            incorrect_steps=0,
            total_steps=5,
        )
        assert ratio.ratio == pytest.approx(0.4)

    def test_nan_accuracy_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AccuracyEffortRatio(
                accuracy=float("nan"),
                effort=1.0,
                correct_steps=1,
                neutral_steps=0,
                incorrect_steps=0,
                total_steps=1,
            )
