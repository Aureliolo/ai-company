"""Unit tests for project-level budget enforcement."""

import pytest

from synthorg.budget.config import BudgetConfig
from synthorg.budget.enforcer import BudgetEnforcer
from synthorg.budget.errors import ProjectBudgetExhaustedError
from synthorg.budget.tracker import CostTracker

from .conftest import make_cost_record


def _make_enforcer(
    *,
    tracker: CostTracker | None = None,
) -> BudgetEnforcer:
    config = BudgetConfig(total_monthly=100.0)
    t = tracker or CostTracker(budget_config=config)
    return BudgetEnforcer(budget_config=config, cost_tracker=t)


@pytest.mark.unit
class TestCheckProjectBudget:
    """Tests for BudgetEnforcer.check_project_budget()."""

    async def test_passes_when_under_budget(self) -> None:
        tracker = CostTracker()
        await tracker.record(make_cost_record(project_id="proj-1", cost_usd=1.0))
        enforcer = _make_enforcer(tracker=tracker)

        # Should not raise
        await enforcer.check_project_budget("proj-1", project_budget=10.0)

    async def test_raises_when_budget_exceeded(self) -> None:
        tracker = CostTracker()
        await tracker.record(make_cost_record(project_id="proj-1", cost_usd=10.0))
        enforcer = _make_enforcer(tracker=tracker)

        with pytest.raises(ProjectBudgetExhaustedError) as exc_info:
            await enforcer.check_project_budget("proj-1", project_budget=5.0)

        assert exc_info.value.project_id == "proj-1"
        assert exc_info.value.project_budget == 5.0
        assert exc_info.value.project_spent >= 10.0

    async def test_raises_when_exactly_at_budget(self) -> None:
        tracker = CostTracker()
        await tracker.record(make_cost_record(project_id="proj-1", cost_usd=5.0))
        enforcer = _make_enforcer(tracker=tracker)

        with pytest.raises(ProjectBudgetExhaustedError):
            await enforcer.check_project_budget("proj-1", project_budget=5.0)

    async def test_zero_budget_skips_check(self) -> None:
        tracker = CostTracker()
        await tracker.record(make_cost_record(project_id="proj-1", cost_usd=100.0))
        enforcer = _make_enforcer(tracker=tracker)

        # Zero budget means no project-level limit
        await enforcer.check_project_budget("proj-1", project_budget=0.0)

    async def test_no_records_passes(self) -> None:
        enforcer = _make_enforcer()

        # No cost records -- should pass
        await enforcer.check_project_budget("proj-1", project_budget=10.0)

    async def test_isolates_between_projects(self) -> None:
        tracker = CostTracker()
        await tracker.record(make_cost_record(project_id="proj-1", cost_usd=8.0))
        await tracker.record(make_cost_record(project_id="proj-2", cost_usd=2.0))
        enforcer = _make_enforcer(tracker=tracker)

        # proj-1 at 8.0 against 10.0 budget -> passes
        await enforcer.check_project_budget("proj-1", project_budget=10.0)

        # proj-2 at 2.0 against 1.0 budget -> exceeds
        with pytest.raises(ProjectBudgetExhaustedError):
            await enforcer.check_project_budget("proj-2", project_budget=1.0)

    async def test_is_subclass_of_budget_exhausted(self) -> None:
        """ProjectBudgetExhaustedError is caught by BudgetExhaustedError."""
        from synthorg.budget.errors import BudgetExhaustedError

        tracker = CostTracker()
        await tracker.record(make_cost_record(project_id="proj-1", cost_usd=10.0))
        enforcer = _make_enforcer(tracker=tracker)

        with pytest.raises(BudgetExhaustedError):
            await enforcer.check_project_budget("proj-1", project_budget=5.0)
