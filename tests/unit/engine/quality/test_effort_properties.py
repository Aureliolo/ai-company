"""Property-based tests for accuracy-effort computation (Hypothesis)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthorg.engine.quality.effort import compute_accuracy_effort
from synthorg.engine.quality.models import StepQuality, StepQualitySignal


def _signal(quality: StepQuality, step_index: int) -> StepQualitySignal:
    return StepQualitySignal(
        quality=quality,
        confidence=0.7,
        reason="test",
        step_index=step_index,
        turn_range=(1, 1),
    )


_quality_strategy = st.sampled_from(list(StepQuality))


@pytest.mark.unit
class TestAccuracyEffortProperties:
    """Property-based tests for compute_accuracy_effort."""

    @given(
        qualities=st.lists(
            _quality_strategy,
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=10, derandomize=True)
    def test_accuracy_bounded_zero_one(self, qualities: list[StepQuality]) -> None:
        """Accuracy is always in [0, 1]."""
        signals = tuple(_signal(q, i) for i, q in enumerate(qualities))
        result = compute_accuracy_effort(signals)
        assert 0.0 <= result.accuracy <= 1.0

    @given(
        qualities=st.lists(
            _quality_strategy,
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=10, derandomize=True)
    def test_ratio_non_negative(self, qualities: list[StepQuality]) -> None:
        """Ratio is always non-negative."""
        signals = tuple(_signal(q, i) for i, q in enumerate(qualities))
        result = compute_accuracy_effort(signals)
        assert result.ratio >= 0.0

    @given(
        qualities=st.lists(
            _quality_strategy,
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=10, derandomize=True)
    def test_step_count_invariant(self, qualities: list[StepQuality]) -> None:
        """correct + neutral + incorrect always equals total."""
        signals = tuple(_signal(q, i) for i, q in enumerate(qualities))
        result = compute_accuracy_effort(signals)
        total = result.correct_steps + result.neutral_steps + result.incorrect_steps
        assert total == result.total_steps

    @given(
        qualities=st.lists(
            _quality_strategy,
            min_size=1,
            max_size=20,
        ),
        expected_steps=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=10, derandomize=True)
    def test_effort_positive(
        self,
        qualities: list[StepQuality],
        expected_steps: int,
    ) -> None:
        """Effort is always positive."""
        signals = tuple(_signal(q, i) for i, q in enumerate(qualities))
        result = compute_accuracy_effort(signals, expected_steps=expected_steps)
        assert result.effort > 0.0

    @given(
        n_correct=st.integers(min_value=0, max_value=10),
        n_other=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=10, derandomize=True)
    def test_accuracy_monotonic_in_correct_count(
        self,
        n_correct: int,
        n_other: int,
    ) -> None:
        """Adding more correct steps never decreases accuracy."""
        if n_correct + n_other == 0:
            return  # Skip empty case
        base_signals = tuple(
            _signal(StepQuality.CORRECT, i) for i in range(n_correct)
        ) + tuple(_signal(StepQuality.NEUTRAL, n_correct + i) for i in range(n_other))
        base_result = compute_accuracy_effort(base_signals)

        # Add one more correct step.
        extended_signals = (
            *base_signals,
            _signal(StepQuality.CORRECT, n_correct + n_other),
        )
        extended_result = compute_accuracy_effort(extended_signals)

        assert extended_result.accuracy >= base_result.accuracy
