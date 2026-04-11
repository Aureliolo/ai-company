"""Tests for batched scaling trigger."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.hr.scaling.triggers.batched import BatchedScalingTrigger


@pytest.mark.unit
class TestBatchedScalingTrigger:
    """BatchedScalingTrigger interval logic."""

    async def test_first_trigger_fires(self) -> None:
        trigger = BatchedScalingTrigger(interval_seconds=900)
        assert await trigger.should_trigger() is True

    async def test_second_trigger_within_interval_skips(self) -> None:
        trigger = BatchedScalingTrigger(interval_seconds=900)
        assert await trigger.should_trigger() is True
        assert await trigger.should_trigger() is False

    async def test_trigger_after_interval_fires(self) -> None:
        trigger = BatchedScalingTrigger(interval_seconds=10)
        assert await trigger.should_trigger() is True

        # Simulate time passing.
        past = datetime.now(UTC) - timedelta(seconds=15)
        trigger._last_run = past
        assert await trigger.should_trigger() is True

    async def test_record_run_updates_last_run(self) -> None:
        trigger = BatchedScalingTrigger(interval_seconds=900)
        assert trigger._last_run is None
        await trigger.record_run()
        assert trigger._last_run is not None

    async def test_minimum_interval_clamped_to_one(self) -> None:
        trigger = BatchedScalingTrigger(interval_seconds=0)
        assert trigger._interval == 1

    async def test_name_property(self) -> None:
        trigger = BatchedScalingTrigger()
        assert trigger.name == "batched"

    async def test_default_interval(self) -> None:
        trigger = BatchedScalingTrigger()
        assert trigger._interval == 900
