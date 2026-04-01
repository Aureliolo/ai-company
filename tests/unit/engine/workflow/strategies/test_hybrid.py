"""Tests for the HybridStrategy (first-wins) implementation."""

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
from synthorg.engine.workflow.strategies.hybrid import (
    HybridStrategy,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType

# -- Helpers -----------------------------------------------------------------

_SECONDS_PER_DAY: float = 86_400.0


def _make_ceremony(
    name: str = "standup",
    frequency: MeetingFrequency | None = MeetingFrequency.DAILY,
    trigger: str | None = None,
    every_n: int = 5,
    sprint_percentage: float | None = None,
) -> SprintCeremonyConfig:
    """Create a ceremony config for hybrid strategy tests.

    When *trigger* is None and *frequency* is set, the ceremony has
    only a calendar leg.  When *trigger* is set, the ceremony has a
    task-driven leg (via policy_override).
    """
    strategy_config: dict[str, object] | None = None
    if trigger is not None:
        strategy_config = {"trigger": trigger}
        if trigger == "every_n_completions":
            strategy_config["every_n_completions"] = every_n
        if sprint_percentage is not None:
            strategy_config["sprint_percentage"] = sprint_percentage
    override: CeremonyPolicyConfig | None = None
    if strategy_config is not None:
        override = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.HYBRID,
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
    completions_since_last: int = 0,
    total_completions: int = 0,
    total_tasks: int = 10,
    sprint_pct: float = 0.0,
) -> CeremonyEvalContext:
    """Create an evaluation context."""
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


class TestHybridStrategyProtocol:
    """Verify HybridStrategy satisfies the protocol."""

    @pytest.mark.unit
    def test_is_protocol_instance(self) -> None:
        strategy = HybridStrategy()
        assert isinstance(strategy, CeremonySchedulingStrategy)

    @pytest.mark.unit
    def test_strategy_type(self) -> None:
        assert HybridStrategy().strategy_type is CeremonyStrategyType.HYBRID

    @pytest.mark.unit
    def test_default_velocity_calculator(self) -> None:
        assert (
            HybridStrategy().get_default_velocity_calculator()
            is VelocityCalcType.MULTI_DIMENSIONAL
        )


# -- should_fire_ceremony ---------------------------------------------------


class TestShouldFireCeremony:
    """should_fire_ceremony() tests."""

    @pytest.mark.unit
    def test_calendar_leg_fires_when_interval_elapsed(self) -> None:
        """Frequency-only ceremony fires on time interval."""
        strategy = HybridStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY, trigger=None)
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_calendar_leg_does_not_fire_before_interval(self) -> None:
        strategy = HybridStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY, trigger=None)
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY - 1.0)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is False

    @pytest.mark.unit
    def test_task_leg_fires_when_every_n_reached(self) -> None:
        """Task-only ceremony (no frequency) fires on count threshold."""
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=None,
            trigger="every_n_completions",
            every_n=5,
        )
        # No frequency, so need policy_override for the ceremony to be valid.
        ctx = _make_context(completions_since_last=5, total_tasks=20)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_task_leg_does_not_fire_below_threshold(self) -> None:
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=None,
            trigger="every_n_completions",
            every_n=5,
        )
        ctx = _make_context(completions_since_last=4, total_tasks=20)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is False

    @pytest.mark.unit
    def test_task_leg_sprint_percentage(self) -> None:
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=None,
            trigger="sprint_percentage",
            sprint_percentage=75.0,
        )
        ctx = _make_context(sprint_pct=0.75, total_tasks=10)
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_calendar_fires_first(self) -> None:
        """Calendar interval met, task threshold not -- fires."""
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=MeetingFrequency.DAILY,
            trigger="every_n_completions",
            every_n=10,
        )
        # Time elapsed, but only 3 completions (below 10).
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
            completions_since_last=3,
        )
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_task_fires_first(self) -> None:
        """Task threshold met before calendar interval -- fires."""
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=MeetingFrequency.DAILY,
            trigger="every_n_completions",
            every_n=5,
        )
        # Only half a day elapsed, but 5 completions.
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY / 2,
            completions_since_last=5,
        )
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_task_fire_resets_calendar_timer(self) -> None:
        """When task-driven fires first, calendar timer resets."""
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=MeetingFrequency.DAILY,
            trigger="every_n_completions",
            every_n=5,
        )
        sprint = _make_sprint()

        # Task fires at T=50000 (before daily interval of 86400).
        ctx1 = _make_context(
            elapsed_seconds=50_000.0,
            completions_since_last=5,
        )
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx1) is True

        # Calendar would have fired at T=86400, but timer was reset to 50000.
        # Next calendar fire should be at 50000 + 86400 = 136400.
        ctx2 = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
            completions_since_last=2,
        )
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx2) is False

        # Fires at 136400.
        ctx3 = _make_context(
            elapsed_seconds=136_400.0,
            completions_since_last=2,
        )
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx3) is True

    @pytest.mark.unit
    def test_both_met_simultaneously_fires_once(self) -> None:
        """Both legs met at the same time -- fires once, returns True."""
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=MeetingFrequency.DAILY,
            trigger="every_n_completions",
            every_n=5,
        )
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
            completions_since_last=5,
        )
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is True

    @pytest.mark.unit
    def test_neither_fires(self) -> None:
        """Neither leg meets threshold."""
        strategy = HybridStrategy()
        ceremony = _make_ceremony(
            frequency=MeetingFrequency.DAILY,
            trigger="every_n_completions",
            every_n=10,
        )
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY / 2,
            completions_since_last=3,
        )
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is False

    @pytest.mark.unit
    def test_no_frequency_no_trigger_returns_false(self) -> None:
        """Ceremony with no frequency and no trigger."""
        strategy = HybridStrategy()
        ceremony = SprintCeremonyConfig(
            name="standup",
            protocol=MeetingProtocolType.ROUND_ROBIN,
            policy_override=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.HYBRID,
                strategy_config={},
            ),
        )
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY * 100,
            completions_since_last=100,
        )
        assert strategy.should_fire_ceremony(ceremony, _make_sprint(), ctx) is False


# -- should_transition_sprint ------------------------------------------------


class TestShouldTransitionSprint:
    """should_transition_sprint() tests."""

    @pytest.mark.unit
    def test_transitions_on_calendar_duration(self) -> None:
        """Calendar leg: elapsed >= duration_days * 86400."""
        strategy = HybridStrategy()
        sprint = _make_sprint(duration_days=14)
        config = SprintConfig(duration_days=14)
        ctx = _make_context(
            elapsed_seconds=14.0 * _SECONDS_PER_DAY,
            sprint_pct=0.5,
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_transitions_on_task_completion(self) -> None:
        """Task leg: sprint_percentage_complete >= threshold."""
        strategy = HybridStrategy()
        sprint = _make_sprint(task_count=10, completed_count=10)
        config = SprintConfig(duration_days=14)
        # Only 1 day elapsed, but all tasks done.
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
            sprint_pct=1.0,
            total_tasks=10,
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_calendar_met_task_not(self) -> None:
        """Calendar duration met, task completion below threshold -- transitions."""
        strategy = HybridStrategy()
        sprint = _make_sprint(task_count=10, completed_count=5)
        config = SprintConfig(duration_days=14)
        ctx = _make_context(
            elapsed_seconds=14.0 * _SECONDS_PER_DAY,
            sprint_pct=0.5,
            total_tasks=10,
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_task_met_calendar_not(self) -> None:
        """Task threshold met, calendar not -- transitions."""
        strategy = HybridStrategy()
        sprint = _make_sprint(task_count=10, completed_count=10)
        config = SprintConfig(duration_days=14)
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
            sprint_pct=1.0,
            total_tasks=10,
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_neither_transitions(self) -> None:
        strategy = HybridStrategy()
        sprint = _make_sprint(task_count=10, completed_count=5)
        config = SprintConfig(duration_days=14)
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
            sprint_pct=0.5,
            total_tasks=10,
        )
        assert strategy.should_transition_sprint(sprint, config, ctx) is None

    @pytest.mark.unit
    def test_does_not_transition_non_active(self) -> None:
        strategy = HybridStrategy()
        sprint = _make_sprint(status=SprintStatus.PLANNING, completed_count=0)
        config = SprintConfig()
        ctx = _make_context(elapsed_seconds=100 * _SECONDS_PER_DAY, sprint_pct=1.0)
        assert strategy.should_transition_sprint(sprint, config, ctx) is None

    @pytest.mark.unit
    def test_empty_sprint_calendar_only_transitions(self) -> None:
        """No tasks -- only calendar leg can transition."""
        strategy = HybridStrategy()
        sprint = _make_sprint(task_count=0, completed_count=0)
        config = SprintConfig(duration_days=7)
        ctx = _make_context(
            elapsed_seconds=7.0 * _SECONDS_PER_DAY,
            sprint_pct=0.0,
            total_tasks=0,
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_duration_from_strategy_config(self) -> None:
        """strategy_config.duration_days overrides config.duration_days."""
        strategy = HybridStrategy()
        sprint = _make_sprint(duration_days=14)
        config = SprintConfig(
            duration_days=14,
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.HYBRID,
                strategy_config={"duration_days": 7},
            ),
        )
        ctx = _make_context(elapsed_seconds=7.0 * _SECONDS_PER_DAY, sprint_pct=0.0)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_custom_task_threshold(self) -> None:
        """Custom transition_threshold for task leg."""
        strategy = HybridStrategy()
        sprint = _make_sprint(task_count=10, completed_count=8)
        config = SprintConfig(
            duration_days=14,
            ceremony_policy=CeremonyPolicyConfig(
                transition_threshold=0.8,
            ),
        )
        ctx = _make_context(
            elapsed_seconds=_SECONDS_PER_DAY,
            sprint_pct=0.8,
            total_tasks=10,
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW


# -- validate_strategy_config ------------------------------------------------


class TestValidateStrategyConfig:
    """validate_strategy_config() tests."""

    @pytest.mark.unit
    def test_valid_combined_config(self) -> None:
        strategy = HybridStrategy()
        strategy.validate_strategy_config(
            {
                "duration_days": 14,
                "every_n_completions": 10,
            }
        )

    @pytest.mark.unit
    def test_valid_task_only(self) -> None:
        strategy = HybridStrategy()
        strategy.validate_strategy_config({"every_n_completions": 5})

    @pytest.mark.unit
    def test_valid_calendar_only(self) -> None:
        strategy = HybridStrategy()
        strategy.validate_strategy_config({"duration_days": 14})

    @pytest.mark.unit
    def test_empty_config_valid(self) -> None:
        strategy = HybridStrategy()
        strategy.validate_strategy_config({})

    @pytest.mark.unit
    def test_unknown_keys_rejected(self) -> None:
        strategy = HybridStrategy()
        with pytest.raises(ValueError, match="Unknown config keys"):
            strategy.validate_strategy_config({"debounce": 5})

    @pytest.mark.unit
    def test_invalid_every_n_zero(self) -> None:
        strategy = HybridStrategy()
        with pytest.raises(ValueError, match="positive integer"):
            strategy.validate_strategy_config({"every_n_completions": 0})

    @pytest.mark.unit
    def test_invalid_sprint_percentage_over_100(self) -> None:
        strategy = HybridStrategy()
        with pytest.raises(ValueError, match="between"):
            strategy.validate_strategy_config({"sprint_percentage": 101})

    @pytest.mark.unit
    def test_invalid_duration_days_range(self) -> None:
        strategy = HybridStrategy()
        with pytest.raises(ValueError, match=r"1.*90"):
            strategy.validate_strategy_config({"duration_days": 0})

    @pytest.mark.unit
    def test_invalid_trigger_value(self) -> None:
        strategy = HybridStrategy()
        with pytest.raises(ValueError, match="Invalid trigger"):
            strategy.validate_strategy_config({"trigger": "unknown"})

    @pytest.mark.unit
    def test_valid_frequency_in_config(self) -> None:
        strategy = HybridStrategy()
        strategy.validate_strategy_config({"frequency": "daily"})


# -- Lifecycle hooks ---------------------------------------------------------


class TestLifecycleHooks:
    """Lifecycle hook tests for state management."""

    @pytest.mark.unit
    async def test_on_sprint_activated_clears_state(self) -> None:
        strategy = HybridStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY, trigger=None)
        sprint = _make_sprint()

        # Fire to create tracked state.
        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        # Activate new sprint.
        await strategy.on_sprint_activated(sprint, SprintConfig())

        # Same elapsed fires again (state cleared).
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_on_sprint_deactivated_clears_state(self) -> None:
        strategy = HybridStrategy()
        ceremony = _make_ceremony(frequency=MeetingFrequency.DAILY, trigger=None)
        sprint = _make_sprint()

        ctx = _make_context(elapsed_seconds=_SECONDS_PER_DAY)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        await strategy.on_sprint_deactivated()

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True
