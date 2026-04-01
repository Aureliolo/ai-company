"""Tests for CeremonyEvalContext dataclass."""

from typing import Any

import pytest

from synthorg.engine.workflow.ceremony_context import CeremonyEvalContext


class TestCeremonyEvalContext:
    """CeremonyEvalContext tests."""

    @pytest.mark.unit
    def test_construction(self) -> None:
        ctx = CeremonyEvalContext(
            completions_since_last_trigger=3,
            total_completions_this_sprint=10,
            total_tasks_in_sprint=20,
            elapsed_seconds=120.0,
            budget_consumed_fraction=0.5,
            budget_remaining=100.0,
            velocity_history=(),
            external_events=(),
            sprint_percentage_complete=0.5,
            story_points_completed=21.0,
            story_points_committed=42.0,
        )
        assert ctx.completions_since_last_trigger == 3
        assert ctx.total_completions_this_sprint == 10
        assert ctx.total_tasks_in_sprint == 20
        assert ctx.elapsed_seconds == 120.0
        assert ctx.budget_consumed_fraction == 0.5
        assert ctx.budget_remaining == 100.0
        assert ctx.velocity_history == ()
        assert ctx.external_events == ()
        assert ctx.sprint_percentage_complete == 0.5
        assert ctx.story_points_completed == 21.0
        assert ctx.story_points_committed == 42.0

    @pytest.mark.unit
    def test_frozen(self) -> None:
        ctx = CeremonyEvalContext(
            completions_since_last_trigger=0,
            total_completions_this_sprint=0,
            total_tasks_in_sprint=10,
            elapsed_seconds=0.0,
            budget_consumed_fraction=0.0,
            budget_remaining=200.0,
            velocity_history=(),
            external_events=(),
            sprint_percentage_complete=0.0,
            story_points_completed=0.0,
            story_points_committed=50.0,
        )
        with pytest.raises(AttributeError):
            ctx.completions_since_last_trigger = 5  # type: ignore[misc]

    @pytest.mark.unit
    def test_with_velocity_history(self) -> None:
        from synthorg.engine.workflow.sprint_velocity import VelocityRecord

        record = VelocityRecord(
            sprint_id="sprint-1",
            sprint_number=1,
            story_points_committed=50.0,
            story_points_completed=42.0,
            duration_days=14,
        )
        ctx = CeremonyEvalContext(
            completions_since_last_trigger=0,
            total_completions_this_sprint=0,
            total_tasks_in_sprint=10,
            elapsed_seconds=0.0,
            budget_consumed_fraction=0.0,
            budget_remaining=0.0,
            velocity_history=(record,),
            external_events=(),
            sprint_percentage_complete=0.0,
            story_points_completed=0.0,
            story_points_committed=50.0,
        )
        assert len(ctx.velocity_history) == 1
        assert ctx.velocity_history[0].sprint_id == "sprint-1"

    @pytest.mark.unit
    def test_with_external_events(self) -> None:
        ctx = CeremonyEvalContext(
            completions_since_last_trigger=0,
            total_completions_this_sprint=0,
            total_tasks_in_sprint=10,
            elapsed_seconds=0.0,
            budget_consumed_fraction=0.0,
            budget_remaining=0.0,
            velocity_history=(),
            external_events=("pr_merged", "deploy_complete"),
            sprint_percentage_complete=0.0,
            story_points_completed=0.0,
            story_points_committed=50.0,
        )
        assert ctx.external_events == ("pr_merged", "deploy_complete")

    @pytest.mark.unit
    def test_equality(self) -> None:
        kwargs: dict[str, Any] = {
            "completions_since_last_trigger": 1,
            "total_completions_this_sprint": 5,
            "total_tasks_in_sprint": 10,
            "elapsed_seconds": 60.0,
            "budget_consumed_fraction": 0.0,
            "budget_remaining": 0.0,
            "velocity_history": (),
            "external_events": (),
            "sprint_percentage_complete": 0.5,
            "story_points_completed": 25.0,
            "story_points_committed": 50.0,
        }
        a = CeremonyEvalContext(**kwargs)
        b = CeremonyEvalContext(**kwargs)
        assert a == b
