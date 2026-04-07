"""Tests for the trajectory budget guard."""

import pytest

from synthorg.engine.trajectory.budget_guard import (
    check_trajectory_budget,
)


@pytest.mark.unit
class TestCheckTrajectoryBudget:
    """check_trajectory_budget pure function tests."""

    def test_sufficient_budget(self) -> None:
        assert check_trajectory_budget(
            remaining_budget=10.0,
            estimated_step_cost=1.0,
            k=2,
            margin=0.2,
        )

    def test_insufficient_budget(self) -> None:
        assert not check_trajectory_budget(
            remaining_budget=2.0,
            estimated_step_cost=1.0,
            k=3,
            margin=0.2,
        )

    def test_exact_budget(self) -> None:
        # available = 10 * 0.8 = 8.0, required = 4 * 2 = 8.0
        assert check_trajectory_budget(
            remaining_budget=10.0,
            estimated_step_cost=4.0,
            k=2,
            margin=0.2,
        )

    def test_zero_remaining_blocked(self) -> None:
        assert not check_trajectory_budget(
            remaining_budget=0.0,
            estimated_step_cost=1.0,
            k=2,
        )

    def test_negative_remaining_blocked(self) -> None:
        assert not check_trajectory_budget(
            remaining_budget=-5.0,
            estimated_step_cost=1.0,
            k=2,
        )

    def test_zero_step_cost_blocked(self) -> None:
        assert not check_trajectory_budget(
            remaining_budget=10.0,
            estimated_step_cost=0.0,
            k=2,
        )

    def test_zero_margin(self) -> None:
        # available = 5 * 1.0 = 5.0, required = 1 * 5 = 5.0
        assert check_trajectory_budget(
            remaining_budget=5.0,
            estimated_step_cost=1.0,
            k=5,
            margin=0.0,
        )

    def test_full_margin(self) -> None:
        # available = 10 * 0.0 = 0.0 -- nothing available
        assert not check_trajectory_budget(
            remaining_budget=10.0,
            estimated_step_cost=1.0,
            k=2,
            margin=1.0,
        )

    def test_default_margin(self) -> None:
        # Default margin = 0.2, available = 10 * 0.8 = 8.0
        assert check_trajectory_budget(
            remaining_budget=10.0,
            estimated_step_cost=2.0,
            k=3,
        )
        # required = 2 * 4 = 8.0, available = 10 * 0.8 = 8.0
        assert check_trajectory_budget(
            remaining_budget=10.0,
            estimated_step_cost=2.0,
            k=4,
        )
        # required = 2 * 5 = 10.0 > 8.0
        assert not check_trajectory_budget(
            remaining_budget=10.0,
            estimated_step_cost=2.0,
            k=5,
        )
