"""Tests for provider controller."""

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from litestar.testing import TestClient

from synthorg.config.schema import ProviderModelConfig
from synthorg.providers.errors import ProviderNotFoundError
from tests.unit.api.conftest import make_auth_headers

if TYPE_CHECKING:
    from synthorg.api.controllers.providers import ProviderController


@pytest.mark.unit
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

    def test_oversized_provider_name_rejected(
        self, test_client: TestClient[Any]
    ) -> None:
        long_name = "x" * 129
        resp = test_client.get(f"/api/v1/providers/{long_name}")
        assert resp.status_code == 400


@pytest.mark.unit
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
        # oauth_client_id is intentionally non-secret (included for frontend UX)
        assert "client-id" in all_values


@pytest.mark.unit
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
        resp = test_client.post(
            "/api/v1/providers",
            json={
                "name": "test-provider",
                "driver": "litellm",
                "auth_type": "none",
            },
            headers=make_auth_headers("observer"),
        )
        assert resp.status_code == 403

    def test_probe_preset_requires_write_access(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """POST /providers/probe-preset is guarded by write access."""
        resp = test_client.post(
            "/api/v1/providers/probe-preset",
            json={"preset_name": "ollama"},
            headers=make_auth_headers("observer"),
        )
        assert resp.status_code == 403


def _make_provider_state_and_mgmt() -> tuple[MagicMock, AsyncMock]:
    """Create a mock Litestar State with a mock provider management service.

    Returns:
        Tuple of (mock_state, mock_provider_management).
    """
    mgmt = AsyncMock()
    app_state = MagicMock()
    app_state.provider_management = mgmt

    state = MagicMock()
    state.app_state = app_state
    return state, mgmt


def _provider_controller() -> ProviderController:
    """Create a ProviderController instance for testing."""
    from synthorg.api.controllers.providers import ProviderController

    return ProviderController(owner=ProviderController)  # type: ignore[arg-type]


@pytest.mark.unit
class TestDiscoverModelsEndpoint:
    """Tests for POST /providers/{name}/discover-models."""

    async def test_discover_models_success(self) -> None:
        """Successful discovery returns models and provider name."""
        state, mgmt = _make_provider_state_and_mgmt()
        discovered = (
            ProviderModelConfig(id="ollama/test-model-a"),
            ProviderModelConfig(id="ollama/test-model-b"),
        )
        mgmt.discover_models_for_provider = AsyncMock(
            return_value=discovered,
        )

        ctrl = _provider_controller()
        result = await ctrl.discover_models.fn(
            ctrl,
            state=state,
            name="test-provider",
        )

        mgmt.discover_models_for_provider.assert_awaited_once_with(
            "test-provider",
            preset_hint=None,
        )
        assert result.data.provider_name == "test-provider"
        assert result.data.discovered_models == discovered

    async def test_discover_models_not_found(self) -> None:
        """Non-existent provider raises NotFoundError."""
        from synthorg.api.errors import NotFoundError

        state, mgmt = _make_provider_state_and_mgmt()
        mgmt.discover_models_for_provider = AsyncMock(
            side_effect=ProviderNotFoundError("Provider 'nonexistent' not found"),
        )

        ctrl = _provider_controller()
        with pytest.raises(NotFoundError):
            await ctrl.discover_models.fn(
                ctrl,
                state=state,
                name="nonexistent",
            )


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestProbePresetEndpoint:
    """Tests for POST /providers/probe-preset."""

    async def test_unknown_preset_raises_validation_error(self) -> None:
        """Unknown preset name produces a validation error."""
        state, _ = _make_provider_state_and_mgmt()
        from synthorg.api.dto import ProbePresetRequest
        from synthorg.api.errors import ApiValidationError

        ctrl = _provider_controller()
        with pytest.raises(ApiValidationError):
            await ctrl.probe_preset.fn(
                ctrl,
                state=state,
                data=ProbePresetRequest(preset_name="nonexistent-preset"),
            )

    async def test_preset_with_no_candidates_returns_empty(self) -> None:
        """Preset with no candidate URLs returns zero candidates tried."""
        state, _ = _make_provider_state_and_mgmt()
        from synthorg.api.dto import ProbePresetRequest

        ctrl = _provider_controller()
        result = await ctrl.probe_preset.fn(
            ctrl,
            state=state,
            data=ProbePresetRequest(preset_name="openrouter"),
        )
        assert result.data.candidates_tried == 0
        assert result.data.url is None

    async def test_successful_probe_maps_result(self) -> None:
        """Successful probe result is correctly mapped to response DTO."""
        from unittest.mock import patch

        from synthorg.api.dto import ProbePresetRequest
        from synthorg.providers.discovery import ProbeResult

        state, _ = _make_provider_state_and_mgmt()
        ctrl = _provider_controller()
        mock_result = ProbeResult(
            url="http://host.docker.internal:11434",
            model_count=3,
            candidates_tried=1,
        )
        with patch(
            "synthorg.api.controllers.providers.probe_preset_urls",
            AsyncMock(return_value=mock_result),
        ):
            result = await ctrl.probe_preset.fn(
                ctrl,
                state=state,
                data=ProbePresetRequest(preset_name="ollama"),
            )
        assert result.data.url == "http://host.docker.internal:11434"
        assert result.data.model_count == 3
        assert result.data.candidates_tried == 1
