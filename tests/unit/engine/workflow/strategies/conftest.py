"""Shared test helpers for ceremony scheduling strategy tests."""

from typing import Any

from synthorg.engine.workflow.ceremony_context import CeremonyEvalContext
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus

SECONDS_PER_DAY: float = 86_400.0


def make_sprint(
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


def make_context(
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
