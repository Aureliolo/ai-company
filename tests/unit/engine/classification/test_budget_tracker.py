"""Tests for ClassificationBudgetTracker."""

import pytest

from synthorg.engine.classification.budget_tracker import (
    ClassificationBudgetTracker,
)


@pytest.mark.unit
class TestClassificationBudgetTracker:
    """ClassificationBudgetTracker spend tracking."""

    def test_initial_state(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        assert tracker.remaining_usd == 0.10
        assert tracker.total_spent_usd == 0.0

    def test_can_spend_within_budget(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        assert tracker.can_spend(0.05) is True

    def test_can_spend_exact_budget(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        assert tracker.can_spend(0.10) is True

    def test_cannot_spend_over_budget(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        assert tracker.can_spend(0.11) is False

    def test_record_reduces_remaining(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        tracker.record(0.03)
        assert tracker.total_spent_usd == pytest.approx(0.03)
        assert tracker.remaining_usd == pytest.approx(0.07)

    def test_record_then_cannot_spend(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        tracker.record(0.08)
        assert tracker.can_spend(0.05) is False
        assert tracker.can_spend(0.02) is True

    def test_remaining_never_negative(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        tracker.record(0.15)
        assert tracker.remaining_usd == 0.0

    def test_zero_budget(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.0)
        assert tracker.can_spend(0.0) is True
        assert tracker.can_spend(0.001) is False

    def test_negative_budget_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            ClassificationBudgetTracker(budget_usd=-0.01)

    def test_negative_estimated_cost_rejected(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        with pytest.raises(ValueError, match="non-negative"):
            tracker.can_spend(-0.01)

    def test_negative_actual_cost_rejected(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        with pytest.raises(ValueError, match="non-negative"):
            tracker.record(-0.01)

    def test_multiple_records(self) -> None:
        tracker = ClassificationBudgetTracker(budget_usd=0.10)
        tracker.record(0.02)
        tracker.record(0.03)
        tracker.record(0.01)
        assert tracker.total_spent_usd == pytest.approx(0.06)
        assert tracker.remaining_usd == pytest.approx(0.04)
