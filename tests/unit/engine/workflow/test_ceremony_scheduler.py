"""Tests for CeremonyScheduler service."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.communication.meeting.enums import MeetingProtocolType
from synthorg.engine.workflow.ceremony_policy import (
    CeremonyPolicyConfig,
    CeremonyStrategyType,
)
from synthorg.engine.workflow.ceremony_scheduler import CeremonyScheduler
from synthorg.engine.workflow.sprint_config import (
    SprintCeremonyConfig,
    SprintConfig,
)
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.engine.workflow.strategies.task_driven import (
    TaskDrivenStrategy,
)


def _make_sprint(
    task_count: int = 10,
    completed_count: int = 0,
    status: SprintStatus = SprintStatus.ACTIVE,
    points_per_task: float = 3.0,
) -> Sprint:
    task_ids = tuple(f"task-{i}" for i in range(task_count))
    completed_ids = tuple(f"task-{i}" for i in range(completed_count))
    kwargs: dict[str, Any] = {
        "id": "sprint-1",
        "name": "Sprint 1",
        "sprint_number": 1,
        "status": status,
        "task_ids": task_ids,
        "completed_task_ids": completed_ids,
        "story_points_committed": float(task_count * points_per_task),
        "story_points_completed": float(completed_count * points_per_task),
    }
    if status is not SprintStatus.PLANNING:
        kwargs["start_date"] = "2026-04-01T00:00:00"
    if status is SprintStatus.COMPLETED:
        kwargs["end_date"] = "2026-04-14T00:00:00"
    return Sprint(**kwargs)


def _make_config(
    ceremonies: tuple[SprintCeremonyConfig, ...] = (),
    transition_threshold: float = 1.0,
) -> SprintConfig:
    return SprintConfig(
        ceremony_policy=CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.TASK_DRIVEN,
            auto_transition=True,
            transition_threshold=transition_threshold,
        ),
        ceremonies=ceremonies,
    )


def _ceremony_with_trigger(
    name: str,
    trigger: str,
    every_n: int = 5,
    sprint_percentage: float | None = None,
) -> SprintCeremonyConfig:
    config: dict = {"trigger": trigger}
    if trigger == "every_n_completions":
        config["every_n_completions"] = every_n
    if sprint_percentage is not None:
        config["sprint_percentage"] = sprint_percentage
    return SprintCeremonyConfig(
        name=name,
        protocol=MeetingProtocolType.ROUND_ROBIN,
        policy_override=CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.TASK_DRIVEN,
            strategy_config=config,
        ),
    )


def _make_mock_meeting_scheduler() -> MagicMock:
    mock = MagicMock()
    mock.trigger_event = AsyncMock(return_value=())
    return mock


class TestCeremonySchedulerActivation:
    """activate_sprint / deactivate_sprint tests."""

    @pytest.mark.unit
    async def test_activate_sets_running(self) -> None:
        scheduler = CeremonyScheduler(
            meeting_scheduler=_make_mock_meeting_scheduler(),
        )
        sprint = _make_sprint()
        config = _make_config()
        await scheduler.activate_sprint(sprint, config, TaskDrivenStrategy())
        assert scheduler.running is True
        assert scheduler.active_sprint is sprint

    @pytest.mark.unit
    async def test_deactivate_clears_state(self) -> None:
        scheduler = CeremonyScheduler(
            meeting_scheduler=_make_mock_meeting_scheduler(),
        )
        await scheduler.activate_sprint(
            _make_sprint(),
            _make_config(),
            TaskDrivenStrategy(),
        )
        await scheduler.deactivate_sprint()
        assert scheduler.running is False
        assert scheduler.active_sprint is None

    @pytest.mark.unit
    async def test_activate_fires_sprint_start_ceremonies(self) -> None:
        mock_ms = _make_mock_meeting_scheduler()
        scheduler = CeremonyScheduler(meeting_scheduler=mock_ms)
        ceremony = _ceremony_with_trigger("planning", "sprint_start")
        config = _make_config(ceremonies=(ceremony,))
        await scheduler.activate_sprint(
            _make_sprint(),
            config,
            TaskDrivenStrategy(),
        )
        mock_ms.trigger_event.assert_called_once()
        call_args = mock_ms.trigger_event.call_args
        assert "ceremony.planning.sprint-1" in str(call_args)

    @pytest.mark.unit
    async def test_double_activate_deactivates_first(self) -> None:
        scheduler = CeremonyScheduler(
            meeting_scheduler=_make_mock_meeting_scheduler(),
        )
        sprint1 = _make_sprint()
        sprint2 = _make_sprint()
        config = _make_config()
        strategy = TaskDrivenStrategy()
        await scheduler.activate_sprint(sprint1, config, strategy)
        await scheduler.activate_sprint(sprint2, config, strategy)
        assert scheduler.active_sprint is sprint2


class TestCeremonySchedulerTaskCompletion:
    """on_task_completed() tests."""

    @pytest.mark.unit
    async def test_fires_every_n_ceremony(self) -> None:
        mock_ms = _make_mock_meeting_scheduler()
        scheduler = CeremonyScheduler(meeting_scheduler=mock_ms)
        ceremony = _ceremony_with_trigger("standup", "every_n_completions", every_n=3)
        config = _make_config(ceremonies=(ceremony,))
        strategy = TaskDrivenStrategy()

        sprint = _make_sprint(task_count=10, completed_count=0)
        await scheduler.activate_sprint(sprint, config, strategy)

        # Simulate 3 task completions.
        for i in range(3):
            completed = i + 1
            sprint = _make_sprint(task_count=10, completed_count=completed)
            sprint = await scheduler.on_task_completed(
                sprint,
                f"task-{i}",
                3.0,
            )

        # The every_n_completions=3 ceremony should have fired.
        assert mock_ms.trigger_event.call_count >= 1

    @pytest.mark.unit
    async def test_auto_transitions_sprint(self) -> None:
        mock_ms = _make_mock_meeting_scheduler()
        scheduler = CeremonyScheduler(meeting_scheduler=mock_ms)
        config = _make_config(transition_threshold=1.0)
        strategy = TaskDrivenStrategy()

        sprint = _make_sprint(task_count=2, completed_count=1)
        await scheduler.activate_sprint(sprint, config, strategy)

        # Complete the last task.
        final_sprint = _make_sprint(task_count=2, completed_count=2)
        result = await scheduler.on_task_completed(
            final_sprint,
            "task-1",
            3.0,
        )
        assert result.status is SprintStatus.IN_REVIEW

    @pytest.mark.unit
    async def test_no_transition_below_threshold(self) -> None:
        mock_ms = _make_mock_meeting_scheduler()
        scheduler = CeremonyScheduler(meeting_scheduler=mock_ms)
        config = _make_config(transition_threshold=1.0)
        strategy = TaskDrivenStrategy()

        sprint = _make_sprint(task_count=10, completed_count=5)
        await scheduler.activate_sprint(sprint, config, strategy)

        sprint = _make_sprint(task_count=10, completed_count=6)
        result = await scheduler.on_task_completed(
            sprint,
            "task-5",
            3.0,
        )
        assert result.status is SprintStatus.ACTIVE

    @pytest.mark.unit
    async def test_not_running_returns_sprint_unchanged(self) -> None:
        scheduler = CeremonyScheduler(
            meeting_scheduler=_make_mock_meeting_scheduler(),
        )
        sprint = _make_sprint(task_count=10, completed_count=5)
        result = await scheduler.on_task_completed(sprint, "task-4", 3.0)
        assert result is sprint

    @pytest.mark.unit
    async def test_sprint_midpoint_fires_once(self) -> None:
        mock_ms = _make_mock_meeting_scheduler()
        scheduler = CeremonyScheduler(meeting_scheduler=mock_ms)
        ceremony = _ceremony_with_trigger("midpoint_review", "sprint_midpoint")
        config = _make_config(ceremonies=(ceremony,))
        strategy = TaskDrivenStrategy()

        sprint = _make_sprint(task_count=4, completed_count=0)
        await scheduler.activate_sprint(sprint, config, strategy)

        # Complete task 1 (25%).
        sprint = _make_sprint(task_count=4, completed_count=1)
        await scheduler.on_task_completed(sprint, "task-0", 3.0)
        initial_count = mock_ms.trigger_event.call_count

        # Complete task 2 (50%) -- should fire midpoint.
        sprint = _make_sprint(task_count=4, completed_count=2)
        await scheduler.on_task_completed(sprint, "task-1", 3.0)
        after_midpoint_count = mock_ms.trigger_event.call_count
        assert after_midpoint_count > initial_count

        # Complete task 3 (75%) -- should NOT fire midpoint again.
        sprint = _make_sprint(task_count=4, completed_count=3)
        await scheduler.on_task_completed(sprint, "task-2", 3.0)
        assert mock_ms.trigger_event.call_count == after_midpoint_count

    @pytest.mark.unit
    async def test_sprint_end_fires_once(self) -> None:
        mock_ms = _make_mock_meeting_scheduler()
        scheduler = CeremonyScheduler(meeting_scheduler=mock_ms)
        ceremony = _ceremony_with_trigger("retro", "sprint_end")
        config = _make_config(ceremonies=(ceremony,))
        strategy = TaskDrivenStrategy()

        sprint = _make_sprint(task_count=2, completed_count=0)
        await scheduler.activate_sprint(sprint, config, strategy)

        # Complete task 1 (50%).
        sprint = _make_sprint(task_count=2, completed_count=1)
        await scheduler.on_task_completed(sprint, "task-0", 3.0)
        count_before = mock_ms.trigger_event.call_count

        # Complete task 2 (100%) -- should fire sprint_end.
        sprint = _make_sprint(task_count=2, completed_count=2)
        await scheduler.on_task_completed(sprint, "task-1", 3.0)
        assert mock_ms.trigger_event.call_count > count_before

    @pytest.mark.unit
    async def test_trigger_event_error_is_logged_and_swallowed(self) -> None:
        mock_ms = _make_mock_meeting_scheduler()
        mock_ms.trigger_event = AsyncMock(side_effect=RuntimeError("boom"))
        scheduler = CeremonyScheduler(meeting_scheduler=mock_ms)
        ceremony = _ceremony_with_trigger("standup", "every_n_completions", every_n=1)
        config = _make_config(ceremonies=(ceremony,))
        strategy = TaskDrivenStrategy()

        sprint = _make_sprint(task_count=10, completed_count=1)
        await scheduler.activate_sprint(sprint, config, strategy)

        # Should not raise despite trigger_event failing.
        sprint = _make_sprint(task_count=10, completed_count=2)
        result = await scheduler.on_task_completed(sprint, "task-1", 3.0)
        assert result.status is SprintStatus.ACTIVE
