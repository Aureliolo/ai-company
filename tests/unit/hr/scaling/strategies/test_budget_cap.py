"""Tests for budget cap strategy."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.strategies.budget_cap import BudgetCapStrategy

from .conftest import make_context, make_signal


@pytest.mark.unit
class TestBudgetCapStrategy:
    """BudgetCapStrategy decision logic."""

    async def test_prune_when_over_safety_margin(self) -> None:
        strategy = BudgetCapStrategy(safety_margin=0.90)
        ctx = make_context(
            budget_signals=(
                make_signal(name="burn_rate_percent", value=95.0, source="budget"),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 1
        assert decisions[0].action_type == ScalingActionType.PRUNE
        assert decisions[0].confidence == 1.0

    async def test_hold_between_headroom_and_safety(self) -> None:
        strategy = BudgetCapStrategy(safety_margin=0.90, headroom_fraction=0.60)
        ctx = make_context(
            budget_signals=(
                make_signal(name="burn_rate_percent", value=75.0, source="budget"),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 1
        assert decisions[0].action_type == ScalingActionType.HOLD

    async def test_no_action_under_headroom(self) -> None:
        strategy = BudgetCapStrategy(headroom_fraction=0.60)
        ctx = make_context(
            budget_signals=(
                make_signal(name="burn_rate_percent", value=50.0, source="budget"),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_no_signals_returns_empty(self) -> None:
        strategy = BudgetCapStrategy()
        ctx = make_context(budget_signals=())
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == 0

    async def test_name_property(self) -> None:
        strategy = BudgetCapStrategy()
        assert strategy.name == "budget_cap"

    async def test_action_types(self) -> None:
        strategy = BudgetCapStrategy()
        assert ScalingActionType.PRUNE in strategy.action_types
        assert ScalingActionType.HOLD in strategy.action_types
