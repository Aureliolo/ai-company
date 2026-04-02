"""Tests for the ThroughputAdaptiveStrategy implementation."""

from unittest.mock import patch

import pytest

from synthorg.communication.meeting.enums import MeetingProtocolType
from synthorg.communication.meeting.frequency import MeetingFrequency
from synthorg.engine.workflow.ceremony_policy import (
    CeremonyPolicyConfig,
    CeremonyStrategyType,
)
from synthorg.engine.workflow.ceremony_strategy import (
    CeremonySchedulingStrategy,
)
from synthorg.engine.workflow.sprint_config import (
    SprintCeremonyConfig,
    SprintConfig,
)
from synthorg.engine.workflow.sprint_lifecycle import SprintStatus
from synthorg.engine.workflow.strategies.throughput_adaptive import (
    ThroughputAdaptiveStrategy,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType

from .conftest import make_context, make_sprint


def _make_ceremony(
    name: str = "standup",
    on_drop: bool | None = None,
    on_spike: bool | None = None,
) -> SprintCeremonyConfig:
    """Create a ceremony config with throughput-adaptive policy override."""
    config: dict[str, object] = {}
    if on_drop is not None:
        config["on_drop"] = on_drop
    if on_spike is not None:
        config["on_spike"] = on_spike
    return SprintCeremonyConfig(
        name=name,
        protocol=MeetingProtocolType.ROUND_ROBIN,
        policy_override=CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.THROUGHPUT_ADAPTIVE,
            strategy_config=config,
        ),
    )


def _make_sprint_config(
    drop_pct: int | float | None = None,
    spike_pct: int | float | None = None,
    window_size: int | None = None,
    transition_threshold: float | None = None,
) -> SprintConfig:
    """Create a SprintConfig with throughput-adaptive policy."""
    config: dict[str, object] = {}
    if drop_pct is not None:
        config["velocity_drop_threshold_pct"] = drop_pct
    if spike_pct is not None:
        config["velocity_spike_threshold_pct"] = spike_pct
    if window_size is not None:
        config["measurement_window_tasks"] = window_size
    policy = CeremonyPolicyConfig(
        strategy=CeremonyStrategyType.THROUGHPUT_ADAPTIVE,
        strategy_config=config,
        transition_threshold=transition_threshold,
    )
    return SprintConfig(ceremony_policy=policy)


class TestThroughputAdaptiveProtocol:
    """Verify ThroughputAdaptiveStrategy satisfies the protocol."""

    @pytest.mark.unit
    def test_is_protocol_instance(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        assert isinstance(strategy, CeremonySchedulingStrategy)

    @pytest.mark.unit
    def test_strategy_type(self) -> None:
        assert (
            ThroughputAdaptiveStrategy().strategy_type
            is CeremonyStrategyType.THROUGHPUT_ADAPTIVE
        )

    @pytest.mark.unit
    def test_default_velocity_calculator(self) -> None:
        assert (
            ThroughputAdaptiveStrategy().get_default_velocity_calculator()
            is VelocityCalcType.TASK_DRIVEN
        )


class TestShouldFireCeremony:
    """should_fire_ceremony() tests."""

    @pytest.mark.unit
    async def test_returns_false_during_cold_start(self) -> None:
        """Before baseline is established, no ceremonies fire."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(window_size=5)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony()
        ctx = make_context()

        # Only 3 completions -- window size is 5, baseline not yet set
        t = 100.0
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = t + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_fires_on_velocity_drop(self) -> None:
        """Ceremony fires when current rate drops below baseline by threshold."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        # 30% drop threshold, window of 3
        config = _make_sprint_config(drop_pct=30, window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony()  # on_drop=True by default
        ctx = make_context()

        # Establish baseline: 3 tasks in 30 seconds = 0.1 tasks/sec
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

            # Now slow down: 3 tasks in 150 seconds = 0.02 tasks/sec (80% drop)
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 50.0
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_does_not_fire_when_drop_below_threshold(self) -> None:
        """No ceremony when drop is less than threshold."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        # 50% drop threshold, window of 3
        config = _make_sprint_config(drop_pct=50, window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony()
        ctx = make_context()

        # Baseline: 3 tasks in 30 seconds = 0.1 tasks/sec
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

            # Slow down to 3 tasks in 45 seconds = 0.067 tasks/sec (33% drop)
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 15.0
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_fires_on_velocity_spike(self) -> None:
        """Ceremony with on_spike=True fires on velocity spike."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        # 50% spike threshold, window of 3
        config = _make_sprint_config(spike_pct=50, window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_spike=True, on_drop=False)
        ctx = make_context()

        # Baseline: 3 tasks in 30 seconds = 0.1 tasks/sec
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

            # Speed up: 3 tasks in 10 seconds = 0.3 tasks/sec (200% spike)
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 3.33
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_does_not_fire_spike_when_on_spike_false(self) -> None:
        """on_spike defaults to False -- spike alone does not fire."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(spike_pct=50, window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony()  # on_spike defaults to False
        ctx = make_context()

        # Baseline: 3 tasks in 30 seconds
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

            # Speed up: 3 tasks in 10 seconds (200% spike)
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 3.33
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_does_not_fire_drop_when_on_drop_false(self) -> None:
        """Explicit on_drop=False suppresses drop detection."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(drop_pct=30, window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_drop=False)
        ctx = make_context()

        # Baseline + big drop
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 50.0
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_no_policy_override_uses_defaults(self) -> None:
        """Ceremony without policy_override uses on_drop=True default."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        # Ceremony with no policy override -- on_drop defaults True
        ceremony = SprintCeremonyConfig(
            name="standup",
            protocol=MeetingProtocolType.ROUND_ROBIN,
            frequency=MeetingFrequency.DAILY,
        )
        ctx = make_context()

        # Establish baseline + drop
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 50.0
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_zero_time_span_returns_false(self) -> None:
        """All completions at the same instant cannot compute rate."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony()
        ctx = make_context()

        with patch("time.monotonic", return_value=100.0):
            for i in range(3):
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

        # Baseline not established (zero time span)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_on_drop_true_by_default(self) -> None:
        """on_drop defaults to True when not specified."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(drop_pct=30, window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        # No explicit on_drop/on_spike -- on_drop should default True
        ceremony = _make_ceremony()
        ctx = make_context()

        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 50.0
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True


class TestShouldTransitionSprint:
    """should_transition_sprint() tests."""

    @pytest.mark.unit
    def test_transitions_when_completion_threshold_met(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(transition_threshold=0.8)
        ctx = make_context(sprint_pct=0.85, total_tasks=10)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_does_not_transition_below_threshold(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(transition_threshold=0.8)
        ctx = make_context(sprint_pct=0.5, total_tasks=10)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None

    @pytest.mark.unit
    def test_does_not_transition_non_active(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint(status=SprintStatus.PLANNING)
        config = _make_sprint_config()
        ctx = make_context(sprint_pct=1.0)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None

    @pytest.mark.unit
    def test_does_not_transition_with_no_tasks(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint(task_count=0)
        config = _make_sprint_config()
        ctx = make_context(total_tasks=0, sprint_pct=0.0)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None

    @pytest.mark.unit
    def test_transition_with_strategy_config_none(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = SprintConfig(
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.THROUGHPUT_ADAPTIVE,
                strategy_config=None,
            ),
        )
        ctx = make_context()
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None


class TestLifecycleHooks:
    """Lifecycle hook tests."""

    @pytest.mark.unit
    async def test_on_sprint_activated_clears_state(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(window_size=3)
        ctx = make_context()

        # Accumulate completions
        await strategy.on_sprint_activated(sprint, config)
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

        # Re-activate -- state should reset
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony()
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_on_sprint_activated_reads_config_values(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(drop_pct=40, spike_pct=60, window_size=5)
        await strategy.on_sprint_activated(sprint, config)

        assert strategy._drop_threshold_pct == 40.0
        assert strategy._spike_threshold_pct == 60.0
        assert strategy._window_size == 5

    @pytest.mark.unit
    async def test_on_sprint_deactivated_clears_state(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(window_size=3)
        ctx = make_context()

        await strategy.on_sprint_activated(sprint, config)
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

        await strategy.on_sprint_deactivated()

        ceremony = _make_ceremony()
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_on_task_completed_establishes_baseline(self) -> None:
        """Baseline is established when deque fills for the first time."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ctx = make_context()
        assert strategy._baseline_rate is None

        with patch("time.monotonic") as mock_mono:
            mock_mono.return_value = 100.0
            await strategy.on_task_completed(sprint, "t-0", 3.0, ctx)
            assert strategy._baseline_rate is None

            mock_mono.return_value = 110.0
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
            assert strategy._baseline_rate is None

            mock_mono.return_value = 120.0
            await strategy.on_task_completed(sprint, "t-2", 3.0, ctx)

        # Baseline now set: 3 tasks / 20 seconds = 0.15 tasks/sec
        assert strategy._baseline_rate is not None
        assert strategy._baseline_rate == pytest.approx(3.0 / 20.0)

    @pytest.mark.unit
    async def test_baseline_frozen_after_establishment(self) -> None:
        """Baseline rate does not change after first establishment."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(window_size=3)
        await strategy.on_sprint_activated(sprint, config)

        ctx = make_context()

        with patch("time.monotonic") as mock_mono:
            # Establish baseline: 3 tasks in 20 seconds
            for i in range(3):
                mock_mono.return_value = 100.0 + i * 10.0
                await strategy.on_task_completed(sprint, f"t-{i}", 3.0, ctx)

        original_baseline = strategy._baseline_rate

        # Add more completions at different rate
        with patch("time.monotonic") as mock_mono:
            for i in range(3):
                mock_mono.return_value = 200.0 + i * 1.0
                await strategy.on_task_completed(sprint, f"t-{i + 3}", 3.0, ctx)

        assert strategy._baseline_rate == original_baseline

    @pytest.mark.unit
    async def test_on_task_blocked_increments_counter(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        assert strategy._blocked_count == 0
        await strategy.on_task_blocked(sprint, "t-1")
        assert strategy._blocked_count == 1
        await strategy.on_task_blocked(sprint, "t-2")
        assert strategy._blocked_count == 2

    @pytest.mark.unit
    async def test_on_sprint_activated_defaults_on_bad_config(self) -> None:
        """Invalid config values fall back to defaults."""
        strategy = ThroughputAdaptiveStrategy()
        sprint = make_sprint()
        bad_config = SprintConfig(
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.THROUGHPUT_ADAPTIVE,
                strategy_config={
                    "velocity_drop_threshold_pct": "not_a_number",
                    "velocity_spike_threshold_pct": True,
                    "measurement_window_tasks": 0,
                },
            ),
        )
        await strategy.on_sprint_activated(sprint, bad_config)

        # Should fall back to defaults
        assert strategy._drop_threshold_pct == 30.0
        assert strategy._spike_threshold_pct == 50.0
        assert strategy._window_size == 10


class TestValidateStrategyConfig:
    """validate_strategy_config() tests."""

    @pytest.mark.unit
    def test_valid_config(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        strategy.validate_strategy_config(
            {
                "velocity_drop_threshold_pct": 30,
                "measurement_window_tasks": 10,
            }
        )

    @pytest.mark.unit
    def test_valid_config_with_all_keys(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        strategy.validate_strategy_config(
            {
                "velocity_drop_threshold_pct": 30,
                "velocity_spike_threshold_pct": 50,
                "measurement_window_tasks": 10,
                "on_drop": True,
                "on_spike": False,
            }
        )

    @pytest.mark.unit
    def test_empty_config_valid(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        strategy.validate_strategy_config({})

    @pytest.mark.unit
    def test_unknown_keys_rejected(self) -> None:
        strategy = ThroughputAdaptiveStrategy()
        with pytest.raises(ValueError, match="Unknown config keys"):
            strategy.validate_strategy_config({"unknown_key": 42})

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("config", "exc_type", "match"),
        [
            ({"velocity_drop_threshold_pct": "abc"}, TypeError, "numeric"),
            ({"velocity_drop_threshold_pct": True}, TypeError, "numeric"),
            ({"velocity_drop_threshold_pct": 0}, ValueError, "between 1.0 and 100.0"),
            ({"velocity_drop_threshold_pct": 101}, ValueError, "between 1.0 and 100.0"),
            ({"velocity_drop_threshold_pct": -5}, ValueError, "between 1.0 and 100.0"),
            ({"velocity_spike_threshold_pct": "abc"}, TypeError, "numeric"),
            ({"velocity_spike_threshold_pct": True}, TypeError, "numeric"),
            ({"velocity_spike_threshold_pct": 0}, ValueError, "between 1.0 and 100.0"),
            ({"velocity_spike_threshold_pct": 101}, ValueError, "between 1.0 and 100"),
            ({"measurement_window_tasks": 1}, ValueError, "between 2 and 100,"),
            ({"measurement_window_tasks": 101}, ValueError, "between 2 and 100,"),
            ({"measurement_window_tasks": 3.5}, TypeError, "integer"),
            ({"measurement_window_tasks": True}, TypeError, "integer"),
            ({"on_drop": 1}, TypeError, "boolean"),
            ({"on_drop": "true"}, TypeError, "boolean"),
            ({"on_spike": 0}, TypeError, "boolean"),
            ({"on_spike": "false"}, TypeError, "boolean"),
        ],
        ids=[
            "drop_string",
            "drop_bool",
            "drop_zero",
            "drop_over_100",
            "drop_negative",
            "spike_string",
            "spike_bool",
            "spike_zero",
            "spike_over_100",
            "window_too_small",
            "window_too_large",
            "window_float",
            "window_bool",
            "on_drop_int",
            "on_drop_string",
            "on_spike_int",
            "on_spike_string",
        ],
    )
    def test_invalid_config_rejected(
        self,
        config: dict[str, object],
        exc_type: type[Exception],
        match: str,
    ) -> None:
        strategy = ThroughputAdaptiveStrategy()
        with pytest.raises(exc_type, match=match):
            strategy.validate_strategy_config(config)

    @pytest.mark.unit
    def test_float_thresholds_accepted(self) -> None:
        """Float values for thresholds should be valid."""
        strategy = ThroughputAdaptiveStrategy()
        strategy.validate_strategy_config(
            {
                "velocity_drop_threshold_pct": 25.5,
                "velocity_spike_threshold_pct": 75.3,
            }
        )
