"""Tests for analytics controller."""

import json
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.config.schema import RootConfig
from synthorg.core.enums import TaskStatus
from synthorg.settings.registry import get_registry
from synthorg.settings.service import SettingsService
from tests.unit.api.conftest import (
    FakeMessageBus,
    FakePersistenceBackend,
    make_auth_headers,
)

_HEADERS = make_auth_headers("ceo")


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestAnalyticsController:
    def test_overview_empty(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/analytics/overview", headers=_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["total_tasks"] == 0
        expected_statuses = {s.value: 0 for s in TaskStatus}
        assert data["tasks_by_status"] == expected_statuses
        assert data["total_agents"] == 0
        assert data["total_cost_usd"] == 0.0

    def test_overview_requires_read_access(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get(
            "/api/v1/analytics/overview",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.timeout(30)
class TestAnalyticsControllerDbOverride:
    """Test that DB-stored agents affect analytics agent count."""

    async def test_db_agents_count_in_overview(
        self,
        fake_persistence: FakePersistenceBackend,
        fake_message_bus: FakeMessageBus,
    ) -> None:
        from synthorg.api.app import create_app
        from synthorg.api.auth.service import AuthService
        from synthorg.budget.tracker import CostTracker
        from tests.unit.api.conftest import _make_test_auth_service, _seed_test_users

        config = RootConfig(company_name="test")
        auth_service: AuthService = _make_test_auth_service()
        _seed_test_users(fake_persistence, auth_service)
        settings_service = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
        )

        db_agents = [
            {"name": "a1", "role": "dev", "department": "eng"},
            {"name": "a2", "role": "qa", "department": "eng"},
            {"name": "a3", "role": "pm", "department": "ops"},
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
            client.headers.update(make_auth_headers("ceo"))
            resp = client.get("/api/v1/analytics/overview")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["data"]["total_agents"] == 3
            assert body["data"]["total_tasks"] == 0
            assert body["data"]["total_cost_usd"] == 0.0
