"""Shared fixtures for provider management tests."""

from typing import Any

import pytest

import synthorg.settings.definitions  # noqa: F401 -- trigger registration
from synthorg.api.dto import CreateProviderRequest
from synthorg.api.state import AppState
from synthorg.config.schema import ProviderModelConfig, RootConfig
from synthorg.providers.enums import AuthType
from synthorg.providers.management.service import ProviderManagementService
from synthorg.settings.encryption import SettingsEncryptor
from synthorg.settings.registry import get_registry
from synthorg.settings.service import SettingsService
from tests.unit.api.fakes import FakeMessageBus, FakePersistenceBackend


@pytest.fixture
async def fake_persistence() -> FakePersistenceBackend:
    """In-memory persistence backend for provider management tests."""
    backend = FakePersistenceBackend()
    await backend.connect()
    return backend


@pytest.fixture
async def fake_message_bus() -> FakeMessageBus:
    """In-memory message bus for provider management tests."""
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


def make_create_request(
    name: str = "test-provider",
    auth_type: AuthType = AuthType.NONE,
    **kwargs: Any,
) -> CreateProviderRequest:
    """Build a ``CreateProviderRequest`` with sensible defaults."""
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
