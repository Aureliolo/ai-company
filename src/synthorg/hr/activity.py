"""Pure functions for building agent activity timelines.

Merges lifecycle events and task metric records into a unified
chronological timeline, and filters career-relevant events.
"""

from typing import TYPE_CHECKING

from synthorg.api.dto import ActivityEvent, CareerEvent
from synthorg.hr.enums import LifecycleEventType

if TYPE_CHECKING:
    from synthorg.hr.models import AgentLifecycleEvent
    from synthorg.hr.performance.models import TaskMetricRecord

_CAREER_EVENT_TYPES: frozenset[LifecycleEventType] = frozenset(
    {
        LifecycleEventType.HIRED,
        LifecycleEventType.FIRED,
        LifecycleEventType.PROMOTED,
        LifecycleEventType.DEMOTED,
        LifecycleEventType.ONBOARDED,
    }
)


def _lifecycle_to_activity(event: AgentLifecycleEvent) -> ActivityEvent:
    """Convert a lifecycle event to a timeline activity event."""
    return ActivityEvent(
        event_type=event.event_type.value,
        timestamp=event.timestamp,
        description=event.details or f"Agent {event.event_type.value}",
        related_ids={"agent_id": str(event.agent_id)},
    )


def _task_metric_to_activity(record: TaskMetricRecord) -> ActivityEvent:
    """Convert a task metric record to a timeline activity event."""
    status = "succeeded" if record.is_success else "failed"
    desc = (
        f"Task {record.task_id} {status} "
        f"({record.duration_seconds:.1f}s, ${record.cost_usd:.4f})"
    )
    return ActivityEvent(
        event_type="task_completed",
        timestamp=record.completed_at,
        description=desc,
        related_ids={
            "task_id": str(record.task_id),
            "agent_id": str(record.agent_id),
        },
    )


def merge_activity_timeline(
    lifecycle_events: tuple[AgentLifecycleEvent, ...],
    task_metrics: tuple[TaskMetricRecord, ...],
) -> tuple[ActivityEvent, ...]:
    """Merge lifecycle events and task metrics into a chronological timeline.

    Events are sorted by timestamp descending (most recent first).

    Args:
        lifecycle_events: Agent lifecycle events.
        task_metrics: Task completion metric records.

    Returns:
        Merged and sorted activity events.
    """
    activities: list[ActivityEvent] = [
        _lifecycle_to_activity(e) for e in lifecycle_events
    ]
    activities.extend(_task_metric_to_activity(r) for r in task_metrics)
    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return tuple(activities)


def filter_career_events(
    lifecycle_events: tuple[AgentLifecycleEvent, ...],
) -> tuple[CareerEvent, ...]:
    """Filter lifecycle events to career-relevant milestones only.

    Career events include: hired, fired, promoted, demoted, onboarded.
    Sorted by timestamp ascending (chronological career progression).

    Args:
        lifecycle_events: All lifecycle events for an agent.

    Returns:
        Career-relevant events in chronological order.
    """
    career: list[CareerEvent] = [
        CareerEvent(
            event_type=e.event_type.value,
            timestamp=e.timestamp,
            description=e.details or f"Agent {e.event_type.value}",
            initiated_by=e.initiated_by,
            metadata=e.metadata,
        )
        for e in lifecycle_events
        if e.event_type in _CAREER_EVENT_TYPES
    ]
    career.sort(key=lambda c: c.timestamp)
    return tuple(career)
