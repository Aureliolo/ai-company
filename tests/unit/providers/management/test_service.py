"""Tests for ProviderManagementService."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synthorg.api.dto import (
    CreateFromPresetRequest,
    CreateProviderRequest,
    UpdateProviderRequest,
)
from synthorg.api.dto import TestConnectionRequest as ConnTestRequest
from synthorg.api.state import AppState
from synthorg.config.schema import ProviderModelConfig, RootConfig
from synthorg.providers.enums import AuthType
from synthorg.providers.errors import (
    ProviderAlreadyExistsError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from synthorg.providers.management.service import ProviderManagementService
from synthorg.settings.encryption import SettingsEncryptor
from synthorg.settings.registry import get_registry
from synthorg.settings.service import SettingsService
from tests.unit.api.conftest import FakeMessageBus, FakePersistenceBackend


@pytest.fixture
async def fake_persistence() -> FakePersistenceBackend:
    backend = FakePersistenceBackend()
    await backend.connect()
    return backend


@pytest.fixture
async def fake_message_bus() -> FakeMessageBus:
    bus = FakeMessageBus()
    await bus.start()
    return bus


@pytest.fixture
def root_config() -> RootConfig:
    return RootConfig(company_name="test-company")


@pytest.fixture
def encryptor() -> SettingsEncryptor:
    from cryptography.fernet import Fernet

    return SettingsEncryptor(Fernet.generate_key())


@pytest.fixture
def settings_service(
    fake_persistence: FakePersistenceBackend,
    root_config: RootConfig,
    encryptor: SettingsEncryptor,
) -> SettingsService:
    return SettingsService(
        repository=fake_persistence.settings,
        registry=get_registry(),
        config=root_config,
        encryptor=encryptor,
    )


@pytest.fixture
def app_state(
    root_config: RootConfig,
    fake_persistence: FakePersistenceBackend,
    fake_message_bus: FakeMessageBus,
    settings_service: SettingsService,
) -> AppState:
    from synthorg.api.approval_store import ApprovalStore

    return AppState(
        config=root_config,
        approval_store=ApprovalStore(),
        persistence=fake_persistence,
        message_bus=fake_message_bus,
        settings_service=settings_service,
    )


@pytest.fixture
def service(
    settings_service: SettingsService,
    app_state: AppState,
    root_config: RootConfig,
) -> ProviderManagementService:
    return ProviderManagementService(
        settings_service=settings_service,
        config_resolver=app_state.config_resolver,
        app_state=app_state,
        config=root_config,
    )


def _make_create_request(
    name: str = "test-provider",
    auth_type: AuthType = AuthType.NONE,
    **kwargs: Any,
) -> CreateProviderRequest:
    return CreateProviderRequest(
        name=name,
        driver="litellm",
        auth_type=auth_type,
        models=(
            ProviderModelConfig(
                id="test-model-001",
                alias="medium",
            ),
        ),
        **kwargs,
    )


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestCreateProvider:
    async def test_create_provider_success(
        self,
        service: ProviderManagementService,
    ) -> None:
        request = _make_create_request()
        result = await service.create_provider(request)
        assert result.driver == "litellm"
        assert result.auth_type == AuthType.NONE

    async def test_create_provider_duplicate_name_raises(
        self,
        service: ProviderManagementService,
    ) -> None:
        request = _make_create_request()
        await service.create_provider(request)

        with pytest.raises(ProviderAlreadyExistsError, match="already exists"):
            await service.create_provider(request)

    async def test_create_provider_persists_to_settings(
        self,
        service: ProviderManagementService,
        settings_service: SettingsService,
    ) -> None:
        request = _make_create_request()
        await service.create_provider(request)

        result = await settings_service.get("providers", "configs")
        data = json.loads(result.value)
        assert "test-provider" in data

    async def test_create_provider_rebuilds_registry(
        self,
        service: ProviderManagementService,
        app_state: AppState,
    ) -> None:
        request = _make_create_request()
        await service.create_provider(request)
        assert app_state.has_provider_registry
        assert "test-provider" in app_state.provider_registry

    async def test_create_provider_swaps_app_state(
        self,
        service: ProviderManagementService,
        app_state: AppState,
    ) -> None:
        request = _make_create_request()
        await service.create_provider(request)
        assert app_state.has_model_router


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestUpdateProvider:
    async def test_update_provider_success(
        self,
        service: ProviderManagementService,
    ) -> None:
        await service.create_provider(_make_create_request())
        update = UpdateProviderRequest(
            base_url="http://localhost:9999",
        )
        result = await service.update_provider("test-provider", update)
        assert result.base_url == "http://localhost:9999"

    async def test_update_provider_nonexistent_raises(
        self,
        service: ProviderManagementService,
    ) -> None:
        update = UpdateProviderRequest(driver="litellm")
        with pytest.raises(ProviderNotFoundError, match="not found"):
            await service.update_provider("nonexistent", update)

    async def test_update_provider_partial_fields(
        self,
        service: ProviderManagementService,
    ) -> None:
        await service.create_provider(
            _make_create_request(
                auth_type=AuthType.API_KEY,
                api_key="sk-original",
            ),
        )
        update = UpdateProviderRequest(
            base_url="http://localhost:5000",
        )
        result = await service.update_provider("test-provider", update)
        assert result.base_url == "http://localhost:5000"
        assert result.api_key == "sk-original"


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestDeleteProvider:
    async def test_delete_provider_success(
        self,
        service: ProviderManagementService,
    ) -> None:
        await service.create_provider(_make_create_request())
        await service.delete_provider("test-provider")

        providers = await service.list_providers()
        assert "test-provider" not in providers

    async def test_delete_provider_nonexistent_raises(
        self,
        service: ProviderManagementService,
    ) -> None:
        with pytest.raises(ProviderNotFoundError, match="not found"):
            await service.delete_provider("nonexistent")


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestTestConnection:
    async def test_test_connection_no_models_error(
        self,
        service: ProviderManagementService,
    ) -> None:
        await service.create_provider(
            CreateProviderRequest(
                name="empty-provider",
                driver="litellm",
                auth_type=AuthType.NONE,
                models=(),
            ),
        )
        request = ConnTestRequest()
        result = await service.test_connection("empty-provider", request)
        assert result.success is False
        assert "no models" in (result.error or "").lower()

    async def test_test_connection_provider_not_found(
        self,
        service: ProviderManagementService,
    ) -> None:
        request = ConnTestRequest()
        result = await service.test_connection("nonexistent", request)
        assert result.success is False
        assert "not found" in (result.error or "").lower()

    async def test_test_connection_success(
        self,
        service: ProviderManagementService,
    ) -> None:
        await service.create_provider(_make_create_request())

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "pong"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.id = "test-id"

        with patch(
            "synthorg.providers.drivers.litellm_driver._litellm.acompletion",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            request = ConnTestRequest()
            result = await service.test_connection(
                "test-provider",
                request,
            )
            assert result.success is True
            assert result.latency_ms is not None
            assert result.model_tested == "test-model-001"

    async def test_test_connection_auth_failure(
        self,
        service: ProviderManagementService,
    ) -> None:
        await service.create_provider(_make_create_request())

        from synthorg.providers.errors import AuthenticationError

        with patch(
            "synthorg.providers.drivers.litellm_driver._litellm.acompletion",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Invalid key"),
        ):
            request = ConnTestRequest()
            result = await service.test_connection(
                "test-provider",
                request,
            )
            assert result.success is False
            assert result.error is not None


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestCreateFromPreset:
    async def test_create_from_preset(
        self,
        service: ProviderManagementService,
    ) -> None:
        request = CreateFromPresetRequest(
            preset_name="ollama",
            name="my-ollama",
        )
        result = await service.create_from_preset(request)
        assert result.auth_type == AuthType.NONE
        assert result.base_url == "http://localhost:11434"

    async def test_create_from_preset_with_overrides(
        self,
        service: ProviderManagementService,
    ) -> None:
        request = CreateFromPresetRequest(
            preset_name="ollama",
            name="my-ollama",
            base_url="http://gpu-server:11434",
        )
        result = await service.create_from_preset(request)
        assert result.base_url == "http://gpu-server:11434"

    async def test_create_from_preset_unknown_raises(
        self,
        service: ProviderManagementService,
    ) -> None:
        request = CreateFromPresetRequest(
            preset_name="nonexistent",
            name="my-provider",
        )
        with pytest.raises(ProviderValidationError, match="Unknown preset"):
            await service.create_from_preset(request)


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestConcurrency:
    async def test_concurrent_creates_serialized(
        self,
        service: ProviderManagementService,
    ) -> None:
        """Verify the lock prevents race conditions."""
        import asyncio

        requests = [
            CreateProviderRequest(
                name=f"provider-{i:02d}",
                driver="litellm",
                auth_type=AuthType.NONE,
                models=(
                    ProviderModelConfig(
                        id=f"model-{i:02d}",
                        alias=f"alias-{i:02d}",
                    ),
                ),
            )
            for i in range(5)
        ]
        results = await asyncio.gather(
            *(service.create_provider(r) for r in requests),
        )
        assert len(results) == 5
        providers = await service.list_providers()
        assert len(providers) == 5


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestClearApiKey:
    async def test_clear_api_key_removes_key(
        self,
        service: ProviderManagementService,
    ) -> None:
        await service.create_provider(
            _make_create_request(
                auth_type=AuthType.API_KEY,
                api_key="sk-original",
            ),
        )
        update = UpdateProviderRequest(clear_api_key=True)
        result = await service.update_provider("test-provider", update)
        assert result.api_key is None

    async def test_api_key_takes_precedence_over_clear(
        self,
        service: ProviderManagementService,
    ) -> None:
        """api_key + clear_api_key is rejected by the DTO validator."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="mutually exclusive"):
            UpdateProviderRequest(api_key="new-key", clear_api_key=True)


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestProviderNameValidation:
    @pytest.mark.parametrize(
        "name",
        ["a", "-bad", "bad-", "My-Provider", "presets", "from-preset"],
    )
    def test_invalid_names_rejected(self, name: str) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateProviderRequest(
                name=name,
                driver="litellm",
                auth_type=AuthType.NONE,
            )

    @pytest.mark.parametrize(
        "name",
        ["ab", "my-provider", "test-01", "ollama-local"],
    )
    def test_valid_names_accepted(self, name: str) -> None:
        request = CreateProviderRequest(
            name=name,
            driver="litellm",
            auth_type=AuthType.NONE,
        )
        assert request.name == name
