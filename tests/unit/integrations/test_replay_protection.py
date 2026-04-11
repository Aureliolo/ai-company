"""Unit tests for webhook replay protection."""

import time

import pytest

from synthorg.integrations.webhooks.replay_protection import ReplayProtector


@pytest.mark.unit
class TestReplayProtector:
    """Tests for nonce + timestamp replay protection."""

    def test_fresh_request_accepted(self) -> None:
        protector = ReplayProtector(window_seconds=300)
        assert protector.check(nonce="abc", timestamp=time.time()) is True

    def test_duplicate_nonce_rejected(self) -> None:
        protector = ReplayProtector(window_seconds=300)
        protector.check(nonce="abc", timestamp=time.time())
        assert protector.check(nonce="abc", timestamp=time.time()) is False

    def test_different_nonces_accepted(self) -> None:
        protector = ReplayProtector(window_seconds=300)
        assert protector.check(nonce="a", timestamp=time.time()) is True
        assert protector.check(nonce="b", timestamp=time.time()) is True

    def test_old_timestamp_rejected(self) -> None:
        protector = ReplayProtector(window_seconds=60)
        old_time = time.time() - 120
        assert protector.check(nonce="x", timestamp=old_time) is False

    def test_future_timestamp_rejected(self) -> None:
        protector = ReplayProtector(window_seconds=60)
        future_time = time.time() + 120
        assert protector.check(nonce="y", timestamp=future_time) is False

    def test_none_nonce_accepted(self) -> None:
        protector = ReplayProtector(window_seconds=300)
        assert protector.check(nonce=None, timestamp=time.time()) is True

    def test_none_timestamp_skips_time_check(self) -> None:
        protector = ReplayProtector(window_seconds=300)
        assert protector.check(nonce="z", timestamp=None) is True

    def test_eviction_removes_old_nonces(self) -> None:
        protector = ReplayProtector(window_seconds=1)
        protector.check(nonce="old", timestamp=time.time())
        protector._seen["old"] = time.time() - 10
        protector._evict(time.time())
        assert "old" not in protector._seen
