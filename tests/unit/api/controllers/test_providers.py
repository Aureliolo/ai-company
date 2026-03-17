"""Tests for provider controller."""

import json
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.config.schema import RootConfig
from synthorg.settings.registry import get_registry
from synthorg.settings.service import SettingsService
from tests.unit.api.conftest import (
    FakeMessageBus,
    FakePersistenceBackend,
    make_auth_headers,
)


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestProviderController:
    def test_list_providers_empty(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == {}

    def test_get_provider_not_found(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/providers/nonexistent")
        assert resp.status_code == 404

    def test_list_models_not_found(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/providers/nonexistent/models")
        assert resp.status_code == 404


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestProviderApiKeySecurity:
    def test_provider_api_key_stripped(self) -> None:
        """Verify api_key is stripped from provider responses."""
        from synthorg.api.controllers.providers import _safe_provider
        from synthorg.config.schema import ProviderConfig

        provider = ProviderConfig(
            driver="test-driver",
            api_key="test-placeholder",
        )
        safe = _safe_provider(provider)
        assert safe.api_key is None


@pytest.mark.integration
@pytest.mark.timeout(30)
class TestProviderControllerDbOverride:
    """Test that DB-stored settings override YAML providers."""

    async def test_db_providers_override_config(
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
        from cryptography.fernet import Fernet

        from synthorg.settings.encryption import SettingsEncryptor

        encryptor = SettingsEncryptor(Fernet.generate_key())
        settings_service = SettingsService(
            repository=fake_persistence.settings,
            registry=get_registry(),
            config=config,
            encryptor=encryptor,
        )

        db_providers = {
            "db-provider": {"driver": "litellm"},
        }
        await settings_service.set("providers", "configs", json.dumps(db_providers))

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
            resp = client.get("/api/v1/providers")
            assert resp.status_code == 200
            body = resp.json()
            assert "db-provider" in body["data"]
            # api_key should be stripped
            assert body["data"]["db-provider"].get("api_key") is None

            detail_resp = client.get("/api/v1/providers/db-provider")
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["data"]["driver"] == "litellm"
            assert detail["data"].get("api_key") is None
