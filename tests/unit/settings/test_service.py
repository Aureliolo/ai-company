"""Unit tests for SettingsService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel, ConfigDict

from synthorg.settings.encryption import SettingsEncryptor
from synthorg.settings.enums import (
    SettingNamespace,
    SettingSource,
    SettingType,
)
from synthorg.settings.errors import (
    SettingNotFoundError,
    SettingsEncryptionError,
    SettingValidationError,
)
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import SettingsRegistry
from synthorg.settings.service import SettingsService

# ── Fixtures ──────────────────────────────────────────────────────


class _BudgetConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_monthly: float = 100.0


class _FakeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    budget: _BudgetConfig = _BudgetConfig()


def _make_definition(  # noqa: PLR0913
    *,
    namespace: SettingNamespace = SettingNamespace.BUDGET,
    key: str = "total_monthly",
    setting_type: SettingType = SettingType.FLOAT,
    default: str | None = "100.0",
    yaml_path: str | None = "budget.total_monthly",
    sensitive: bool = False,
    restart_required: bool = False,
    enum_values: tuple[str, ...] = (),
    min_value: float | None = None,
    max_value: float | None = None,
) -> SettingDefinition:
    return SettingDefinition(
        namespace=namespace,
        key=key,
        type=setting_type,
        default=default,
        description="test",
        group="test",
        yaml_path=yaml_path,
        sensitive=sensitive,
        restart_required=restart_required,
        enum_values=enum_values,
        min_value=min_value,
        max_value=max_value,
    )


@pytest.fixture
def registry() -> SettingsRegistry:
    r = SettingsRegistry()
    r.register(_make_definition())
    return r


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.set = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def config() -> _FakeConfig:
    return _FakeConfig()


@pytest.fixture
def service(
    mock_repo: AsyncMock, registry: SettingsRegistry, config: _FakeConfig
) -> SettingsService:
    return SettingsService(
        repository=mock_repo,
        registry=registry,
        config=config,
    )


# ── Resolution Order Tests ───────────────────────────────────────


@pytest.mark.unit
class TestResolutionOrder:
    """Tests for the DB > env > YAML > default resolution chain."""

    async def test_resolves_from_db(
        self, service: SettingsService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get.return_value = ("200.0", "2026-03-16T10:00:00Z")
        result = await service.get("budget", "total_monthly")
        assert result.value == "200.0"
        assert result.source == SettingSource.DATABASE
        assert result.updated_at == "2026-03-16T10:00:00Z"

    async def test_resolves_from_env(
        self,
        service: SettingsService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SYNTHORG_BUDGET_TOTAL_MONTHLY", "500.0")
        result = await service.get("budget", "total_monthly")
        assert result.value == "500.0"
        assert result.source == SettingSource.ENVIRONMENT

    async def test_resolves_from_yaml(self, service: SettingsService) -> None:
        result = await service.get("budget", "total_monthly")
        assert result.value == "100.0"
        assert result.source == SettingSource.YAML

    async def test_resolves_from_default(
        self,
        mock_repo: AsyncMock,
        config: _FakeConfig,
    ) -> None:
        registry = SettingsRegistry()
        registry.register(
            _make_definition(key="custom_key", yaml_path=None, default="42")
        )
        svc = SettingsService(repository=mock_repo, registry=registry, config=config)
        result = await svc.get("budget", "custom_key")
        assert result.value == "42"
        assert result.source == SettingSource.DEFAULT

    async def test_db_overrides_env(
        self,
        service: SettingsService,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SYNTHORG_BUDGET_TOTAL_MONTHLY", "500.0")
        mock_repo.get.return_value = ("200.0", "2026-03-16T10:00:00Z")
        result = await service.get("budget", "total_monthly")
        assert result.source == SettingSource.DATABASE

    async def test_env_overrides_yaml(
        self,
        service: SettingsService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SYNTHORG_BUDGET_TOTAL_MONTHLY", "500.0")
        result = await service.get("budget", "total_monthly")
        assert result.source == SettingSource.ENVIRONMENT

    async def test_unknown_setting_raises(self, service: SettingsService) -> None:
        with pytest.raises(SettingNotFoundError, match="Unknown setting"):
            await service.get("budget", "nonexistent")


# ── Cache Tests ──────────────────────────────────────────────────


@pytest.mark.unit
class TestCache:
    """Tests for cache behavior."""

    async def test_cache_hit(
        self, service: SettingsService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get.return_value = ("200.0", "2026-03-16T10:00:00Z")
        await service.get("budget", "total_monthly")
        await service.get("budget", "total_monthly")
        # Only one DB call — second was cached
        assert mock_repo.get.call_count == 1

    async def test_cache_invalidated_on_set(
        self, service: SettingsService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get.return_value = ("200.0", "2026-03-16T10:00:00Z")
        await service.get("budget", "total_monthly")
        await service.set("budget", "total_monthly", "300.0")
        mock_repo.get.return_value = ("300.0", "2026-03-16T11:00:00Z")
        result = await service.get("budget", "total_monthly")
        assert result.value == "300.0"
        assert mock_repo.get.call_count == 2

    async def test_cache_invalidated_on_delete(
        self, service: SettingsService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get.return_value = ("200.0", "2026-03-16T10:00:00Z")
        await service.get("budget", "total_monthly")
        await service.delete("budget", "total_monthly")
        mock_repo.get.return_value = None
        result = await service.get("budget", "total_monthly")
        # Falls through to YAML after cache miss
        assert result.source == SettingSource.YAML
        assert mock_repo.get.call_count == 2


# ── Validation Tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestValidation:
    """Tests for value validation on set()."""

    async def test_rejects_non_float(self, service: SettingsService) -> None:
        with pytest.raises(SettingValidationError, match="Expected float"):
            await service.set("budget", "total_monthly", "not-a-number")

    async def test_rejects_below_min(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        registry = SettingsRegistry()
        registry.register(_make_definition(min_value=0.0))
        svc = SettingsService(repository=mock_repo, registry=registry, config=config)
        with pytest.raises(SettingValidationError, match="below minimum"):
            await svc.set("budget", "total_monthly", "-1.0")

    async def test_rejects_above_max(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        registry = SettingsRegistry()
        registry.register(_make_definition(max_value=1000.0))
        svc = SettingsService(repository=mock_repo, registry=registry, config=config)
        with pytest.raises(SettingValidationError, match="above maximum"):
            await svc.set("budget", "total_monthly", "9999.0")

    async def test_rejects_invalid_enum(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        registry = SettingsRegistry()
        registry.register(
            _make_definition(
                key="strategy",
                setting_type=SettingType.ENUM,
                enum_values=("a", "b"),
                yaml_path=None,
            )
        )
        svc = SettingsService(repository=mock_repo, registry=registry, config=config)
        with pytest.raises(SettingValidationError, match="Invalid enum"):
            await svc.set("budget", "strategy", "c")

    async def test_rejects_invalid_bool(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        registry = SettingsRegistry()
        registry.register(
            _make_definition(
                key="enabled",
                setting_type=SettingType.BOOLEAN,
                yaml_path=None,
            )
        )
        svc = SettingsService(repository=mock_repo, registry=registry, config=config)
        with pytest.raises(SettingValidationError, match="Expected boolean"):
            await svc.set("budget", "enabled", "maybe")

    async def test_accepts_valid_value(
        self, service: SettingsService, mock_repo: AsyncMock
    ) -> None:
        entry = await service.set("budget", "total_monthly", "200.0")
        assert entry.value == "200.0"
        assert entry.source == SettingSource.DATABASE
        mock_repo.set.assert_called_once()


# ── Sensitive Settings Tests ─────────────────────────────────────


@pytest.mark.unit
class TestSensitiveSettings:
    """Tests for encryption of sensitive settings."""

    async def test_sensitive_encrypted_on_write(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        enc = SettingsEncryptor(Fernet.generate_key())
        registry = SettingsRegistry()
        registry.register(
            _make_definition(
                key="api_key",
                setting_type=SettingType.STRING,
                sensitive=True,
                yaml_path=None,
            )
        )
        svc = SettingsService(
            repository=mock_repo,
            registry=registry,
            config=config,
            encryptor=enc,
        )
        await svc.set("budget", "api_key", "secret123")
        # The stored value should be encrypted, not plaintext
        call_args = mock_repo.set.call_args
        stored_value = call_args[0][2]
        assert stored_value != "secret123"
        assert enc.decrypt(stored_value) == "secret123"

    async def test_sensitive_decrypted_on_read(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        enc = SettingsEncryptor(Fernet.generate_key())
        registry = SettingsRegistry()
        registry.register(
            _make_definition(
                key="api_key",
                setting_type=SettingType.STRING,
                sensitive=True,
                yaml_path=None,
            )
        )
        svc = SettingsService(
            repository=mock_repo,
            registry=registry,
            config=config,
            encryptor=enc,
        )
        ciphertext = enc.encrypt("secret123")
        mock_repo.get.return_value = (ciphertext, "2026-03-16T10:00:00Z")
        result = await svc.get("budget", "api_key")
        assert result.value == "secret123"

    async def test_sensitive_masked_in_entry(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        enc = SettingsEncryptor(Fernet.generate_key())
        registry = SettingsRegistry()
        registry.register(
            _make_definition(
                key="api_key",
                setting_type=SettingType.STRING,
                sensitive=True,
                yaml_path=None,
            )
        )
        svc = SettingsService(
            repository=mock_repo,
            registry=registry,
            config=config,
            encryptor=enc,
        )
        ciphertext = enc.encrypt("secret123")
        mock_repo.get.return_value = (ciphertext, "2026-03-16T10:00:00Z")
        entry = await svc.get_entry("budget", "api_key")
        assert entry.value == "********"

    async def test_sensitive_rejects_without_encryptor(
        self, mock_repo: AsyncMock, config: _FakeConfig
    ) -> None:
        registry = SettingsRegistry()
        registry.register(
            _make_definition(
                key="api_key",
                setting_type=SettingType.STRING,
                sensitive=True,
                yaml_path=None,
            )
        )
        svc = SettingsService(
            repository=mock_repo,
            registry=registry,
            config=config,
            encryptor=None,
        )
        with pytest.raises(SettingsEncryptionError, match="without encryption"):
            await svc.set("budget", "api_key", "secret123")


# ── Notification Tests ───────────────────────────────────────────


@pytest.mark.unit
class TestNotifications:
    """Tests for change notification publishing."""

    async def test_publishes_on_set(
        self, mock_repo: AsyncMock, registry: SettingsRegistry, config: _FakeConfig
    ) -> None:
        bus = MagicMock()
        bus.is_running = True
        bus.publish = AsyncMock()
        svc = SettingsService(
            repository=mock_repo,
            registry=registry,
            config=config,
            message_bus=bus,
        )
        await svc.set("budget", "total_monthly", "200.0")
        bus.publish.assert_called_once()
        msg = bus.publish.call_args[0][0]
        assert msg.channel == "#settings"
        assert "total_monthly" in msg.content

    async def test_publishes_on_delete(
        self, mock_repo: AsyncMock, registry: SettingsRegistry, config: _FakeConfig
    ) -> None:
        bus = MagicMock()
        bus.is_running = True
        bus.publish = AsyncMock()
        svc = SettingsService(
            repository=mock_repo,
            registry=registry,
            config=config,
            message_bus=bus,
        )
        await svc.delete("budget", "total_monthly")
        bus.publish.assert_called_once()

    async def test_no_publish_without_bus(self, service: SettingsService) -> None:
        """Set should succeed even without message bus."""
        entry = await service.set("budget", "total_monthly", "200.0")
        assert entry.value == "200.0"


# ── Schema Tests ─────────────────────────────────────────────────


@pytest.mark.unit
class TestSchema:
    """Tests for schema introspection."""

    def test_get_schema_all(self, service: SettingsService) -> None:
        schema = service.get_schema()
        assert len(schema) == 1
        assert schema[0].key == "total_monthly"

    def test_get_schema_namespace(self, service: SettingsService) -> None:
        schema = service.get_schema(namespace="budget")
        assert len(schema) == 1

    def test_get_schema_empty_namespace(self, service: SettingsService) -> None:
        schema = service.get_schema(namespace="nonexistent")
        assert schema == ()
