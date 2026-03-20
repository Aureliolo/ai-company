"""Tests for agent controller."""

import json
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.config.schema import AgentConfig, RootConfig
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
