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
class TestProviderResponseSecurity:
    def test_to_provider_response_strips_secrets(self) -> None:
        from synthorg.api.dto import to_provider_response
        from synthorg.config.schema import ProviderConfig

        provider = ProviderConfig(
            driver="test-driver",
            api_key="test-placeholder",
        )
        response = to_provider_response(provider)
        assert response.has_api_key is True
        # The response should not have api_key attribute at all
        assert (
            not hasattr(response, "api_key") or "api_key" not in response.model_fields
        )

    def test_response_has_credential_indicators(self) -> None:
        from synthorg.api.dto import to_provider_response
        from synthorg.config.schema import ProviderConfig
        from synthorg.providers.enums import AuthType

        provider = ProviderConfig(
            driver="test-driver",
            auth_type=AuthType.CUSTOM_HEADER,
            custom_header_name="X-Auth",
            custom_header_value="secret",
        )
        response = to_provider_response(provider)
        assert response.has_custom_header is True
        assert response.has_api_key is False
        assert response.has_oauth_credentials is False

    def test_response_never_contains_secrets(self) -> None:
        from synthorg.api.dto import to_provider_response
        from synthorg.config.schema import ProviderConfig
        from synthorg.providers.enums import AuthType

        provider = ProviderConfig(
            driver="test-driver",
            auth_type=AuthType.OAUTH,
            api_key="secret-key",
            oauth_token_url="https://auth.example.com/token",
            oauth_client_id="client-id",
            oauth_client_secret="secret-value",
        )
        response = to_provider_response(provider)
        dumped = response.model_dump()
        all_values = json.dumps(dumped)
        assert "secret-key" not in all_values
        assert "secret-value" not in all_values
        assert "client-id" not in all_values


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestProviderCrudEndpoints:
    def test_get_presets_returns_all(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get("/api/v1/providers/presets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) >= 4

    def test_write_endpoints_require_write_access(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.post(
            "/api/v1/providers",
            json={
                "name": "test-provider",
                "driver": "litellm",
                "auth_type": "none",
            },
        )
        assert resp.status_code == 403


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
            # Response should use ProviderResponse format
            assert body["data"]["db-provider"]["driver"] == "litellm"
            assert body["data"]["db-provider"]["auth_type"] == "api_key"

            detail_resp = client.get("/api/v1/providers/db-provider")
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["data"]["driver"] == "litellm"
            assert "api_key" not in detail["data"]
