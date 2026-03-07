"""Tests for delegation deduplicator."""

import pytest

from ai_company.communication.loop_prevention.dedup import (
    DelegationDeduplicator,
)

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestDelegationDeduplicator:
    def test_first_check_passes(self) -> None:
        dedup = DelegationDeduplicator(window_seconds=60)
        result = dedup.check("a", "b", "task-1")
        assert result.passed is True
        assert result.mechanism == "dedup"

    def test_duplicate_within_window_fails(self) -> None:
        clock_time = 100.0

        def clock() -> float:
            return clock_time

        dedup = DelegationDeduplicator(window_seconds=60, clock=clock)
        dedup.record("a", "b", "task-1")
        clock_time = 130.0  # 30s later, within window
        result = dedup.check("a", "b", "task-1")
        assert result.passed is False
        assert result.mechanism == "dedup"

    def test_duplicate_after_window_passes(self) -> None:
        clock_time = 100.0

        def clock() -> float:
            return clock_time

        dedup = DelegationDeduplicator(window_seconds=60, clock=clock)
        dedup.record("a", "b", "task-1")
        clock_time = 161.0  # 61s later, outside window
        result = dedup.check("a", "b", "task-1")
        assert result.passed is True

    def test_different_task_title_passes(self) -> None:
        clock_time = 100.0

        def clock() -> float:
            return clock_time

        dedup = DelegationDeduplicator(window_seconds=60, clock=clock)
        dedup.record("a", "b", "task-1")
        result = dedup.check("a", "b", "task-2")
        assert result.passed is True

    def test_different_pair_passes(self) -> None:
        clock_time = 100.0

        def clock() -> float:
            return clock_time

        dedup = DelegationDeduplicator(window_seconds=60, clock=clock)
        dedup.record("a", "b", "task-1")
        result = dedup.check("a", "c", "task-1")
        assert result.passed is True

    def test_record_updates_timestamp(self) -> None:
        clock_time = 100.0

        def clock() -> float:
            return clock_time

        dedup = DelegationDeduplicator(window_seconds=60, clock=clock)
        dedup.record("a", "b", "task-1")
        clock_time = 150.0  # 50s later
        dedup.record("a", "b", "task-1")  # re-record
        clock_time = 200.0  # 100s after first, 50s after second
        result = dedup.check("a", "b", "task-1")
        assert result.passed is False  # still within window of 2nd
