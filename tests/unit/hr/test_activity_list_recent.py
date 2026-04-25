"""Tests for ActivityFeedService.list_recent_activity().

The new entry point is the no-agent-required variant of
``get_agent_activity``. It powers ``synthorg_activities_list``: a feed
that operators query for "recent activity in this project" or
"recent events on this task" without scoping to a single agent.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.budget.currency import DEFAULT_CURRENCY
from synthorg.core.enums import Complexity, TaskType
from synthorg.core.types import NotBlankStr
from synthorg.hr.activity_service import ActivityFeedService
from synthorg.hr.performance.models import TaskMetricRecord


def _now() -> datetime:
    return datetime.now(UTC)


def _make_task_metric(
    *,
    agent_id: str,
    task_id: str,
    completed_at: datetime,
    is_success: bool = True,
) -> TaskMetricRecord:
    return TaskMetricRecord(
        agent_id=NotBlankStr(agent_id),
        task_id=NotBlankStr(task_id),
        task_type=TaskType.REVIEW,
        completed_at=completed_at,
        is_success=is_success,
        duration_seconds=60.0,
        cost=0.5,
        currency=DEFAULT_CURRENCY,
        turns_used=2,
        tokens_used=100,
        complexity=Complexity.MEDIUM,
    )


@pytest.fixture
def lifecycle_repo() -> Any:
    repo = AsyncMock()
    repo.list_events.return_value = ()
    return repo


@pytest.fixture
def performance_tracker() -> Any:
    tracker = MagicMock()
    tracker.get_task_metrics = MagicMock(return_value=())
    return tracker


@pytest.fixture
def service(
    lifecycle_repo: Any,
    performance_tracker: Any,
) -> ActivityFeedService:
    return ActivityFeedService(
        performance_tracker=performance_tracker,
        lifecycle_repo=lifecycle_repo,
    )


class TestListRecentActivity:
    """list_recent_activity merges sources with optional filters."""

    @pytest.mark.unit
    async def test_unfiltered_happy_path(
        self,
        service: ActivityFeedService,
        performance_tracker: Any,
    ) -> None:
        completed_at = _now() - timedelta(minutes=5)
        performance_tracker.get_task_metrics.return_value = (
            _make_task_metric(
                agent_id="agent-1",
                task_id="task-1",
                completed_at=completed_at,
            ),
            _make_task_metric(
                agent_id="agent-2",
                task_id="task-2",
                completed_at=completed_at,
            ),
        )

        page, total = await service.list_recent_activity(offset=0, limit=10)
        # Two completed task metrics produce two events (no started_at).
        assert total == 2
        assert len(page) == 2
        assert all("task_id" in event.related_ids for event in page)

    @pytest.mark.unit
    async def test_task_id_filter(
        self,
        service: ActivityFeedService,
        performance_tracker: Any,
    ) -> None:
        completed_at = _now() - timedelta(minutes=5)
        performance_tracker.get_task_metrics.return_value = (
            _make_task_metric(
                agent_id="agent-1",
                task_id="task-1",
                completed_at=completed_at,
            ),
            _make_task_metric(
                agent_id="agent-2",
                task_id="task-2",
                completed_at=completed_at,
            ),
            _make_task_metric(
                agent_id="agent-3",
                task_id="task-1",
                completed_at=completed_at - timedelta(seconds=10),
            ),
        )
        page, total = await service.list_recent_activity(
            task_id="task-1",
            offset=0,
            limit=10,
        )
        assert total == 2
        for event in page:
            assert event.related_ids.get("task_id") == "task-1"

    @pytest.mark.unit
    async def test_pagination(
        self,
        service: ActivityFeedService,
        performance_tracker: Any,
    ) -> None:
        completed_at = _now() - timedelta(minutes=5)
        performance_tracker.get_task_metrics.return_value = tuple(
            _make_task_metric(
                agent_id=f"agent-{i}",
                task_id=f"task-{i}",
                completed_at=completed_at - timedelta(seconds=i),
            )
            for i in range(5)
        )
        page, total = await service.list_recent_activity(offset=2, limit=2)
        assert total == 5
        assert len(page) == 2

    @pytest.mark.unit
    async def test_invalid_offset_rejected(
        self,
        service: ActivityFeedService,
    ) -> None:
        with pytest.raises(ValueError, match="offset"):
            await service.list_recent_activity(offset=-1, limit=10)

    @pytest.mark.unit
    async def test_invalid_window_rejected(
        self,
        service: ActivityFeedService,
    ) -> None:
        with pytest.raises(ValueError, match="window_hours"):
            await service.list_recent_activity(
                offset=0,
                limit=10,
                window_hours=10_000,
            )

    @pytest.mark.unit
    async def test_isolated_source_failure_does_not_abort(
        self,
        lifecycle_repo: Any,
        performance_tracker: Any,
    ) -> None:
        """A failing optional source must not abort the merge."""

        class _BoomCostTracker:
            async def get_records(
                self,
                **_: Any,
            ) -> tuple[Any, ...]:
                msg = "cost tracker explodes"
                raise RuntimeError(msg)

        completed_at = _now() - timedelta(minutes=5)
        performance_tracker.get_task_metrics.return_value = (
            _make_task_metric(
                agent_id="agent-1",
                task_id="task-1",
                completed_at=completed_at,
            ),
        )
        service = ActivityFeedService(
            performance_tracker=performance_tracker,
            lifecycle_repo=lifecycle_repo,
            cost_tracker=_BoomCostTracker(),  # type: ignore[arg-type]
        )

        page, total = await service.list_recent_activity(offset=0, limit=10)
        # Cost source failed but task metric still produced an event.
        assert total == 1
        assert len(page) == 1
