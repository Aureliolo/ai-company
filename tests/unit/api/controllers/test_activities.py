"""Tests for org-wide activity feed endpoint."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.core.enums import Complexity, TaskType
from synthorg.hr.enums import LifecycleEventType
from synthorg.hr.models import AgentLifecycleEvent
from synthorg.hr.performance.models import TaskMetricRecord
from synthorg.hr.performance.tracker import PerformanceTracker
from tests.unit.api.conftest import FakePersistenceBackend

_NOW = datetime.now(UTC)
_AGENT_ID = "00000000-0000-0000-0000-000000000aaa"


def _make_lifecycle_event(
    *,
    agent_id: str = _AGENT_ID,
    agent_name: str = "alice",
    event_type: LifecycleEventType = LifecycleEventType.HIRED,
    timestamp: datetime | None = None,
    details: str = "test event",
) -> AgentLifecycleEvent:
    return AgentLifecycleEvent(
        agent_id=agent_id,
        agent_name=agent_name,
        event_type=event_type,
        timestamp=timestamp or _NOW,
        initiated_by="system",
        details=details,
    )


def _make_task_metric(
    *,
    agent_id: str = _AGENT_ID,
    completed_at: datetime | None = None,
    is_success: bool = True,
) -> TaskMetricRecord:
    return TaskMetricRecord(
        agent_id=agent_id,
        task_id="task-001",
        task_type=TaskType.DEVELOPMENT,
        completed_at=completed_at or _NOW,
        is_success=is_success,
        duration_seconds=10.0,
        cost_usd=0.01,
        turns_used=2,
        tokens_used=150,
        complexity=Complexity.SIMPLE,
    )


@pytest.mark.unit
class TestActivityFeed:
    def test_empty_feed(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/activities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    def test_auth_required(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get(
            "/api/v1/activities",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401

    async def test_feed_with_lifecycle_events(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
    ) -> None:
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                timestamp=_NOW - timedelta(hours=1),
                event_type=LifecycleEventType.HIRED,
            ),
        )
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                timestamp=_NOW - timedelta(hours=2),
                event_type=LifecycleEventType.ONBOARDED,
            ),
        )
        resp = test_client.get("/api/v1/activities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 2
        # Most recent first
        assert body["data"][0]["event_type"] == "hired"
        assert body["data"][1]["event_type"] == "onboarded"

    async def test_feed_with_task_metrics(
        self,
        test_client: TestClient[Any],
        performance_tracker: PerformanceTracker,
    ) -> None:
        await performance_tracker.record_task_metric(
            _make_task_metric(completed_at=_NOW - timedelta(hours=1)),
        )
        resp = test_client.get("/api/v1/activities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["event_type"] == "task_completed"

    async def test_filter_by_type(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        performance_tracker: PerformanceTracker,
    ) -> None:
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                timestamp=_NOW - timedelta(hours=1),
                event_type=LifecycleEventType.HIRED,
            ),
        )
        await performance_tracker.record_task_metric(
            _make_task_metric(completed_at=_NOW - timedelta(hours=2)),
        )
        resp = test_client.get(
            "/api/v1/activities",
            params={"type": "task_completed"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["event_type"] == "task_completed"

    async def test_filter_by_agent_id(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
    ) -> None:
        other_id = "00000000-0000-0000-0000-000000000bbb"
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                agent_id=_AGENT_ID,
                timestamp=_NOW - timedelta(hours=1),
            ),
        )
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                agent_id=other_id,
                agent_name="bob",
                timestamp=_NOW - timedelta(hours=2),
            ),
        )
        resp = test_client.get(
            "/api/v1/activities",
            params={"agent_id": _AGENT_ID},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 1

    def test_last_n_hours_default(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Default last_n_hours is 24."""
        resp = test_client.get("/api/v1/activities")
        assert resp.status_code == 200

    def test_last_n_hours_valid_values(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """48 and 168 are valid values."""
        for hours in (24, 48, 168):
            resp = test_client.get(
                "/api/v1/activities",
                params={"last_n_hours": hours},
            )
            assert resp.status_code == 200

    def test_last_n_hours_invalid(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Invalid last_n_hours values should return 400."""
        resp = test_client.get(
            "/api/v1/activities",
            params={"last_n_hours": 12},
        )
        assert resp.status_code == 400

    def test_pagination(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/activities",
            params={"offset": 0, "limit": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "pagination" in body
        assert body["pagination"]["offset"] == 0
        assert body["pagination"]["limit"] == 10
