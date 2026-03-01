"""Unit tests for ProviderRegistry."""

import pytest

from ai_company.config.schema import ProviderConfig, ProviderModelConfig
from ai_company.providers.base import BaseCompletionProvider
from ai_company.providers.errors import (
    DriverFactoryNotFoundError,
    DriverNotRegisteredError,
)
from ai_company.providers.registry import ProviderRegistry

# ── Helpers ──────────────────────────────────────────────────────


def _make_config(
    *,
    driver: str = "litellm",
    api_key: str | None = "sk-test",
) -> ProviderConfig:
    return ProviderConfig(
        driver=driver,
        api_key=api_key,
        models=(
            ProviderModelConfig(
                id="test-model",
                alias="test",
                cost_per_1k_input=0.001,
                cost_per_1k_output=0.002,
            ),
        ),
    )


class _StubDriver(BaseCompletionProvider):
    """Minimal concrete driver for registry tests."""

    def __init__(self, provider_name: str, config: ProviderConfig) -> None:
        self.provider_name = provider_name
        self.config = config

    async def _do_complete(self, messages, model, *, tools=None, config=None):
        raise NotImplementedError

    async def _do_stream(self, messages, model, *, tools=None, config=None):
        raise NotImplementedError

    async def _do_get_model_capabilities(self, model):
        raise NotImplementedError


# ── get() ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRegistryGet:
    def test_get_returns_registered_driver(self):
        driver = _StubDriver("anthropic", _make_config())
        registry = ProviderRegistry({"anthropic": driver})

        result = registry.get("anthropic")

        assert result is driver

    def test_get_raises_for_unknown_name(self):
        registry = ProviderRegistry({})

        with pytest.raises(DriverNotRegisteredError, match="not registered"):
            registry.get("nonexistent")

    def test_get_error_lists_available_providers(self):
        driver = _StubDriver("anthropic", _make_config())
        registry = ProviderRegistry({"anthropic": driver})

        with pytest.raises(DriverNotRegisteredError, match="anthropic"):
            registry.get("openai")


# ── list_providers() ─────────────────────────────────────────────


@pytest.mark.unit
class TestRegistryListProviders:
    def test_list_providers_returns_sorted_names(self):
        drivers = {
            "openrouter": _StubDriver("openrouter", _make_config()),
            "anthropic": _StubDriver("anthropic", _make_config()),
            "ollama": _StubDriver("ollama", _make_config()),
        }
        registry = ProviderRegistry(drivers)

        result = registry.list_providers()

        assert result == ("anthropic", "ollama", "openrouter")

    def test_list_providers_empty_registry(self):
        registry = ProviderRegistry({})

        assert registry.list_providers() == ()


# ── __contains__ / __len__ ───────────────────────────────────────


@pytest.mark.unit
class TestRegistryContainsAndLen:
    def test_contains_registered_provider(self):
        driver = _StubDriver("anthropic", _make_config())
        registry = ProviderRegistry({"anthropic": driver})

        assert "anthropic" in registry
        assert "unknown" not in registry

    def test_len_reflects_registered_count(self):
        drivers = {
            "a": _StubDriver("a", _make_config()),
            "b": _StubDriver("b", _make_config()),
        }
        registry = ProviderRegistry(drivers)

        assert len(registry) == 2

    def test_empty_registry_len_zero(self):
        assert len(ProviderRegistry({})) == 0


# ── from_config() ────────────────────────────────────────────────


@pytest.mark.unit
class TestRegistryFromConfig:
    def test_from_config_with_factory_overrides(self):
        config = _make_config(driver="stub")
        providers = {"test-provider": config}

        registry = ProviderRegistry.from_config(
            providers,
            factory_overrides={"stub": _StubDriver},
        )

        assert "test-provider" in registry
        driver = registry.get("test-provider")
        assert isinstance(driver, _StubDriver)
        assert driver.provider_name == "test-provider"

    def test_from_config_multiple_providers(self):
        providers = {
            "alpha": _make_config(driver="stub"),
            "beta": _make_config(driver="stub"),
        }

        registry = ProviderRegistry.from_config(
            providers,
            factory_overrides={"stub": _StubDriver},
        )

        assert len(registry) == 2
        assert registry.list_providers() == ("alpha", "beta")

    def test_from_config_raises_for_unknown_driver(self):
        config = _make_config(driver="nonexistent")
        providers = {"test": config}

        with pytest.raises(DriverFactoryNotFoundError, match="No factory"):
            ProviderRegistry.from_config(providers)

    def test_from_config_empty_providers(self):
        registry = ProviderRegistry.from_config({})

        assert len(registry) == 0
        assert registry.list_providers() == ()

    def test_from_config_uses_litellm_by_default(self):
        """Default driver='litellm' resolves to LiteLLMDriver factory."""
        from ai_company.providers.drivers.litellm_driver import LiteLLMDriver

        config = _make_config(driver="litellm")
        providers = {"anthropic": config}

        registry = ProviderRegistry.from_config(providers)

        driver = registry.get("anthropic")
        assert isinstance(driver, LiteLLMDriver)


# ── Immutability ─────────────────────────────────────────────────


@pytest.mark.unit
class TestRegistryImmutability:
    def test_registry_does_not_reflect_mutations_to_original_dict(self):
        drivers: dict[str, BaseCompletionProvider] = {
            "a": _StubDriver("a", _make_config()),
        }
        registry = ProviderRegistry(drivers)

        # Mutate the original dict
        drivers["b"] = _StubDriver("b", _make_config())

        # Registry should not be affected
        assert len(registry) == 1
        assert "b" not in registry
