"""Tests for multi-provider model resolution."""

from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from synthorg.config.schema import ProviderConfig, ProviderModelConfig
from synthorg.providers.routing.models import ResolvedModel
from synthorg.providers.routing.resolver import ModelResolver
from synthorg.providers.routing.selector import (
    CheapestSelector,
    QuotaAwareSelector,
)

pytestmark = pytest.mark.unit

# ── Helpers ──────────────────────────────────────────────────────


def _two_provider_config() -> dict[str, ProviderConfig]:
    """Two providers serving the same model ID with different costs."""
    return {
        "test-provider-a": ProviderConfig(
            driver="litellm",
            api_key="sk-test-a",
            models=(
                ProviderModelConfig(
                    id="test-shared-001",
                    alias="shared",
                    cost_per_1k_input=0.010,
                    cost_per_1k_output=0.050,
                    estimated_latency_ms=1000,
                ),
            ),
        ),
        "test-provider-b": ProviderConfig(
            driver="litellm",
            api_key="sk-test-b",
            models=(
                ProviderModelConfig(
                    id="test-shared-001",
                    alias="shared",
                    cost_per_1k_input=0.001,
                    cost_per_1k_output=0.005,
                    estimated_latency_ms=500,
                ),
            ),
        ),
    }


def _mixed_provider_config() -> dict[str, ProviderConfig]:
    """Provider A has shared + unique model; provider B has shared only."""
    return {
        "test-provider-a": ProviderConfig(
            driver="litellm",
            api_key="sk-test-a",
            models=(
                ProviderModelConfig(
                    id="test-shared-001",
                    alias="shared",
                    cost_per_1k_input=0.010,
                    cost_per_1k_output=0.050,
                ),
                ProviderModelConfig(
                    id="test-unique-001",
                    alias="unique",
                    cost_per_1k_input=0.003,
                    cost_per_1k_output=0.015,
                ),
            ),
        ),
        "test-provider-b": ProviderConfig(
            driver="litellm",
            api_key="sk-test-b",
            models=(
                ProviderModelConfig(
                    id="test-shared-001",
                    alias="shared",
                    cost_per_1k_input=0.001,
                    cost_per_1k_output=0.005,
                ),
            ),
        ),
    }


# ── TestMultiProviderIndex ───────────────────────────────────────


class TestMultiProviderIndex:
    def test_same_model_id_different_providers_no_error(self) -> None:
        """Two providers registering the same model_id should not raise."""
        resolver = ModelResolver.from_config(_two_provider_config())
        model = resolver.resolve("test-shared-001")
        assert model.model_id == "test-shared-001"

    def test_same_alias_different_providers_no_error(self) -> None:
        """Two providers registering the same alias should not raise."""
        resolver = ModelResolver.from_config(_two_provider_config())
        model = resolver.resolve("shared")
        assert model.model_id == "test-shared-001"

    def test_resolve_all_returns_all_candidates(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        candidates = resolver.resolve_all("shared")
        assert len(candidates) == 2
        providers = {c.provider_name for c in candidates}
        assert providers == {"test-provider-a", "test-provider-b"}

    def test_resolve_all_by_model_id(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        candidates = resolver.resolve_all("test-shared-001")
        assert len(candidates) == 2

    def test_resolve_all_empty_for_unknown(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        assert resolver.resolve_all("nonexistent") == ()

    def test_all_models_returns_all_variants(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        models = resolver.all_models()
        assert len(models) == 2
        providers = {m.provider_name for m in models}
        assert providers == {"test-provider-a", "test-provider-b"}

    def test_all_models_mixed_shared_and_unique(self) -> None:
        resolver = ModelResolver.from_config(_mixed_provider_config())
        models = resolver.all_models()
        # 2 shared variants + 1 unique = 3
        assert len(models) == 3

    def test_all_models_sorted_by_cost_includes_all_variants(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        models = resolver.all_models_sorted_by_cost()
        assert len(models) == 2
        # Cheapest first
        assert models[0].provider_name == "test-provider-b"
        assert models[1].provider_name == "test-provider-a"

    def test_all_models_sorted_by_latency_includes_all_variants(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        models = resolver.all_models_sorted_by_latency()
        assert len(models) == 2
        # Fastest first (500ms < 1000ms)
        assert models[0].provider_name == "test-provider-b"

    def test_exact_duplicate_skipped(self) -> None:
        """Same provider, same model, same ref should not create duplicates."""
        providers = {
            "test-provider": ProviderConfig(
                driver="litellm",
                api_key="sk-test",
                models=(
                    ProviderModelConfig(
                        id="test-model-001",
                        alias="model",
                        cost_per_1k_input=0.003,
                        cost_per_1k_output=0.015,
                    ),
                ),
            ),
        }
        resolver = ModelResolver.from_config(providers)
        # model_id and alias both point to same model -- only one candidate
        candidates_by_id = resolver.resolve_all("test-model-001")
        candidates_by_alias = resolver.resolve_all("model")
        assert len(candidates_by_id) == 1
        assert len(candidates_by_alias) == 1


# ── TestMultiProviderWithSelector ────────────────────────────────


class TestMultiProviderWithSelector:
    def test_default_selector_is_quota_aware(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        assert isinstance(resolver.selector, QuotaAwareSelector)

    def test_resolve_uses_injected_selector(self) -> None:
        mock_selector = MagicMock()
        expected = ResolvedModel(
            provider_name="test-provider-a",
            model_id="test-shared-001",
            cost_per_1k_input=0.010,
            cost_per_1k_output=0.050,
        )
        mock_selector.select.return_value = expected

        resolver = ModelResolver.from_config(
            _two_provider_config(),
            selector=mock_selector,
        )
        result = resolver.resolve("shared")

        mock_selector.select.assert_called_once()
        assert result is expected

    def test_resolve_safe_uses_selector(self) -> None:
        mock_selector = MagicMock()
        expected = ResolvedModel(
            provider_name="test-provider-b",
            model_id="test-shared-001",
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.005,
        )
        mock_selector.select.return_value = expected

        resolver = ModelResolver.from_config(
            _two_provider_config(),
            selector=mock_selector,
        )
        result = resolver.resolve_safe("shared")

        mock_selector.select.assert_called()
        assert result is expected

    def test_cheapest_selector_picks_cheapest(self) -> None:
        resolver = ModelResolver.from_config(
            _two_provider_config(),
            selector=CheapestSelector(),
        )
        model = resolver.resolve("shared")
        assert model.provider_name == "test-provider-b"

    def test_quota_aware_prefers_available(self) -> None:
        selector = QuotaAwareSelector(
            provider_quota_available={
                "test-provider-a": True,
                "test-provider-b": False,
            },
        )
        resolver = ModelResolver.from_config(
            _two_provider_config(),
            selector=selector,
        )
        model = resolver.resolve("shared")
        assert model.provider_name == "test-provider-a"

    def test_from_config_passes_selector(self) -> None:
        selector = CheapestSelector()
        resolver = ModelResolver.from_config(
            _two_provider_config(),
            selector=selector,
        )
        assert resolver.selector is selector


# ── TestMultiProviderImmutability ────────────────────────────────


class TestMultiProviderImmutability:
    def test_index_is_mapping_proxy(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        assert isinstance(resolver._index, MappingProxyType)

    def test_candidate_tuples_are_immutable(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        candidates = resolver.resolve_all("shared")
        assert isinstance(candidates, tuple)

    def test_index_mutation_blocked(self) -> None:
        resolver = ModelResolver.from_config(_two_provider_config())
        with pytest.raises(TypeError):
            resolver._index["new"] = ()  # type: ignore[index]
