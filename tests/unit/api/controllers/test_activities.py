"""Tests for org-wide activity feed endpoint."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.config.schema import RootConfig
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

    @pytest.mark.parametrize("hours", [24, 48, 168])
    def test_last_n_hours_valid_values(
        self,
        test_client: TestClient[Any],
        hours: int,
    ) -> None:
        """24, 48, and 168 are valid values."""
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

    async def test_graceful_degradation_no_performance_tracker(
        self,
        fake_persistence: FakePersistenceBackend,
    ) -> None:
        """Endpoint still returns lifecycle events when perf tracker fails."""
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                timestamp=_NOW - timedelta(hours=1),
            ),
        )

        # Build a tracker whose get_task_metrics always raises
        from synthorg.hr.performance.tracker import PerformanceTracker

        tracker = PerformanceTracker()

        def _raise(**_kwargs: object) -> None:
            msg = "simulated failure"
            raise RuntimeError(msg)

        tracker.get_task_metrics = _raise  # type: ignore[assignment]

        from synthorg.api.app import create_app
        from synthorg.api.auth.service import AuthService
        from synthorg.budget.tracker import CostTracker
        from synthorg.settings.registry import get_registry
        from synthorg.settings.service import SettingsService
        from tests.unit.api.conftest import (
            FakeMessageBus,
            _make_test_auth_service,
            _seed_test_users,
            make_auth_headers,
        )

        config = RootConfig(company_name="test")
        auth_service: AuthService = _make_test_auth_service()
        bus = FakeMessageBus()
        await bus.start()
        _seed_test_users(fake_persistence, auth_service)
        settings_service = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
        )
        app = create_app(
            config=config,
            persistence=fake_persistence,
            message_bus=bus,
            cost_tracker=CostTracker(),
            auth_service=auth_service,
            settings_service=settings_service,
            performance_tracker=tracker,
        )

        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/activities",
                headers=make_auth_headers("ceo"),
            )
            assert resp.status_code == 200
            body = resp.json()
            # Should still return lifecycle events
            assert body["pagination"]["total"] >= 1
