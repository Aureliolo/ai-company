"""Tests for composite scaling trigger."""

from datetime import UTC, datetime

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.models import ScalingSignal
from synthorg.hr.scaling.triggers.batched import BatchedScalingTrigger
from synthorg.hr.scaling.triggers.composite import CompositeScalingTrigger
from synthorg.hr.scaling.triggers.threshold import SignalThresholdTrigger

_NOW = datetime(2026, 4, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
class TestCompositeScalingTrigger:
    """CompositeScalingTrigger OR combination."""

    async def test_fires_when_first_child_fires(self) -> None:
        # Batched trigger fires on first call.
        batched = BatchedScalingTrigger(interval_seconds=900)
        threshold = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
        )
        composite = CompositeScalingTrigger(triggers=(batched, threshold))
        assert await composite.should_trigger() is True

    async def test_fires_when_second_child_fires(self) -> None:
        # Batched has already fired, threshold crosses.
        batched = BatchedScalingTrigger(interval_seconds=900)
        await batched.should_trigger()  # consume the first fire

        threshold = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
        )
        await threshold.update_signal(
            ScalingSignal(
                name=NotBlankStr("utilization"),
                value=0.90,
                source=NotBlankStr("test"),
                timestamp=_NOW,
            ),
        )

        composite = CompositeScalingTrigger(triggers=(batched, threshold))
        assert await composite.should_trigger() is True

    async def test_does_not_fire_when_no_child_fires(self) -> None:
        # Batched has already fired, threshold has no crossing.
        batched = BatchedScalingTrigger(interval_seconds=900)
        await batched.should_trigger()  # consume

        threshold = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
        )
        composite = CompositeScalingTrigger(triggers=(batched, threshold))
        assert await composite.should_trigger() is False

    async def test_empty_triggers_returns_false(self) -> None:
        composite = CompositeScalingTrigger(triggers=())
        assert await composite.should_trigger() is False

    async def test_name_property(self) -> None:
        composite = CompositeScalingTrigger(triggers=())
        assert composite.name == "composite"
