"""Tests for budget cap strategy."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.strategies.budget_cap import BudgetCapStrategy

from .conftest import make_context, make_signal


@pytest.mark.unit
class TestBudgetCapStrategy:
    """BudgetCapStrategy decision logic."""

    @pytest.mark.parametrize(
        ("burn_rate_value", "expected_action_types"),
        [
            (95.0, (ScalingActionType.HOLD,)),
            (75.0, (ScalingActionType.HOLD,)),
            (50.0, ()),
        ],
        ids=[
            "hold-only-when-over-safety-margin",
            "hold-between-headroom-and-safety",
            "no-action-under-headroom",
        ],
    )
    async def test_threshold_decisions(
        self,
        burn_rate_value: float,
        expected_action_types: tuple[str, ...],
    ) -> None:
        if burn_rate_value >= 90.0:
            strategy = BudgetCapStrategy(safety_margin=0.90)
        elif burn_rate_value >= 60.0:
            strategy = BudgetCapStrategy(safety_margin=0.90, headroom_fraction=0.60)
        else:
            strategy = BudgetCapStrategy(headroom_fraction=0.60)
        ctx = make_context(
            budget_signals=(
                make_signal(
                    name="burn_rate_percent",
                    value=burn_rate_value,
                    source="budget",
                ),
            ),
        )
        decisions = await strategy.evaluate(ctx)
        assert len(decisions) == len(expected_action_types)
        for i, expected_type in enumerate(expected_action_types):
            assert decisions[i].action_type == expected_type
        if burn_rate_value >= 90.0:
            assert decisions[0].confidence == 1.0

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
