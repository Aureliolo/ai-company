"""Tests for the denial tracker (deny-and-continue with retry tracking)."""

import pytest

from synthorg.security.denial_tracker import DenialAction, DenialTracker


@pytest.mark.unit
class TestDenialTracker:
    """DenialTracker unit tests."""

    def test_first_denial_returns_retry(self) -> None:
        """First denial should return RETRY."""
        tracker = DenialTracker(max_consecutive=3, max_total=20)
        action = tracker.record_denial("agent-1")
        assert action == DenialAction.RETRY

    def test_consecutive_limit_triggers_escalate(self) -> None:
        """Hitting max consecutive denials returns ESCALATE."""
        tracker = DenialTracker(max_consecutive=3, max_total=20)
        tracker.record_denial("agent-1")
        tracker.record_denial("agent-1")
        action = tracker.record_denial("agent-1")
        assert action == DenialAction.ESCALATE

    def test_total_limit_triggers_escalate(self) -> None:
        """Hitting max total denials returns ESCALATE."""
        tracker = DenialTracker(max_consecutive=10, max_total=3)
        tracker.record_denial("agent-1")
        tracker.reset_consecutive("agent-1")
        tracker.record_denial("agent-1")
        tracker.reset_consecutive("agent-1")
        action = tracker.record_denial("agent-1")
        assert action == DenialAction.ESCALATE

    def test_reset_consecutive_allows_retry(self) -> None:
        """Resetting consecutive count allows more retries."""
        tracker = DenialTracker(max_consecutive=2, max_total=20)
        tracker.record_denial("agent-1")
        tracker.reset_consecutive("agent-1")
        action = tracker.record_denial("agent-1")
        assert action == DenialAction.RETRY

    def test_reset_preserves_total(self) -> None:
        """Reset only clears consecutive, not total."""
        tracker = DenialTracker(max_consecutive=10, max_total=3)
        tracker.record_denial("agent-1")
        tracker.record_denial("agent-1")
        tracker.reset_consecutive("agent-1")

        consecutive, total = tracker.get_counts("agent-1")
        assert consecutive == 0
        assert total == 2

    def test_get_counts_unknown_agent(self) -> None:
        """Unknown agent returns (0, 0)."""
        tracker = DenialTracker(max_consecutive=3, max_total=20)
        assert tracker.get_counts("unknown") == (0, 0)

    def test_get_counts_tracks_correctly(self) -> None:
        """Counts are tracked correctly across operations."""
        tracker = DenialTracker(max_consecutive=5, max_total=20)
        tracker.record_denial("agent-1")
        tracker.record_denial("agent-1")
        consecutive, total = tracker.get_counts("agent-1")
        assert consecutive == 2
        assert total == 2

    def test_independent_agents(self) -> None:
        """Different agents have independent counts."""
        tracker = DenialTracker(max_consecutive=3, max_total=20)
        tracker.record_denial("agent-1")
        tracker.record_denial("agent-1")
        action = tracker.record_denial("agent-2")
        assert action == DenialAction.RETRY

        consecutive_1, total_1 = tracker.get_counts("agent-1")
        consecutive_2, total_2 = tracker.get_counts("agent-2")
        assert consecutive_1 == 2
        assert total_1 == 2
        assert consecutive_2 == 1
        assert total_2 == 1

    def test_reset_on_unknown_agent_is_noop(self) -> None:
        """Resetting an unknown agent does nothing."""
        tracker = DenialTracker(max_consecutive=3, max_total=20)
        tracker.reset_consecutive("unknown")
        assert tracker.get_counts("unknown") == (0, 0)

    def test_reset_on_zero_consecutive_is_noop(self) -> None:
        """Resetting when consecutive is already 0 does nothing."""
        tracker = DenialTracker(max_consecutive=3, max_total=20)
        tracker.record_denial("agent-1")
        tracker.reset_consecutive("agent-1")
        tracker.reset_consecutive("agent-1")
        consecutive, total = tracker.get_counts("agent-1")
        assert consecutive == 0
        assert total == 1

    def test_invalid_max_consecutive_raises(self) -> None:
        """max_consecutive < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_consecutive"):
            DenialTracker(max_consecutive=0, max_total=20)

    def test_invalid_max_total_raises(self) -> None:
        """max_total < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_total"):
            DenialTracker(max_consecutive=3, max_total=0)

    @pytest.mark.parametrize(
        ("max_consecutive", "max_total", "denial_count", "expected"),
        [
            (1, 20, 1, DenialAction.ESCALATE),
            (2, 20, 1, DenialAction.RETRY),
            (2, 20, 2, DenialAction.ESCALATE),
            (5, 3, 3, DenialAction.ESCALATE),
        ],
        ids=[
            "single-denial-at-limit",
            "single-denial-under-limit",
            "double-denial-at-limit",
            "total-limit-hit-first",
        ],
    )
    def test_parametrized_limits(
        self,
        max_consecutive: int,
        max_total: int,
        denial_count: int,
        expected: DenialAction,
    ) -> None:
        """Parametrized tests for various limit combinations."""
        tracker = DenialTracker(
            max_consecutive=max_consecutive,
            max_total=max_total,
        )
        action = DenialAction.RETRY
        for _ in range(denial_count):
            action = tracker.record_denial("agent-1")
        assert action == expected
