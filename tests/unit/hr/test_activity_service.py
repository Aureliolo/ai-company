"""Unit tests for :class:`ActivityFeedService`."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.budget.cost_record import CostRecord
from synthorg.communication.delegation.models import DelegationRecord
from synthorg.core.enums import Complexity, TaskType
from synthorg.core.types import NotBlankStr
from synthorg.hr.activity_service import ActivityFeedService
from synthorg.hr.enums import ActivityEventType, LifecycleEventType
from synthorg.hr.models import AgentLifecycleEvent
from synthorg.hr.performance.models import TaskMetricRecord
from synthorg.tools.invocation_record import ToolInvocationRecord

pytestmark = pytest.mark.unit

# Anchor timestamps relative to real wall-clock time so the service's
# ``datetime.now(UTC)`` window does not drop records that happen to be
# dated after a test-local constant (see ``get_agent_activity`` -- the
# window ends at ``datetime.now(UTC)``).
_NOW = datetime.now(UTC) - timedelta(hours=1)
_AGENT_ID = "agent-alice"


def _lifecycle(
    event_type: LifecycleEventType = LifecycleEventType.HIRED,
    *,
    offset_minutes: int = 0,
    event_id: str = "evt-1",
) -> AgentLifecycleEvent:
    return AgentLifecycleEvent(
        id=NotBlankStr(event_id),
        agent_id=NotBlankStr(_AGENT_ID),
        agent_name=NotBlankStr("alice"),
        event_type=event_type,
        timestamp=_NOW - timedelta(minutes=offset_minutes),
        initiated_by=NotBlankStr("system"),
        details=f"Agent {event_type.value}",
        metadata={},
    )


def _task_metric(
    offset_minutes: int = 0,
    task_id: str = "task-1",
    is_success: bool = True,
) -> TaskMetricRecord:
    return TaskMetricRecord(
        task_id=NotBlankStr(task_id),
        agent_id=NotBlankStr(_AGENT_ID),
        task_type=TaskType.DEVELOPMENT,
        started_at=_NOW - timedelta(minutes=offset_minutes + 1),
        completed_at=_NOW - timedelta(minutes=offset_minutes),
        duration_seconds=60.0,
        is_success=is_success,
        cost=0.01,
        currency="USD",
        turns_used=1,
        tokens_used=100,
        complexity=Complexity.MEDIUM,
    )


def _cost_record(offset_minutes: int = 0, task_id: str = "task-cost") -> CostRecord:
    return CostRecord(
        agent_id=NotBlankStr(_AGENT_ID),
        task_id=NotBlankStr(task_id),
        provider=NotBlankStr("test-provider"),
        model=NotBlankStr("test-small-001"),
        input_tokens=10,
        output_tokens=20,
        cost=0.02,
        currency="USD",
        timestamp=_NOW - timedelta(minutes=offset_minutes),
    )


def _tool_record(
    offset_minutes: int = 0, record_id: str = "inv-1"
) -> ToolInvocationRecord:
    return ToolInvocationRecord(
        id=NotBlankStr(record_id),
        agent_id=NotBlankStr(_AGENT_ID),
        tool_name=NotBlankStr("test_tool"),
        is_success=True,
        timestamp=_NOW - timedelta(minutes=offset_minutes),
        task_id=None,
    )


def _delegation(
    offset_minutes: int = 0,
    delegator_first: bool = True,
    delegation_id: str = "del-1",
) -> DelegationRecord:
    delegator = _AGENT_ID if delegator_first else "other-agent"
    delegatee = "other-agent" if delegator_first else _AGENT_ID
    return DelegationRecord(
        delegation_id=NotBlankStr(delegation_id),
        delegator_id=NotBlankStr(delegator),
        delegatee_id=NotBlankStr(delegatee),
        original_task_id=NotBlankStr("task-original"),
        delegated_task_id=NotBlankStr("task-delegated"),
        timestamp=_NOW - timedelta(minutes=offset_minutes),
    )


class _FakeLifecycleRepo:
    def __init__(self, events: list[AgentLifecycleEvent]) -> None:
        self._events = events
        self.calls: list[dict[str, object]] = []

    async def list_events(
        self,
        *,
        agent_id: str | None = None,
        event_type: LifecycleEventType | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[AgentLifecycleEvent, ...]:
        self.calls.append(
            {"agent_id": agent_id, "since": since, "limit": limit},
        )
        out = [
            e
            for e in self._events
            if (agent_id is None or str(e.agent_id) == agent_id)
            and (since is None or e.timestamp >= since)
        ]
        if limit is not None:
            out = out[:limit]
        return tuple(out)


class _FakePerformanceTracker:
    def __init__(self, metrics: list[TaskMetricRecord]) -> None:
        self._metrics = metrics

    def get_task_metrics(
        self,
        *,
        agent_id: str | None,
        since: datetime,
        until: datetime,
    ) -> tuple[TaskMetricRecord, ...]:
        return tuple(
            m
            for m in self._metrics
            if (agent_id is None or str(m.agent_id) == agent_id)
            and since <= m.completed_at <= until
        )


class _FakeCostTracker:
    def __init__(self, records: list[CostRecord]) -> None:
        self._records = records

    async def get_records(
        self,
        *,
        agent_id: str | None,
        start: datetime,
        end: datetime,
    ) -> tuple[CostRecord, ...]:
        return tuple(
            r
            for r in self._records
            if (agent_id is None or str(r.agent_id) == agent_id)
            and start <= r.timestamp <= end
        )


class _FakeToolTracker:
    def __init__(self, records: list[ToolInvocationRecord]) -> None:
        self._records = records

    async def get_records(
        self,
        *,
        agent_id: str | None,
        start: datetime,
        end: datetime,
    ) -> tuple[ToolInvocationRecord, ...]:
        return tuple(
            r
            for r in self._records
            if (agent_id is None or str(r.agent_id) == agent_id)
            and start <= r.timestamp <= end
        )


class _FakeDelegationStore:
    def __init__(
        self,
        sent: list[DelegationRecord] | None = None,
        received: list[DelegationRecord] | None = None,
    ) -> None:
        self._sent = sent or []
        self._received = received or []

    async def get_records_as_delegator(
        self,
        agent_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[DelegationRecord, ...]:
        return tuple(self._sent)

    async def get_records_as_delegatee(
        self,
        agent_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[DelegationRecord, ...]:
        return tuple(self._received)


class TestGetAgentActivity:
    """Merge + pagination + optional sources."""

    async def test_merges_required_sources(self) -> None:
        service = ActivityFeedService(
            performance_tracker=_FakePerformanceTracker(  # type: ignore[arg-type]
                [_task_metric(offset_minutes=30)],
            ),
            lifecycle_repo=_FakeLifecycleRepo(  # type: ignore[arg-type]
                [_lifecycle(offset_minutes=60)],
            ),
        )

        page, total = await service.get_agent_activity(
            NotBlankStr(_AGENT_ID),
            offset=0,
            limit=50,
        )

        # Lifecycle + task_started + task_completed = 3 events.
        assert total == 3
        assert len(page) == 3
        event_types = {e.event_type for e in page}
        assert ActivityEventType.HIRED in event_types
        assert ActivityEventType.TASK_COMPLETED in event_types
        assert ActivityEventType.TASK_STARTED in event_types

    async def test_includes_optional_sources_when_present(self) -> None:
        cost_fake = _FakeCostTracker([_cost_record(offset_minutes=10)])
        tool_fake = _FakeToolTracker([_tool_record(offset_minutes=20)])
        del_fake = _FakeDelegationStore(
            sent=[_delegation(offset_minutes=5, delegator_first=True)],
        )
        service = ActivityFeedService(
            performance_tracker=_FakePerformanceTracker([]),  # type: ignore[arg-type]
            lifecycle_repo=_FakeLifecycleRepo([]),  # type: ignore[arg-type]
            cost_tracker=cost_fake,  # type: ignore[arg-type]
            tool_invocation_tracker=tool_fake,  # type: ignore[arg-type]
            delegation_store=del_fake,  # type: ignore[arg-type]
        )

        page, total = await service.get_agent_activity(
            NotBlankStr(_AGENT_ID),
            offset=0,
            limit=50,
        )

        types = {e.event_type for e in page}
        assert total == 3, f"total={total}, types={types}"
        assert ActivityEventType.COST_INCURRED in types
        assert ActivityEventType.TOOL_USED in types
        assert ActivityEventType.DELEGATION_SENT in types

    async def test_paginates_newest_first(self) -> None:
        events = [
            _lifecycle(offset_minutes=m, event_id=f"evt-{m}")
            for m in (5, 10, 15, 20, 25)
        ]
        service = ActivityFeedService(
            performance_tracker=_FakePerformanceTracker([]),  # type: ignore[arg-type]
            lifecycle_repo=_FakeLifecycleRepo(events),  # type: ignore[arg-type]
        )

        page, total = await service.get_agent_activity(
            NotBlankStr(_AGENT_ID),
            offset=1,
            limit=2,
        )

        assert total == 5
        assert len(page) == 2
        # Events are newest-first; slice is contiguous in descending
        # timestamp order.
        assert page[0].timestamp > page[1].timestamp

    async def test_window_filters_old_events(self) -> None:
        # 10h old vs 200h old -- window 24h should drop the latter.
        events = [
            _lifecycle(offset_minutes=10 * 60, event_id="recent"),
            _lifecycle(
                event_type=LifecycleEventType.PROMOTED,
                offset_minutes=200 * 60,
                event_id="ancient",
            ),
        ]
        service = ActivityFeedService(
            performance_tracker=_FakePerformanceTracker([]),  # type: ignore[arg-type]
            lifecycle_repo=_FakeLifecycleRepo(events),  # type: ignore[arg-type]
        )

        page, total = await service.get_agent_activity(
            NotBlankStr(_AGENT_ID),
            offset=0,
            limit=50,
            window_hours=24,
        )

        assert total == 1
        assert page[0].event_type == ActivityEventType.HIRED

    async def test_no_sources_returns_empty(self) -> None:
        service = ActivityFeedService(
            performance_tracker=_FakePerformanceTracker([]),  # type: ignore[arg-type]
            lifecycle_repo=_FakeLifecycleRepo([]),  # type: ignore[arg-type]
        )

        page, total = await service.get_agent_activity(
            NotBlankStr(_AGENT_ID),
            offset=0,
            limit=50,
        )

        assert total == 0
        assert page == ()
