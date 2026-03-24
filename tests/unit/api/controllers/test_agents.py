"""Tests for agent controller."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from litestar.testing import TestClient

from synthorg.config.schema import AgentConfig, RootConfig
from synthorg.core.agent import AgentIdentity, ModelConfig
from synthorg.core.enums import Complexity, TaskType
from synthorg.hr.enums import LifecycleEventType, TrendDirection
from synthorg.hr.models import AgentLifecycleEvent
from synthorg.hr.performance.models import TaskMetricRecord
from synthorg.hr.performance.tracker import PerformanceTracker
from synthorg.hr.registry import AgentRegistryService
from synthorg.settings.registry import get_registry
from synthorg.settings.service import SettingsService
from tests.unit.api.conftest import (
    FakeMessageBus,
    FakePersistenceBackend,
    make_auth_headers,
)


@pytest.mark.unit
class TestAgentController:
    def test_list_agents_empty(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    def test_list_agents_with_data(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        from synthorg.api.app import create_app
        from synthorg.api.auth.service import AuthService
        from synthorg.budget.tracker import CostTracker
        from tests.unit.api.conftest import _make_test_auth_service, _seed_test_users

        config = RootConfig(
            company_name="test",
            agents=(
                AgentConfig(
                    name="alice",
                    role="developer",
                    department="eng",
                ),
            ),
        )
        auth_service: AuthService = _make_test_auth_service()
        _seed_test_users(fake_persistence, auth_service)
        settings_service = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
        )
        app = create_app(
            config=config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            cost_tracker=CostTracker(),
            auth_service=auth_service,
            settings_service=settings_service,
        )
        with TestClient(app) as client:
            client.headers.update(make_auth_headers("observer"))
            resp = client.get("/api/v1/agents")
            body = resp.json()
            assert body["pagination"]["total"] == 1
            assert body["data"][0]["name"] == "alice"

    def test_get_agent_not_found(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/agents/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["success"] is False

    def test_oversized_agent_name_rejected(self, test_client: TestClient[Any]) -> None:
        long_name = "x" * 129
        resp = test_client.get(f"/api/v1/agents/{long_name}")
        assert resp.status_code == 400


@pytest.mark.integration
class TestAgentControllerDbOverride:
    """Test that DB-stored settings override YAML agents."""

    async def test_db_agents_override_config(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        from synthorg.api.app import create_app
        from synthorg.api.auth.service import AuthService
        from synthorg.budget.tracker import CostTracker
        from tests.unit.api.conftest import _make_test_auth_service, _seed_test_users

        config = RootConfig(
            company_name="test",
            agents=(AgentConfig(name="yaml-agent", role="dev", department="eng"),),
        )
        auth_service: AuthService = _make_test_auth_service()
        _seed_test_users(fake_persistence, auth_service)
        settings_service = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
        )

        db_agents = [
            {"name": "db-agent-1", "role": "qa", "department": "eng"},
            {"name": "db-agent-2", "role": "pm", "department": "ops"},
        ]
        await settings_service.set("company", "agents", json.dumps(db_agents))

        app = create_app(
            config=config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            cost_tracker=CostTracker(),
            auth_service=auth_service,
            settings_service=settings_service,
        )
        with TestClient(app) as client:
            client.headers.update(make_auth_headers("observer"))
            resp = client.get("/api/v1/agents")
            assert resp.status_code == 200
            body = resp.json()
            assert body["pagination"]["total"] == 2
            names = {a["name"] for a in body["data"]}
            assert names == {"db-agent-1", "db-agent-2"}

            detail_resp = client.get("/api/v1/agents/db-agent-1")
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["data"]["name"] == "db-agent-1"


# ── Helpers for performance/activity/history tests ────────────
# Note: Similar factories exist in tests/unit/hr/test_activity.py with
# different defaults (simple string IDs vs UUID format) because controller
# tests need UUID-valid agent_id for AgentIdentity construction.


_NOW = datetime(2026, 3, 24, 12, 0, 0, tzinfo=UTC)
_AGENT_NAME = "test-agent"
_AGENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_identity(
    *,
    agent_id: str = _AGENT_ID,
    name: str = _AGENT_NAME,
) -> AgentIdentity:
    return AgentIdentity(
        id=UUID(agent_id),
        name=name,
        role="developer",
        department="eng",
        model=ModelConfig(provider="test-provider", model_id="test-small-001"),
        hiring_date=_NOW.date(),
    )


def _make_task_metric(  # noqa: PLR0913
    *,
    completed_at: datetime = _NOW,
    agent_id: str = _AGENT_ID,
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


def _make_lifecycle_event(  # noqa: PLR0913
    *,
    event_type: LifecycleEventType = LifecycleEventType.HIRED,
    timestamp: datetime = _NOW,
    agent_id: str = _AGENT_ID,
    agent_name: str = _AGENT_NAME,
    details: str = "",
    initiated_by: str = "system",
) -> AgentLifecycleEvent:
    return AgentLifecycleEvent(
        agent_id=agent_id,
        agent_name=agent_name,
        event_type=event_type,
        timestamp=timestamp,
        initiated_by=initiated_by,
        details=details,
    )


# ── Performance endpoint tests ────────────────────────────────


@pytest.mark.unit
class TestAgentPerformance:
    async def test_performance_returns_summary(
        self,
        test_client: TestClient[Any],
        performance_tracker: PerformanceTracker,
        agent_registry: AgentRegistryService,
    ) -> None:
        identity = _make_identity()
        await agent_registry.register(identity)
        for i in range(3):
            await performance_tracker.record_task_metric(
                _make_task_metric(
                    completed_at=_NOW - timedelta(days=i),
                    task_id=f"task-{i}",
                ),
            )

        resp = test_client.get(f"/api/v1/agents/{_AGENT_NAME}/performance")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agent_name"] == _AGENT_NAME
        assert data["trend_direction"] in {d.value for d in TrendDirection}
        assert isinstance(data["windows"], list)
        assert len(data["windows"]) >= 1
        assert isinstance(data["trends"], list)

    async def test_performance_empty_metrics(
        self,
        test_client: TestClient[Any],
        agent_registry: AgentRegistryService,
    ) -> None:
        await agent_registry.register(_make_identity())

        resp = test_client.get(f"/api/v1/agents/{_AGENT_NAME}/performance")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tasks_completed_total"] == 0
        assert data["tasks_completed_7d"] == 0
        assert data["tasks_completed_30d"] == 0
        assert data["success_rate_percent"] is None
        assert data["quality_score"] is None
        assert data["collaboration_score"] is None

    def test_performance_agent_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get("/api/v1/agents/nonexistent/performance")
        assert resp.status_code == 404
        assert resp.json()["success"] is False

    def test_performance_returns_503_without_registry(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        """Agent registry not configured returns 503."""
        from synthorg.api.app import create_app
        from synthorg.budget.tracker import CostTracker
        from tests.unit.api.conftest import _make_test_auth_service, _seed_test_users

        config = RootConfig(company_name="test")
        auth_svc = _make_test_auth_service()
        _seed_test_users(fake_persistence, auth_svc)
        settings_svc = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
        )
        app = create_app(
            config=config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            cost_tracker=CostTracker(),
            auth_service=auth_svc,
            settings_service=settings_svc,
        )
        with TestClient(app) as client:
            client.headers.update(make_auth_headers("ceo"))
            resp = client.get(f"/api/v1/agents/{_AGENT_NAME}/performance")
            assert resp.status_code == 503
            assert resp.json()["success"] is False

    def test_activity_returns_503_without_registry(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        """Activity endpoint returns 503 when agent registry not configured."""
        from synthorg.api.app import create_app
        from synthorg.budget.tracker import CostTracker
        from tests.unit.api.conftest import _make_test_auth_service, _seed_test_users

        config = RootConfig(company_name="test")
        auth_svc = _make_test_auth_service()
        _seed_test_users(fake_persistence, auth_svc)
        settings_svc = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
        )
        app = create_app(
            config=config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            cost_tracker=CostTracker(),
            auth_service=auth_svc,
            settings_service=settings_svc,
        )
        with TestClient(app) as client:
            client.headers.update(make_auth_headers("ceo"))
            resp = client.get(f"/api/v1/agents/{_AGENT_NAME}/activity")
            assert resp.status_code == 503
            assert resp.json()["success"] is False

    def test_history_returns_503_without_registry(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        """History endpoint returns 503 when agent registry not configured."""
        from synthorg.api.app import create_app
        from synthorg.budget.tracker import CostTracker
        from tests.unit.api.conftest import _make_test_auth_service, _seed_test_users

        config = RootConfig(company_name="test")
        auth_svc = _make_test_auth_service()
        _seed_test_users(fake_persistence, auth_svc)
        settings_svc = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
        )
        app = create_app(
            config=config,
            persistence=fake_persistence,
            message_bus=fake_message_bus,
            cost_tracker=CostTracker(),
            auth_service=auth_svc,
            settings_service=settings_svc,
        )
        with TestClient(app) as client:
            client.headers.update(make_auth_headers("ceo"))
            resp = client.get(f"/api/v1/agents/{_AGENT_NAME}/history")
            assert resp.status_code == 503
            assert resp.json()["success"] is False


# ── Activity endpoint tests ───────────────────────────────────


@pytest.mark.unit
class TestAgentActivity:
    async def test_activity_returns_merged_timeline(
        self,
        test_client: TestClient[Any],
        performance_tracker: PerformanceTracker,
        agent_registry: AgentRegistryService,
        fake_persistence: FakePersistenceBackend,
    ) -> None:
        identity = _make_identity()
        await agent_registry.register(identity)

        # Seed lifecycle event
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                event_type=LifecycleEventType.HIRED,
                timestamp=_NOW - timedelta(days=10),
                details="Hired as developer",
            ),
        )

        # Seed task metric
        await performance_tracker.record_task_metric(
            _make_task_metric(
                completed_at=_NOW - timedelta(days=5),
                task_id="task-100",
            ),
        )

        resp = test_client.get(f"/api/v1/agents/{_AGENT_NAME}/activity")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 2
        events = body["data"]
        # Most recent first
        assert events[0]["event_type"] == "task_completed"
        assert "task-100" in events[0]["related_ids"]["task_id"]
        assert "succeeded" in events[0]["description"]
        assert events[1]["event_type"] == "hired"
        assert events[1]["description"] == "Hired as developer"

    async def test_activity_pagination(
        self,
        test_client: TestClient[Any],
        performance_tracker: PerformanceTracker,
        agent_registry: AgentRegistryService,
    ) -> None:
        await agent_registry.register(_make_identity())
        for i in range(5):
            await performance_tracker.record_task_metric(
                _make_task_metric(
                    completed_at=_NOW - timedelta(hours=i),
                    task_id=f"task-{i}",
                ),
            )

        resp = test_client.get(
            f"/api/v1/agents/{_AGENT_NAME}/activity",
            params={"offset": 1, "limit": 2},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 5
        assert body["pagination"]["offset"] == 1
        assert body["pagination"]["limit"] == 2
        assert len(body["data"]) == 2

    async def test_activity_empty(
        self,
        test_client: TestClient[Any],
        agent_registry: AgentRegistryService,
    ) -> None:
        await agent_registry.register(_make_identity())

        resp = test_client.get(f"/api/v1/agents/{_AGENT_NAME}/activity")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0
        assert body["data"] == []

    def test_activity_agent_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get("/api/v1/agents/nonexistent/activity")
        assert resp.status_code == 404


# ── History endpoint tests ────────────────────────────────────


@pytest.mark.unit
class TestAgentHistory:
    async def test_history_returns_career_events(
        self,
        test_client: TestClient[Any],
        agent_registry: AgentRegistryService,
        fake_persistence: FakePersistenceBackend,
    ) -> None:
        await agent_registry.register(_make_identity())

        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                event_type=LifecycleEventType.HIRED,
                timestamp=_NOW - timedelta(days=30),
                details="Hired as developer",
            ),
        )
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                event_type=LifecycleEventType.STATUS_CHANGED,
                timestamp=_NOW - timedelta(days=20),
                details="Status changed to idle",
            ),
        )
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                event_type=LifecycleEventType.PROMOTED,
                timestamp=_NOW - timedelta(days=10),
                details="Promoted to senior",
            ),
        )

        resp = test_client.get(f"/api/v1/agents/{_AGENT_NAME}/history")

        assert resp.status_code == 200
        data = resp.json()["data"]
        # STATUS_CHANGED is filtered out; only HIRED and PROMOTED remain
        assert len(data) == 2
        assert data[0]["event_type"] == "hired"
        assert data[1]["event_type"] == "promoted"

    async def test_history_chronological_order(
        self,
        test_client: TestClient[Any],
        agent_registry: AgentRegistryService,
        fake_persistence: FakePersistenceBackend,
    ) -> None:
        await agent_registry.register(_make_identity())

        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                event_type=LifecycleEventType.PROMOTED,
                timestamp=_NOW - timedelta(days=1),
            ),
        )
        await fake_persistence.lifecycle_events.save(
            _make_lifecycle_event(
                event_type=LifecycleEventType.HIRED,
                timestamp=_NOW - timedelta(days=30),
            ),
        )

        resp = test_client.get(f"/api/v1/agents/{_AGENT_NAME}/history")

        assert resp.status_code == 200
        data = resp.json()["data"]
        # Ascending order (hired first, then promoted)
        assert data[0]["event_type"] == "hired"
        assert data[1]["event_type"] == "promoted"

    async def test_history_empty(
        self,
        test_client: TestClient[Any],
        agent_registry: AgentRegistryService,
    ) -> None:
        await agent_registry.register(_make_identity())

        resp = test_client.get(f"/api/v1/agents/{_AGENT_NAME}/history")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == []

    def test_history_agent_not_found(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get("/api/v1/agents/nonexistent/history")
        assert resp.status_code == 404
