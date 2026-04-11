"""Unit tests for webhook replay protection.

All tests use an injected clock so the nonce / timestamp checks
are fully deterministic -- no dependency on wall-clock time.
"""

import pytest

from synthorg.integrations.webhooks.replay_protection import ReplayProtector


class _FakeClock:
    """Injectable clock for deterministic replay tests."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.mark.unit
class TestReplayProtector:
    """Tests for nonce + timestamp replay protection."""

    def test_fresh_request_accepted(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=300, clock=clock)
        assert protector.check(nonce="abc", timestamp=clock.now) is True

    def test_duplicate_nonce_rejected(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=300, clock=clock)
        protector.check(nonce="abc", timestamp=clock.now)
        assert protector.check(nonce="abc", timestamp=clock.now) is False

    def test_different_nonces_accepted(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=300, clock=clock)
        assert protector.check(nonce="a", timestamp=clock.now) is True
        assert protector.check(nonce="b", timestamp=clock.now) is True

    def test_old_timestamp_rejected(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=60, clock=clock)
        old_time = clock.now - 120
        assert protector.check(nonce="x", timestamp=old_time) is False

    def test_future_timestamp_rejected(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=60, clock=clock)
        future_time = clock.now + 120
        assert protector.check(nonce="y", timestamp=future_time) is False

    def test_none_nonce_accepted(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=300, clock=clock)
        assert protector.check(nonce=None, timestamp=clock.now) is True

    def test_none_timestamp_skips_time_check(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=300, clock=clock)
        assert protector.check(nonce="z", timestamp=None) is True

    def test_eviction_removes_old_nonces(self) -> None:
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=1, clock=clock)
        protector.check(nonce="old", timestamp=clock.now)
        assert "old" in protector._seen
        clock.advance(10)
        # Trigger eviction via a fresh check.
        protector.check(nonce="new", timestamp=clock.now)
        assert "old" not in protector._seen

    def test_bounded_cache_evicts_oldest(self) -> None:
        """With max_entries reached, oldest nonces are dropped."""
        clock = _FakeClock()
        protector = ReplayProtector(
            window_seconds=3600,
            max_entries=3,
            clock=clock,
        )
        for i in range(5):
            assert protector.check(nonce=f"n{i}", timestamp=clock.now) is True
        # Only the 3 most recent nonces should remain.
        assert set(protector._seen) == {"n2", "n3", "n4"}

    def test_duplicate_detected_after_single_check(self) -> None:
        """A second call with the same nonce must be rejected."""
        clock = _FakeClock()
        protector = ReplayProtector(window_seconds=300, clock=clock)
        assert protector.check(nonce="once", timestamp=clock.now) is True
        # Advance a little but stay inside the window.
        clock.advance(30)
        assert protector.check(nonce="once", timestamp=clock.now) is False
