"""Tests for the CalendarStrategy implementation."""

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
from synthorg.engine.workflow.strategies.calendar import (
    CalendarStrategy,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType

from .conftest import SECONDS_PER_DAY, make_context, make_sprint

# -- Helpers -----------------------------------------------------------------


def _make_ceremony(
    name: str = "standup",
    frequency: MeetingFrequency | None = MeetingFrequency.DAILY,
    strategy_config: dict[str, object] | None = None,
) -> SprintCeremonyConfig:
    """Create a ceremony config for calendar strategy tests."""
    override: CeremonyPolicyConfig | None = None
    if strategy_config is not None:
        override = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.CALENDAR,
            strategy_config=strategy_config,
        )
    return SprintCeremonyConfig(
        name=name,
        protocol=MeetingProtocolType.ROUND_ROBIN,
        frequency=frequency,
        policy_override=override,
    )


# -- Protocol conformance ---------------------------------------------------


class TestCalendarStrategyProtocol:
    """Verify CalendarStrategy satisfies the protocol."""

    @pytest.mark.unit
    def test_is_protocol_instance(self) -> None:
        strategy = CalendarStrategy()
        assert isinstance(strategy, CeremonySchedulingStrategy)

    @pytest.mark.unit
    def test_strategy_type(self) -> None:
        assert CalendarStrategy().strategy_type is CeremonyStrategyType.CALENDAR

    @pytest.mark.unit
    def test_default_velocity_calculator(self) -> None:
        assert (
            CalendarStrategy().get_default_velocity_calculator()
            is VelocityCalcType.CALENDAR
        )


# -- should_fire_ceremony ---------------------------------------------------


class TestShouldFireCeremony:
    """should_fire_ceremony() tests."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("frequency", "interval_seconds"),
        [
            (MeetingFrequency.DAILY, SECONDS_PER_DAY),
            (MeetingFrequency.WEEKLY, 604_800.0),
            (MeetingFrequency.BI_WEEKLY, 1_209_600.0),
        ],
    )
    def test_fires_when_interval_elapsed(
        self,
        frequency: MeetingFrequency,
        interval_seconds: float,
    ) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=frequency)
        ctx = make_context(elapsed_seconds=interval_seconds)
        assert strategy.should_fire_ceremony(ceremony, make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_does_not_fire_before_interval(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        ctx = make_context(elapsed_seconds=SECONDS_PER_DAY - 1.0)
        assert strategy.should_fire_ceremony(ceremony, make_sprint(), ctx) is False

    @pytest.mark.unit
    def test_does_not_double_fire_within_interval(self) -> None:
        """Calling twice at the same elapsed time should fire only once."""
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = make_sprint()
        ctx = make_context(elapsed_seconds=SECONDS_PER_DAY)

        # First call fires.
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True
        # Second call at same elapsed does not fire again.
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    def test_fires_again_after_next_interval(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = make_sprint()

        # First fire at day 1.
        ctx1 = make_context(elapsed_seconds=SECONDS_PER_DAY)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx1) is True

        # Second fire at day 2.
        ctx2 = make_context(elapsed_seconds=2 * SECONDS_PER_DAY)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx2) is True

    @pytest.mark.unit
    def test_no_frequency_returns_false(self) -> None:
        """Ceremony with no frequency and no strategy_config frequency."""
        strategy = CalendarStrategy()
        ceremony = SprintCeremonyConfig(
            name="standup",
            protocol=MeetingProtocolType.ROUND_ROBIN,
            policy_override=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.CALENDAR,
                strategy_config={},
            ),
        )
        ctx = make_context(elapsed_seconds=SECONDS_PER_DAY * 100)
        assert strategy.should_fire_ceremony(ceremony, make_sprint(), ctx) is False

    @pytest.mark.unit
    def test_frequency_from_strategy_config_fallback(self) -> None:
        """When ceremony.frequency is None, fall back to strategy_config."""
        strategy = CalendarStrategy()
        ceremony = SprintCeremonyConfig(
            name="standup",
            protocol=MeetingProtocolType.ROUND_ROBIN,
            policy_override=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.CALENDAR,
                strategy_config={"frequency": "weekly"},
            ),
        )
        ctx = make_context(elapsed_seconds=604_800.0)
        assert strategy.should_fire_ceremony(ceremony, make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_independent_tracking_per_ceremony(self) -> None:
        """Different ceremonies track their fire times independently."""
        strategy = CalendarStrategy()
        daily = _make_ceremony(name="standup", frequency=MeetingFrequency.DAILY)
        weekly = _make_ceremony(name="review", frequency=MeetingFrequency.WEEKLY)
        sprint = make_sprint()

        ctx = make_context(elapsed_seconds=SECONDS_PER_DAY)
        # Daily fires, weekly does not.
        assert strategy.should_fire_ceremony(daily, sprint, ctx) is True
        assert strategy.should_fire_ceremony(weekly, sprint, ctx) is False


# -- should_transition_sprint ------------------------------------------------


class TestShouldTransitionSprint:
    """should_transition_sprint() tests."""

    @pytest.mark.unit
    def test_transitions_at_duration_days(self) -> None:
        strategy = CalendarStrategy()
        sprint = make_sprint(duration_days=14)
        config = SprintConfig(duration_days=14)
        ctx = make_context(elapsed_seconds=14.0 * SECONDS_PER_DAY)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_does_not_transition_before_duration(self) -> None:
        strategy = CalendarStrategy()
        sprint = make_sprint(duration_days=14)
        config = SprintConfig(duration_days=14)
        ctx = make_context(elapsed_seconds=13.9 * SECONDS_PER_DAY)
        assert strategy.should_transition_sprint(sprint, config, ctx) is None

    @pytest.mark.unit
    def test_duration_from_strategy_config(self) -> None:
        """strategy_config.duration_days overrides config.duration_days."""
        strategy = CalendarStrategy()
        sprint = make_sprint(duration_days=14)
        config = SprintConfig(
            duration_days=14,
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.CALENDAR,
                strategy_config={"duration_days": 7},
            ),
        )
        ctx = make_context(elapsed_seconds=7.0 * SECONDS_PER_DAY)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_defaults_to_config_duration_days(self) -> None:
        """Without strategy_config, uses SprintConfig.duration_days."""
        strategy = CalendarStrategy()
        sprint = make_sprint(duration_days=7)
        config = SprintConfig(duration_days=7)
        ctx = make_context(elapsed_seconds=7.0 * SECONDS_PER_DAY)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_does_not_transition_non_active(self) -> None:
        strategy = CalendarStrategy()
        sprint = make_sprint(status=SprintStatus.PLANNING, completed_count=0)
        config = SprintConfig()
        ctx = make_context(elapsed_seconds=100 * SECONDS_PER_DAY)
        assert strategy.should_transition_sprint(sprint, config, ctx) is None

    @pytest.mark.unit
    def test_task_completion_does_not_affect_transition(self) -> None:
        """Calendar transition is time-only; 100% tasks done doesn't trigger it."""
        strategy = CalendarStrategy()
        sprint = make_sprint(task_count=10, completed_count=10)
        config = SprintConfig(duration_days=14)
        # Only 1 day elapsed, but all tasks done.
        ctx = make_context(
            elapsed_seconds=SECONDS_PER_DAY,
            sprint_pct=1.0,
            total_tasks=10,
        )
        assert strategy.should_transition_sprint(sprint, config, ctx) is None


# -- validate_strategy_config ------------------------------------------------


class TestValidateStrategyConfig:
    """validate_strategy_config() tests."""

    @pytest.mark.unit
    def test_valid_config(self) -> None:
        strategy = CalendarStrategy()
        strategy.validate_strategy_config({"duration_days": 14})

    @pytest.mark.unit
    def test_empty_config_valid(self) -> None:
        strategy = CalendarStrategy()
        strategy.validate_strategy_config({})

    @pytest.mark.unit
    def test_valid_frequency_in_config(self) -> None:
        strategy = CalendarStrategy()
        strategy.validate_strategy_config({"frequency": "daily"})

    @pytest.mark.unit
    def test_invalid_duration_days_type(self) -> None:
        strategy = CalendarStrategy()
        with pytest.raises(ValueError, match="positive integer"):
            strategy.validate_strategy_config({"duration_days": "fourteen"})

    @pytest.mark.unit
    def test_invalid_duration_days_zero(self) -> None:
        strategy = CalendarStrategy()
        with pytest.raises(ValueError, match=r"1.*90"):
            strategy.validate_strategy_config({"duration_days": 0})

    @pytest.mark.unit
    def test_invalid_duration_days_too_large(self) -> None:
        strategy = CalendarStrategy()
        with pytest.raises(ValueError, match=r"1.*90"):
            strategy.validate_strategy_config({"duration_days": 91})

    @pytest.mark.unit
    def test_invalid_frequency_value(self) -> None:
        strategy = CalendarStrategy()
        with pytest.raises(ValueError, match="Invalid frequency"):
            strategy.validate_strategy_config({"frequency": "hourly"})

    @pytest.mark.unit
    def test_unknown_keys_rejected(self) -> None:
        strategy = CalendarStrategy()
        with pytest.raises(ValueError, match="Unknown config keys"):
            strategy.validate_strategy_config({"trigger": "sprint_end"})

    @pytest.mark.unit
    def test_bool_rejected_as_duration_days(self) -> None:
        """bool is not accepted as int for duration_days."""
        strategy = CalendarStrategy()
        with pytest.raises(ValueError, match="positive integer"):
            strategy.validate_strategy_config({"duration_days": True})


# -- Lifecycle hooks ---------------------------------------------------------


class TestLifecycleHooks:
    """Lifecycle hook tests for state management."""

    @pytest.mark.unit
    async def test_on_sprint_activated_clears_state(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = make_sprint()

        # Fire a ceremony to create tracked state.
        ctx = make_context(elapsed_seconds=SECONDS_PER_DAY)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        # Activate new sprint -- should clear fire tracking.
        await strategy.on_sprint_activated(sprint, SprintConfig())

        # Same elapsed should fire again (state was cleared).
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_on_sprint_deactivated_clears_state(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = make_sprint()

        # Fire a ceremony.
        ctx = make_context(elapsed_seconds=SECONDS_PER_DAY)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        # Deactivate -- should clear state.
        await strategy.on_sprint_deactivated()

        # Same elapsed fires again.
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True
