"""Tests for the BudgetDrivenStrategy implementation."""

import pytest

from synthorg.communication.meeting.enums import MeetingProtocolType
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
from synthorg.engine.workflow.strategies.budget_driven import (
    BudgetDrivenStrategy,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType

from .conftest import make_context, make_sprint


def _make_ceremony(
    name: str = "standup",
    budget_thresholds: list[float] | None = None,
) -> SprintCeremonyConfig:
    """Create a ceremony config with budget-driven policy override."""
    config: dict[str, object] = {}
    if budget_thresholds is not None:
        config["budget_thresholds"] = budget_thresholds
    return SprintCeremonyConfig(
        name=name,
        protocol=MeetingProtocolType.ROUND_ROBIN,
        policy_override=CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.BUDGET_DRIVEN,
            strategy_config=config,
        ),
    )


def _make_sprint_config(
    transition_threshold: float | None = None,
) -> SprintConfig:
    """Create a SprintConfig with budget-driven policy."""
    config: dict[str, object] = {}
    if transition_threshold is not None:
        config["transition_threshold"] = transition_threshold
    return SprintConfig(
        ceremony_policy=CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.BUDGET_DRIVEN,
            strategy_config=config,
        ),
    )


class TestBudgetDrivenStrategyProtocol:
    """Verify BudgetDrivenStrategy satisfies the protocol."""

    @pytest.mark.unit
    def test_is_protocol_instance(self) -> None:
        strategy = BudgetDrivenStrategy()
        assert isinstance(strategy, CeremonySchedulingStrategy)

    @pytest.mark.unit
    def test_strategy_type(self) -> None:
        assert (
            BudgetDrivenStrategy().strategy_type is CeremonyStrategyType.BUDGET_DRIVEN
        )

    @pytest.mark.unit
    def test_default_velocity_calculator(self) -> None:
        assert (
            BudgetDrivenStrategy().get_default_velocity_calculator()
            is VelocityCalcType.BUDGET
        )


class TestShouldFireCeremony:
    """should_fire_ceremony() tests."""

    @pytest.mark.unit
    def test_fires_when_threshold_crossed(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[25])
        sprint = make_sprint()
        ctx = make_context(budget_consumed_fraction=0.25)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    def test_does_not_fire_below_threshold(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[25])
        sprint = make_sprint()
        ctx = make_context(budget_consumed_fraction=0.24)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    def test_does_not_double_fire_same_threshold(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[25])
        sprint = make_sprint()
        ctx = make_context(budget_consumed_fraction=0.30)

        # First call fires
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True
        # Second call at same/higher budget does not re-fire 25%
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    def test_fires_next_threshold_after_budget_increase(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[25, 50, 75])
        sprint = make_sprint()

        # Fire at 25%
        ctx25 = make_context(budget_consumed_fraction=0.25)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx25) is True

        # Fire at 50%
        ctx50 = make_context(budget_consumed_fraction=0.50)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx50) is True

        # Fire at 75%
        ctx75 = make_context(budget_consumed_fraction=0.75)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx75) is True

    @pytest.mark.unit
    def test_multiple_thresholds_fire_one_at_a_time(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[25, 50, 75])
        sprint = make_sprint()

        # Budget jumps from 0 to 60% -- only the lowest unfired (25%) fires
        ctx = make_context(budget_consumed_fraction=0.60)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

        # Next call fires 50% (still below 60%)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

        # 75% not reached yet
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    def test_no_thresholds_returns_false(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = SprintCeremonyConfig(
            name="standup",
            protocol=MeetingProtocolType.ROUND_ROBIN,
            policy_override=CeremonyPolicyConfig(
                strategy=CeremonyStrategyType.BUDGET_DRIVEN,
                strategy_config={},
            ),
        )
        sprint = make_sprint()
        ctx = make_context(budget_consumed_fraction=0.50)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    def test_empty_thresholds_returns_false(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[])
        sprint = make_sprint()
        ctx = make_context(budget_consumed_fraction=0.50)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is False

    @pytest.mark.unit
    def test_independent_tracking_per_ceremony(self) -> None:
        strategy = BudgetDrivenStrategy()
        standup = _make_ceremony(
            name="standup",
            budget_thresholds=[25, 50],
        )
        retro = _make_ceremony(
            name="retro",
            budget_thresholds=[50],
        )
        sprint = make_sprint()
        ctx = make_context(budget_consumed_fraction=0.50)

        # Both fire on their respective thresholds
        assert strategy.should_fire_ceremony(standup, sprint, ctx) is True
        assert strategy.should_fire_ceremony(retro, sprint, ctx) is True

        # Standup fires 50% next
        assert strategy.should_fire_ceremony(standup, sprint, ctx) is True
        # Retro already fired 50%
        assert strategy.should_fire_ceremony(retro, sprint, ctx) is False

    @pytest.mark.unit
    def test_fires_at_100_percent(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[100])
        sprint = make_sprint()
        ctx = make_context(budget_consumed_fraction=1.0)
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True


class TestShouldTransitionSprint:
    """should_transition_sprint() tests."""

    @pytest.mark.unit
    def test_transitions_at_100_pct(self) -> None:
        strategy = BudgetDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        ctx = make_context(budget_consumed_fraction=1.0)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_transitions_at_custom_threshold(self) -> None:
        strategy = BudgetDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config(transition_threshold=80.0)
        ctx = make_context(budget_consumed_fraction=0.80)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    def test_does_not_transition_below_threshold(self) -> None:
        strategy = BudgetDrivenStrategy()
        sprint = make_sprint()
        config = _make_sprint_config()
        ctx = make_context(budget_consumed_fraction=0.99)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None

    @pytest.mark.unit
    def test_does_not_transition_non_active(self) -> None:
        strategy = BudgetDrivenStrategy()
        sprint = make_sprint(status=SprintStatus.PLANNING)
        config = _make_sprint_config()
        ctx = make_context(budget_consumed_fraction=1.0)
        result = strategy.should_transition_sprint(sprint, config, ctx)
        assert result is None


class TestLifecycleHooks:
    """Lifecycle hook tests."""

    @pytest.mark.unit
    async def test_on_sprint_activated_clears_fired_thresholds(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[25])
        sprint = make_sprint()
        config = _make_sprint_config()

        # Fire threshold
        ctx = make_context(budget_consumed_fraction=0.30)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        # Activate new sprint -- state should reset
        await strategy.on_sprint_activated(sprint, config)

        # Same threshold fires again after reset
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True

    @pytest.mark.unit
    async def test_on_sprint_deactivated_clears_fired_thresholds(self) -> None:
        strategy = BudgetDrivenStrategy()
        ceremony = _make_ceremony(budget_thresholds=[25])
        sprint = make_sprint()

        # Fire threshold
        ctx = make_context(budget_consumed_fraction=0.30)
        strategy.should_fire_ceremony(ceremony, sprint, ctx)

        # Deactivate sprint
        await strategy.on_sprint_deactivated()

        # Threshold fires again after reset
        assert strategy.should_fire_ceremony(ceremony, sprint, ctx) is True


class TestValidateStrategyConfig:
    """validate_strategy_config() tests."""

    @pytest.mark.unit
    def test_valid_config(self) -> None:
        strategy = BudgetDrivenStrategy()
        strategy.validate_strategy_config(
            {
                "budget_thresholds": [25, 50, 75, 100],
            }
        )

    @pytest.mark.unit
    def test_valid_config_with_transition(self) -> None:
        strategy = BudgetDrivenStrategy()
        strategy.validate_strategy_config(
            {
                "budget_thresholds": [25, 50],
                "transition_threshold": 80.0,
            }
        )

    @pytest.mark.unit
    def test_empty_config_valid(self) -> None:
        strategy = BudgetDrivenStrategy()
        strategy.validate_strategy_config({})

    @pytest.mark.unit
    def test_unknown_keys_rejected(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match="Unknown config keys"):
            strategy.validate_strategy_config({"unknown_key": 42})

    @pytest.mark.unit
    def test_invalid_threshold_zero(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match="in \\(0, 100\\]"):
            strategy.validate_strategy_config(
                {
                    "budget_thresholds": [0],
                }
            )

    @pytest.mark.unit
    def test_invalid_threshold_over_100(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match="in \\(0, 100\\]"):
            strategy.validate_strategy_config(
                {
                    "budget_thresholds": [101],
                }
            )

    @pytest.mark.unit
    def test_invalid_threshold_negative(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match="in \\(0, 100\\]"):
            strategy.validate_strategy_config(
                {
                    "budget_thresholds": [-10],
                }
            )

    @pytest.mark.unit
    def test_invalid_thresholds_not_list(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match="list"):
            strategy.validate_strategy_config(
                {
                    "budget_thresholds": 50,
                }
            )

    @pytest.mark.unit
    def test_duplicate_thresholds_rejected(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match=r"[Dd]uplicate"):
            strategy.validate_strategy_config(
                {
                    "budget_thresholds": [25, 50, 25],
                }
            )

    @pytest.mark.unit
    def test_invalid_transition_threshold_zero(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match="in \\(0, 100\\]"):
            strategy.validate_strategy_config(
                {
                    "transition_threshold": 0,
                }
            )

    @pytest.mark.unit
    def test_invalid_transition_threshold_over_100(self) -> None:
        strategy = BudgetDrivenStrategy()
        with pytest.raises(ValueError, match="in \\(0, 100\\]"):
            strategy.validate_strategy_config(
                {
                    "transition_threshold": 101,
                }
            )
