"""Tests for the EventDrivenStrategy implementation."""

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
from synthorg.engine.workflow.strategies.event_driven import (
    EventDrivenStrategy,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType

from .conftest import make_context, make_sprint


def _make_ceremony(
    name: str = "standup",
    on_event: str = "task_completed",
    debounce: int | None = None,
) -> SprintCeremonyConfig:
    """Create a ceremony config with event-driven policy override."""
    config: dict[str, object] = {"on_event": on_event}
    if debounce is not None:
        config["debounce"] = debounce
    return SprintCeremonyConfig(
        name=name,
        protocol=MeetingProtocolType.ROUND_ROBIN,
        policy_override=CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.EVENT_DRIVEN,
            strategy_config=config,
        ),
    )


def _make_sprint_config(
    transition_event: str | None = None,
    debounce_default: int | None = None,
) -> SprintConfig:
    """Create a SprintConfig with event-driven policy."""
    config: dict[str, object] = {}
    if transition_event is not None:
        config["transition_event"] = transition_event
    if debounce_default is not None:
        config["debounce_default"] = debounce_default
    return SprintConfig(
        ceremony_policy=CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.EVENT_DRIVEN,
            strategy_config=config,
        ),
    )


class TestEventDrivenStrategyProtocol:
    """Verify EventDrivenStrategy satisfies the protocol."""

    @pytest.mark.unit
    def test_is_protocol_instance(self) -> None:
        strategy = EventDrivenStrategy()
        assert isinstance(strategy, CeremonySchedulingStrategy)

    @pytest.mark.unit
    def test_strategy_type(self) -> None:
        assert EventDrivenStrategy().strategy_type is CeremonyStrategyType.EVENT_DRIVEN

    @pytest.mark.unit
    def test_default_velocity_calculator(self) -> None:
        assert (
            EventDrivenStrategy().get_default_velocity_calculator()
            is VelocityCalcType.POINTS_PER_SPRINT
        )


class TestShouldFireCeremony:
    """should_fire_ceremony() tests."""

    @pytest.mark.unit
    async def test_fires_when_debounce_reached(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="task_completed", debounce=3)
        ctx = make_context()

        # Simulate 3 task completions
        for _ in range(3):
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_does_not_fire_below_debounce(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="task_completed", debounce=5)
        ctx = make_context()

        for _ in range(4):
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_fires_with_custom_debounce(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(debounce_default=10)
        await strategy.on_sprint_activated(sprint, config)

        # Ceremony overrides debounce to 2
        ceremony = _make_ceremony(on_event="task_completed", debounce=2)
        ctx = make_context()

        for _ in range(2):
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_uses_debounce_default(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(debounce_default=3)
        await strategy.on_sprint_activated(sprint, config)

        # No per-ceremony debounce override
        ceremony = _make_ceremony(on_event="task_completed")
        ctx = make_context()

        for _ in range(3):
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_resets_counter_after_fire(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="task_completed", debounce=3)
        ctx = make_context()

        # First batch: fire at 3
        for _ in range(3):
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

        # Only 2 more -- should not fire again
        for _ in range(2):
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

        # One more to reach 3 since last fire
        await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_no_on_event_returns_false(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        # Ceremony with no on_event
        ceremony = SprintCeremonyConfig(
            name="standup",
            protocol=MeetingProtocolType.ROUND_ROBIN,
            policy_override=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.EVENT_DRIVEN,
                strategy_config={},
            ),
        )
        ctx = make_context()
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_no_policy_override_returns_false(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = SprintCeremonyConfig(
            name="standup",
            protocol=MeetingProtocolType.ROUND_ROBIN,
            frequency=MeetingFrequency.DAILY,
        )
        ctx = make_context()
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_external_event_increments_counter(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="deploy_completed", debounce=2)
        ctx = make_context()

        await strategy.on_external_event(sprint, "deploy_completed", {})
        await strategy.on_external_event(sprint, "deploy_completed", {})

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_task_blocked_increments_counter(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="task_blocked", debounce=1)
        ctx = make_context()

        await strategy.on_task_blocked(sprint, "t-1")

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_task_added_increments_counter(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="task_added", debounce=1)
        ctx = make_context()

        await strategy.on_task_added(sprint, "t-1")

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_budget_updated_increments_counter(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="budget_updated", debounce=1)
        ctx = make_context()

        await strategy.on_budget_updated(sprint, 0.5)

        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_independent_tracking_per_ceremony(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        await strategy.on_sprint_activated(sprint, config)

        standup = _make_ceremony(
            name="standup",
            on_event="task_completed",
            debounce=2,
        )
        retro = _make_ceremony(
            name="retro",
            on_event="task_completed",
            debounce=5,
        )
        ctx = make_context()

        for _ in range(3):
            await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)

        # Standup fires at 2, retro needs 5
        assert strategy.should_fire_ceremony(standup, sprint, ctx) is True
        assert strategy.should_fire_ceremony(retro, sprint, ctx) is False


class TestShouldTransitionSprint:
    """should_transition_sprint() tests."""

    @pytest.mark.unit
    async def test_transitions_on_configured_event(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(transition_event="sprint_backlog_empty")
        await strategy.on_sprint_activated(sprint, config)

        # Simulate the event via external_events in context
        ctx = make_context(
            external_events=("sprint_backlog_empty",),
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    async def test_transitions_on_internal_event(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(transition_event="task_completed")
        await strategy.on_sprint_activated(sprint, config)

        ctx = make_context()
        await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)

        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    async def test_does_not_transition_without_event(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(transition_event="sprint_backlog_empty")
        await strategy.on_sprint_activated(sprint, config)

        ctx = make_context()
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None

    @pytest.mark.unit
    def test_does_not_transition_non_active(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint(status=SprintStatus.PLANNING)
        config = _make_sprint_config(transition_event="sprint_backlog_empty")
        ctx = make_context(
            external_events=("sprint_backlog_empty",),
        )
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None

    @pytest.mark.unit
    def test_no_transition_event_returns_none(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        ctx = make_context()
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None


class TestLifecycleHooks:
    """Lifecycle hook tests."""

    @pytest.mark.unit
    async def test_on_sprint_activated_clears_state(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        ctx = make_context()

        # Accumulate some events
        await strategy.on_sprint_activated(sprint, config)
        await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)

        # Activate a new sprint -- state should reset
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="task_completed", debounce=1)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_on_sprint_deactivated_clears_state(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        ctx = make_context()

        await strategy.on_sprint_activated(sprint, config)
        await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
        await strategy.on_sprint_deactivated()

        ceremony = _make_ceremony(on_event="task_completed", debounce=1)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    async def test_on_sprint_activated_reads_debounce_default(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(debounce_default=3)
        await strategy.on_sprint_activated(sprint, config)

        ceremony = _make_ceremony(on_event="task_completed")
        ctx = make_context()

        # 2 events -- below debounce_default of 3
        await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
        await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

        # 3rd event -- meets debounce_default
        await strategy.on_task_completed(sprint, "t-1", 3.0, ctx)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True


class TestValidateStrategyConfig:
    """validate_strategy_config() tests."""

    @pytest.mark.unit
    def test_valid_config(self) -> None:
        strategy = EventDrivenStrategy()
        strategy.validate_strategy_config(
            {
                "on_event": "task_completed",
                "debounce": 5,
            }
        )

    @pytest.mark.unit
    def test_valid_config_with_all_keys(self) -> None:
        strategy = EventDrivenStrategy()
        strategy.validate_strategy_config(
            {
                "on_event": "task_completed",
                "debounce": 5,
                "debounce_default": 10,
                "transition_event": "sprint_backlog_empty",
            }
        )

    @pytest.mark.unit
    def test_empty_config_valid(self) -> None:
        strategy = EventDrivenStrategy()
        strategy.validate_strategy_config({})

    @pytest.mark.unit
    def test_unknown_keys_rejected(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="Unknown config keys"):
            strategy.validate_strategy_config({"unknown_key": 42})

    @pytest.mark.unit
    def test_invalid_debounce_zero(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="positive integer"):
            strategy.validate_strategy_config({"debounce": 0})

    @pytest.mark.unit
    def test_invalid_debounce_negative(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="positive integer"):
            strategy.validate_strategy_config({"debounce": -1})

    @pytest.mark.unit
    def test_invalid_debounce_bool(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="positive integer"):
            strategy.validate_strategy_config({"debounce": True})

    @pytest.mark.unit
    def test_invalid_debounce_default_zero(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="positive integer"):
            strategy.validate_strategy_config({"debounce_default": 0})

    @pytest.mark.unit
    def test_invalid_on_event_empty(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="non-empty string"):
            strategy.validate_strategy_config({"on_event": ""})

    @pytest.mark.unit
    def test_invalid_transition_event_empty(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="non-empty string"):
            strategy.validate_strategy_config({"transition_event": ""})

    @pytest.mark.unit
    def test_invalid_on_event_non_string(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="non-empty string"):
            strategy.validate_strategy_config({"on_event": 123})

    @pytest.mark.unit
    def test_invalid_on_event_bool(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="non-empty string"):
            strategy.validate_strategy_config({"on_event": True})

    @pytest.mark.unit
    def test_debounce_exceeds_max(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="<= 10000"):
            strategy.validate_strategy_config({"debounce": 10_001})

    @pytest.mark.unit
    def test_debounce_default_exceeds_max(self) -> None:
        strategy = EventDrivenStrategy()
        with pytest.raises(ValueError, match="<= 10000"):
            strategy.validate_strategy_config({"debounce_default": 10_001})

    @pytest.mark.unit
    async def test_debounce_default_fallback_on_bool(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(debounce_default=5)
        # Activate with valid config first
        await strategy.on_sprint_activated(sprint, config)

        # Now activate with bool -- should fallback to default
        bad_config = SprintConfig(
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.EVENT_DRIVEN,
                strategy_config={"debounce_default": True},
            ),
        )
        await strategy.on_sprint_activated(sprint, bad_config)
        # Verify the debounce_default is the default (5), not True (1)
        assert strategy._debounce_default == 5

    @pytest.mark.unit
    async def test_debounce_default_fallback_on_float(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        bad_config = SprintConfig(
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.EVENT_DRIVEN,
                strategy_config={"debounce_default": 3.5},
            ),
        )
        await strategy.on_sprint_activated(sprint, bad_config)
        assert strategy._debounce_default == 5

    @pytest.mark.unit
    async def test_debounce_default_fallback_on_zero(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        bad_config = SprintConfig(
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.EVENT_DRIVEN,
                strategy_config={"debounce_default": 0},
            ),
        )
        await strategy.on_sprint_activated(sprint, bad_config)
        assert strategy._debounce_default == 5

    @pytest.mark.unit
    def test_transition_with_strategy_config_none(self) -> None:
        strategy = EventDrivenStrategy()
        sprint = make_sprint()
        config = SprintConfig(
            ceremony_policy=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.EVENT_DRIVEN,
                strategy_config=None,
            ),
        )
        ctx = make_context()
        # No transition_event configured -- should return None
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None
