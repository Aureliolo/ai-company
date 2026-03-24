"""Tests for the activity timeline pure functions."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.enums import Complexity, TaskType
from synthorg.hr.activity import filter_career_events, merge_activity_timeline
from synthorg.hr.enums import LifecycleEventType
from synthorg.hr.models import AgentLifecycleEvent
from synthorg.hr.performance.models import TaskMetricRecord

_NOW = datetime(2026, 3, 24, 12, 0, 0, tzinfo=UTC)


def _make_lifecycle_event(  # noqa: PLR0913
    *,
    event_type: LifecycleEventType = LifecycleEventType.HIRED,
    timestamp: datetime = _NOW,
    agent_id: str = "agent-001",
    agent_name: str = "alice",
    details: str = "",
    initiated_by: str = "system",
    metadata: dict[str, str] | None = None,
) -> AgentLifecycleEvent:
    return AgentLifecycleEvent(
        agent_id=agent_id,
        agent_name=agent_name,
        event_type=event_type,
        timestamp=timestamp,
        initiated_by=initiated_by,
        details=details,
        metadata=metadata or {},
    )


def _make_task_metric(  # noqa: PLR0913
    *,
    completed_at: datetime = _NOW,
    agent_id: str = "agent-001",
    task_id: str = "task-001",
    is_success: bool = True,
    duration_seconds: float = 60.0,
    cost_usd: float = 0.05,
) -> TaskMetricRecord:
    return TaskMetricRecord(
        agent_id=agent_id,
        task_id=task_id,
        task_type=TaskType.DEVELOPMENT,
        completed_at=completed_at,
        is_success=is_success,
        duration_seconds=duration_seconds,
        cost_usd=cost_usd,
        turns_used=5,
        tokens_used=1000,
        complexity=Complexity.MEDIUM,
    )


@pytest.mark.unit
class TestMergeActivityTimeline:
    def test_merge_lifecycle_and_tasks(self) -> None:
        hired = _make_lifecycle_event(
            event_type=LifecycleEventType.HIRED,
            timestamp=_NOW - timedelta(days=10),
            details="Hired as developer",
        )
        task = _make_task_metric(
            completed_at=_NOW - timedelta(days=5),
            task_id="task-100",
        )
        promoted = _make_lifecycle_event(
            event_type=LifecycleEventType.PROMOTED,
            timestamp=_NOW - timedelta(days=1),
            details="Promoted to senior",
        )

        timeline = merge_activity_timeline(
            lifecycle_events=(hired, promoted),
            task_metrics=(task,),
        )

        assert len(timeline) == 3
        # Most recent first
        assert timeline[0].event_type == "promoted"
        assert timeline[1].event_type == "task_completed"
        assert timeline[2].event_type == "hired"

    def test_empty_inputs(self) -> None:
        timeline = merge_activity_timeline(
            lifecycle_events=(),
            task_metrics=(),
        )
        assert timeline == ()

    def test_only_lifecycle_events(self) -> None:
        hired = _make_lifecycle_event(
            event_type=LifecycleEventType.HIRED,
            timestamp=_NOW - timedelta(days=5),
        )
        onboarded = _make_lifecycle_event(
            event_type=LifecycleEventType.ONBOARDED,
            timestamp=_NOW - timedelta(days=4),
        )

        timeline = merge_activity_timeline(
            lifecycle_events=(hired, onboarded),
            task_metrics=(),
        )

        assert len(timeline) == 2
        assert timeline[0].event_type == "onboarded"
        assert timeline[0].description == "Agent onboarded"
        assert timeline[1].event_type == "hired"
        assert timeline[1].description == "Agent hired"

    def test_only_task_metrics(self) -> None:
        t1 = _make_task_metric(
            completed_at=_NOW - timedelta(hours=2),
            task_id="task-a",
        )
        t2 = _make_task_metric(
            completed_at=_NOW - timedelta(hours=1),
            task_id="task-b",
            is_success=False,
        )

        timeline = merge_activity_timeline(
            lifecycle_events=(),
            task_metrics=(t1, t2),
        )

        assert len(timeline) == 2
        assert timeline[0].event_type == "task_completed"
        assert timeline[0].related_ids["task_id"] == "task-b"
        assert "failed" in timeline[0].description
        assert timeline[1].related_ids["task_id"] == "task-a"
        assert "succeeded" in timeline[1].description
        assert "USD" in timeline[1].description

    def test_identical_timestamps_stable_sort(self) -> None:
        ts = _NOW - timedelta(days=1)
        hired = _make_lifecycle_event(
            event_type=LifecycleEventType.HIRED,
            timestamp=ts,
        )
        task = _make_task_metric(completed_at=ts, task_id="task-same-ts")

        timeline = merge_activity_timeline(
            lifecycle_events=(hired,),
            task_metrics=(task,),
        )

        assert len(timeline) == 2
        # Stable sort: lifecycle events appear before task metrics at same timestamp
        assert timeline[0].event_type == "hired"
        assert timeline[1].event_type == "task_completed"

    def test_related_ids_populated(self) -> None:
        hired = _make_lifecycle_event(agent_id="agent-001")
        task = _make_task_metric(agent_id="agent-001", task_id="task-x")

        timeline = merge_activity_timeline(
            lifecycle_events=(hired,),
            task_metrics=(task,),
        )

        assert timeline[0].related_ids["agent_id"] == "agent-001"
        assert timeline[1].related_ids["agent_id"] == "agent-001"
        assert timeline[1].related_ids["task_id"] == "task-x"


@pytest.mark.unit
class TestFilterCareerEvents:
    def test_filters_to_career_types(self) -> None:
        hired = _make_lifecycle_event(
            event_type=LifecycleEventType.HIRED,
            timestamp=_NOW - timedelta(days=30),
            details="Hired",
        )
        status_changed = _make_lifecycle_event(
            event_type=LifecycleEventType.STATUS_CHANGED,
            timestamp=_NOW - timedelta(days=20),
            details="Status changed",
        )
        promoted = _make_lifecycle_event(
            event_type=LifecycleEventType.PROMOTED,
            timestamp=_NOW - timedelta(days=10),
            details="Promoted",
        )

        career = filter_career_events((hired, status_changed, promoted))

        assert len(career) == 2
        assert career[0].event_type == "hired"
        assert career[1].event_type == "promoted"

    def test_chronological_order(self) -> None:
        promoted = _make_lifecycle_event(
            event_type=LifecycleEventType.PROMOTED,
            timestamp=_NOW - timedelta(days=1),
        )
        hired = _make_lifecycle_event(
            event_type=LifecycleEventType.HIRED,
            timestamp=_NOW - timedelta(days=30),
        )

        career = filter_career_events((promoted, hired))

        # Sorted ascending by timestamp
        assert career[0].event_type == "hired"
        assert career[1].event_type == "promoted"

    def test_empty_input(self) -> None:
        assert filter_career_events(()) == ()

    def test_no_career_events(self) -> None:
        status_changed = _make_lifecycle_event(
            event_type=LifecycleEventType.STATUS_CHANGED,
        )
        offboarded = _make_lifecycle_event(
            event_type=LifecycleEventType.OFFBOARDED,
        )

        career = filter_career_events((status_changed, offboarded))

        assert career == ()

    def test_all_career_types_included(self) -> None:
        events = tuple(
            _make_lifecycle_event(
                event_type=et,
                timestamp=_NOW - timedelta(days=i),
            )
            for i, et in enumerate(
                [
                    LifecycleEventType.HIRED,
                    LifecycleEventType.ONBOARDED,
                    LifecycleEventType.PROMOTED,
                    LifecycleEventType.DEMOTED,
                    LifecycleEventType.FIRED,
                ]
            )
        )

        career = filter_career_events(events)

        assert len(career) == 5
        types = {c.event_type for c in career}
        assert types == {"hired", "onboarded", "promoted", "demoted", "fired"}

    def test_empty_details_produces_fallback_description(self) -> None:
        hired = _make_lifecycle_event(
            event_type=LifecycleEventType.HIRED,
            details="",
        )

        career = filter_career_events((hired,))

        assert career[0].description == "Agent hired"

    def test_metadata_and_initiated_by_preserved(self) -> None:
        hired = _make_lifecycle_event(
            event_type=LifecycleEventType.HIRED,
            initiated_by="ceo",
            details="Hired as developer",
            metadata={"reason": "expansion", "team": "backend"},
        )

        career = filter_career_events((hired,))

        assert career[0].initiated_by == "ceo"
        assert career[0].description == "Hired as developer"
        assert career[0].metadata == {"reason": "expansion", "team": "backend"}
