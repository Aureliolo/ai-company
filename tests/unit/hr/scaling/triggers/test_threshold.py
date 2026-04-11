"""Tests for signal threshold trigger."""

from datetime import UTC, datetime

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.models import ScalingSignal
from synthorg.hr.scaling.triggers.threshold import SignalThresholdTrigger

_NOW = datetime(2026, 4, 11, 12, 0, 0, tzinfo=UTC)


def _make_signal(name: str, value: float) -> ScalingSignal:
    return ScalingSignal(
        name=NotBlankStr(name),
        value=value,
        source=NotBlankStr("test"),
        timestamp=_NOW,
    )


@pytest.mark.unit
class TestSignalThresholdTrigger:
    """SignalThresholdTrigger crossing detection."""

    async def test_no_crossing_initially(self) -> None:
        trigger = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
            above=True,
        )
        assert await trigger.should_trigger() is False

    @pytest.mark.parametrize(
        ("signal_name", "threshold", "above", "values", "expect_trigger"),
        [
            ("utilization", 0.85, True, (0.80, 0.90), True),
            ("utilization", 0.85, True, (0.80, 0.80), False),
            ("utilization", 0.30, False, (0.40, 0.20), True),
        ],
        ids=[
            "fires-on-above-crossing",
            "does-not-fire-below-threshold",
            "fires-on-below-crossing",
        ],
    )
    async def test_threshold_crossing(
        self,
        signal_name: str,
        threshold: float,
        above: bool,
        values: tuple,
        expect_trigger: bool,
    ) -> None:
        initial_value, final_value = values
        trigger = SignalThresholdTrigger(
            signal_name=signal_name,
            threshold=threshold,
            above=above,
        )
        await trigger.update_signal(_make_signal(signal_name, initial_value))
        await trigger.update_signal(_make_signal(signal_name, final_value))
        assert (await trigger.should_trigger()) is expect_trigger

    async def test_ignores_wrong_signal_name(self) -> None:
        trigger = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
            above=True,
        )
        await trigger.update_signal(_make_signal("budget", 0.90))
        assert await trigger.should_trigger() is False

    async def test_resets_after_trigger(self) -> None:
        trigger = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
            above=True,
        )
        # Initialize below threshold
        await trigger.update_signal(_make_signal("utilization", 0.80))
        # Cross above threshold
        await trigger.update_signal(_make_signal("utilization", 0.90))
        assert await trigger.should_trigger() is True
        # Should not fire again without new crossing.
        assert await trigger.should_trigger() is False

    async def test_no_repeated_firing(self) -> None:
        trigger = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
            above=True,
        )
        # Initialize below threshold
        await trigger.update_signal(_make_signal("utilization", 0.80))
        # Multiple updates above threshold should only fire once.
        await trigger.update_signal(_make_signal("utilization", 0.90))
        await trigger.update_signal(_make_signal("utilization", 0.95))
        assert await trigger.should_trigger() is True
        assert await trigger.should_trigger() is False

    async def test_name_property(self) -> None:
        trigger = SignalThresholdTrigger(
            signal_name="utilization",
            threshold=0.85,
        )
        assert trigger.name == "signal_threshold"
