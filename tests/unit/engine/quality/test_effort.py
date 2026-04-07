"""Tests for accuracy-effort ratio computation."""

import pytest

from synthorg.engine.quality.effort import compute_accuracy_effort
from synthorg.engine.quality.models import StepQuality, StepQualitySignal


def _signal(quality: StepQuality, step_index: int = 0) -> StepQualitySignal:
    """Helper to build a minimal StepQualitySignal."""
    return StepQualitySignal(
        quality=quality,
        confidence=0.7,
        reason="test",
        step_index=step_index,
        turn_range=(1, 1),
    )


@pytest.mark.unit
class TestComputeAccuracyEffort:
    """compute_accuracy_effort pure function tests."""

    def test_all_correct(self) -> None:
        signals = tuple(_signal(StepQuality.CORRECT, i) for i in range(3))
        result = compute_accuracy_effort(signals)
        assert result.accuracy == 1.0
        assert result.correct_steps == 3
        assert result.neutral_steps == 0
        assert result.incorrect_steps == 0
        assert result.total_steps == 3

    def test_all_incorrect(self) -> None:
        signals = tuple(_signal(StepQuality.INCORRECT, i) for i in range(3))
        result = compute_accuracy_effort(signals)
        assert result.accuracy == 0.0
        assert result.ratio == 0.0

    def test_all_neutral(self) -> None:
        signals = tuple(_signal(StepQuality.NEUTRAL, i) for i in range(4))
        result = compute_accuracy_effort(signals)
        assert result.accuracy == 0.0
        assert result.neutral_steps == 4

    def test_mixed_signals(self) -> None:
        signals = (
            _signal(StepQuality.CORRECT, 0),
            _signal(StepQuality.CORRECT, 1),
            _signal(StepQuality.NEUTRAL, 2),
            _signal(StepQuality.INCORRECT, 3),
        )
        result = compute_accuracy_effort(signals)
        assert result.accuracy == pytest.approx(0.5)
        assert result.correct_steps == 2
        assert result.neutral_steps == 1
        assert result.incorrect_steps == 1
        assert result.total_steps == 4

    def test_effort_with_expected_steps(self) -> None:
        signals = tuple(_signal(StepQuality.CORRECT, i) for i in range(6))
        result = compute_accuracy_effort(signals, expected_steps=3)
        # effort = 6 / 3 = 2.0 (took twice as many steps as expected)
        assert result.effort == pytest.approx(2.0)
        # ratio = 1.0 / 2.0 = 0.5
        assert result.ratio == pytest.approx(0.5)

    def test_effort_without_expected_steps_defaults_to_total(self) -> None:
        signals = tuple(_signal(StepQuality.CORRECT, i) for i in range(5))
        result = compute_accuracy_effort(signals, expected_steps=0)
        # effort = 5 / 5 = 1.0 (denominator defaults to len(signals))
        assert result.effort == pytest.approx(1.0)

    def test_effort_with_negative_expected_steps(self) -> None:
        signals = (_signal(StepQuality.CORRECT, 0),)
        result = compute_accuracy_effort(signals, expected_steps=-1)
        # Negative expected_steps -> defaults to total
        assert result.effort == pytest.approx(1.0)

    def test_single_correct_step(self) -> None:
        signals = (_signal(StepQuality.CORRECT, 0),)
        result = compute_accuracy_effort(signals)
        assert result.accuracy == 1.0
        assert result.effort == 1.0
        assert result.ratio == 1.0

    def test_empty_signals_raises(self) -> None:
        with pytest.raises(ValueError, match="empty signals"):
            compute_accuracy_effort(())

    def test_step_count_invariant(self) -> None:
        signals = (
            _signal(StepQuality.CORRECT, 0),
            _signal(StepQuality.NEUTRAL, 1),
            _signal(StepQuality.INCORRECT, 2),
        )
        result = compute_accuracy_effort(signals)
        total = result.correct_steps + result.neutral_steps + result.incorrect_steps
        assert total == result.total_steps

    def test_fewer_steps_than_expected(self) -> None:
        signals = (_signal(StepQuality.CORRECT, 0),)
        result = compute_accuracy_effort(signals, expected_steps=5)
        # effort = 1 / 5 = 0.2
        assert result.effort == pytest.approx(0.2)
        # ratio = 1.0 / 0.2 = 5.0 (very efficient)
        assert result.ratio == pytest.approx(5.0)
