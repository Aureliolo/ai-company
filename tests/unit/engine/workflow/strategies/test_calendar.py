"""Tests for the CalendarStrategy implementation."""

from typing import Any

import pytest

from synthorg.communication.meeting.enums import MeetingProtocolType
from synthorg.communication.meeting.frequency import MeetingFrequency
from synthorg.engine.workflow.ceremony_context import CeremonyEvalContext
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
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.engine.workflow.strategies.calendar import (
    CalendarStrategy,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType

# -- Helpers -----------------------------------------------------------------

_SECONDS_PER_DAY: float = 86_400.0


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


def _make_sprint(
    task_count: int = 10,
    completed_count: int = 0,
    status: SprintStatus = SprintStatus.ACTIVE,
    duration_days: int = 14,
) -> Sprint:
    """Create a sprint with the given task/completion counts."""
    task_ids = tuple(f"task-{i}" for i in range(task_count))
    completed_ids = tuple(f"task-{i}" for i in range(completed_count))
    kwargs: dict[str, Any] = {
        "id": "sprint-1",
        "name": "Sprint 1",
        "sprint_number": 1,
        "status": status,
        "duration_days": duration_days,
        "task_ids": task_ids,
        "completed_task_ids": completed_ids,
        "story_points_committed": float(task_count * 3),
        "story_points_completed": float(completed_count * 3),
    }
    if status is not SprintStatus.PLANNING:
        kwargs["start_date"] = "2026-04-01T00:00:00"
    if status is SprintStatus.COMPLETED:
        kwargs["end_date"] = "2026-04-14T00:00:00"
    return Sprint(**kwargs)


def _make_context(
    elapsed_seconds: float = 0.0,
    completions_since_last: int = 1,
    total_completions: int = 1,
    total_tasks: int = 10,
    sprint_pct: float = 0.0,
) -> CeremonyEvalContext:
    """Create an evaluation context with elapsed time."""
    return CeremonyEvalContext(
        completions_since_last_trigger=completions_since_last,
        total_completions_this_sprint=total_completions,
        total_tasks_in_sprint=total_tasks,
        elapsed_seconds=elapsed_seconds,
        budget_consumed_fraction=0.0,
        budget_remaining=0.0,
        velocity_history=(),
        external_events=(),
        sprint_percentage_complete=sprint_pct,
        story_points_completed=sprint_pct * total_tasks * 3,
        story_points_committed=float(total_tasks * 3),
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
    def test_fires_when_daily_interval_elapsed(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_does_not_fire_before_interval(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY - 1.0)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is False

    @pytest.mark.unit
    def test_does_not_double_fire_within_interval(self) -> None:
        """Calling twice at the same elapsed time should fire only once."""
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = _make_sprint()
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)

        # First call fires.
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True
        # Second call at same elapsed does not fire again.
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    def test_fires_again_after_next_interval(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = _make_sprint()

        # First fire at day 1.
        ctx1 = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx1) is True

        # Second fire at day 2.
        ctx2 = _make_context(elapsed_seconds=2 * _SECONDS_PER_DAY)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx2) is True

    @pytest.mark.unit
    def test_weekly_interval(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.WEEKLY)
        ctx = _make_context(elapsed_seconds=604_800.0)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_bi_weekly_interval(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.BI_WEEKLY)
        ctx = _make_context(elapsed_seconds=1_209_600.0)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

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
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY * 100)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is False

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
        ctx = _make_context(elapsed_seconds=604_800.0)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_independent_tracking_per_ceremony(self) -> None:
        """Different ceremonies track their fire times independently."""
        strategy = CalendarStrategy()
        daily = _make_ceremony(name="standup", frequency=MeetingFrequency.DAILY)
        weekly = _make_ceremony(name="review", frequency=MeetingFrequency.WEEKLY)
        sprint = _make_sprint()

        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        # Daily fires, weekly does not.
        assert strategy.should_fire_ceremony(daily, sprint, ctx) is True
        assert strategy.should_fire_ceremony(weekly, sprint, ctx) is False


# -- should_transition_sprint ------------------------------------------------


class TestShouldTransitionSprint:
    """should_transition_sprint() tests."""

    @pytest.mark.unit
    def test_transitions_at_duration_days(self) -> None:
        strategy = CalendarStrategy()
        sprint = _make_sprint(duration_days=14)
        config = SprintConfig(duration_days=14)
        ctx = _make_context(elapsed_seconds=14.0 * _SECONDS_PER_DAY)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_does_not_transition_before_duration(self) -> None:
        strategy = CalendarStrategy()
        sprint = _make_sprint(duration_days=14)
        config = SprintConfig(duration_days=14)
        ctx = _make_context(elapsed_seconds=13.9 * _SECONDS_PER_DAY)
        assert strategy.should_transition_sprint(sprint, config, ctx) is None

    @pytest.mark.unit
    def test_duration_from_strategy_config(self) -> None:
        """strategy_config.duration_days overrides config.duration_days."""
        strategy = CalendarStrategy()
        sprint = _make_sprint(duration_days=14)
        config = SprintConfig(
            duration_days=14,
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.CALENDAR,
                strategy_config={"duration_days": 7},
            ),
        )
        ctx = _make_context(elapsed_seconds=7.0 * _SECONDS_PER_DAY)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_defaults_to_config_duration_days(self) -> None:
        """Without strategy_config, uses SprintConfig.duration_days."""
        strategy = CalendarStrategy()
        sprint = _make_sprint(duration_days=7)
        config = SprintConfig(duration_days=7)
        ctx = _make_context(elapsed_seconds=7.0 * _SECONDS_PER_DAY)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_does_not_transition_non_active(self) -> None:
        strategy = CalendarStrategy()
        sprint = _make_sprint(status=SprintStatus.PLANNING, completed_count=0)
        config = SprintConfig()
        ctx = _make_context(elapsed_seconds=100 * _SECONDS_PER_DAY)
        assert strategy.should_transition_sprint(sprint, config, ctx) is None

    @pytest.mark.unit
    def test_task_completion_does_not_affect_transition(self) -> None:
        """Calendar transition is time-only; 100% tasks done doesn't trigger it."""
        strategy = CalendarStrategy()
        sprint = _make_sprint(task_count=10, completed_count=10)
        config = SprintConfig(duration_days=14)
        # Only 1 day elapsed, but all tasks done.
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
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


# -- Lifecycle hooks ---------------------------------------------------------


class TestLifecycleHooks:
    """Lifecycle hook tests for state management."""

    @pytest.mark.unit
    async def test_on_sprint_activated_clears_state(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = _make_sprint()

        # Fire a ceremony to create tracked state.
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        # Activate new sprint -- should clear fire tracking.
        await strategy.on_sprint_activated(sprint, SprintConfig())

        # Same elapsed should fire again (state was cleared).
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_on_sprint_deactivated_clears_state(self) -> None:
        strategy = CalendarStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY)
        sprint = _make_sprint()

        # Fire a ceremony.
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        # Deactivate -- should clear state.
        await strategy.on_sprint_deactivated()

        # Same elapsed fires again.
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True
