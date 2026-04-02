"""Tests for embedder config resolution."""

import pytest

from synthorg.memory.config import CompanyMemoryConfig, EmbedderOverrideConfig
from synthorg.memory.embedding.rankings import LMEB_RANKINGS, DeploymentTier
from synthorg.memory.embedding.resolve import resolve_embedder_config
from synthorg.memory.errors import MemoryConfigError


@pytest.mark.unit
class TestResolveEmbedderConfig:
    def test_settings_override_wins(self) -> None:
        """Settings override takes highest priority."""
        override = EmbedderOverrideConfig(
            provider="override-provider",
            model="override-model",
            dims=512,
        )
        config = CompanyMemoryConfig()
        result = resolve_embedder_config(
            config,
            available_models=(LMEB_RANKINGS[0].model_id,),
            settings_override=override,
        )
        assert result.provider == "override-provider"
        assert result.model == "override-model"
        assert result.dims == 512

    def test_yaml_config_override_second_priority(self) -> None:
        """YAML config embedder override wins over auto-select."""
        yaml_override = EmbedderOverrideConfig(
            provider="yaml-provider",
            model="yaml-model",
            dims=768,
        )
        config = CompanyMemoryConfig(embedder=yaml_override)
        result = resolve_embedder_config(
            config,
            available_models=(LMEB_RANKINGS[0].model_id,),
        )
        assert result.provider == "yaml-provider"
        assert result.model == "yaml-model"
        assert result.dims == 768

    def test_auto_select_from_available_models(self) -> None:
        """Falls back to auto-selection from available models."""
        top = LMEB_RANKINGS[0]
        config = CompanyMemoryConfig()
        result = resolve_embedder_config(
            config,
            available_models=(top.model_id,),
            provider_preset_name="ollama",
        )
        assert result.model == top.model_id
        assert result.dims == top.output_dims

    def test_auto_select_with_tier(self) -> None:
        """Tier inference affects auto-selection."""
        cpu_model = next(r for r in LMEB_RANKINGS if r.tier == DeploymentTier.CPU)
        config = CompanyMemoryConfig()
        result = resolve_embedder_config(
            config,
            available_models=(cpu_model.model_id,),
            provider_preset_name="ollama",
            has_gpu=False,
        )
        assert result.model == cpu_model.model_id
        assert result.dims == cpu_model.output_dims

    def test_no_available_models_raises(self) -> None:
        """Raises MemoryConfigError when no models can be resolved."""
        config = CompanyMemoryConfig()
        with pytest.raises(MemoryConfigError, match="resolve"):
            resolve_embedder_config(config)

    def test_no_lmeb_match_raises(self) -> None:
        """Raises when available models don't match any LMEB entry."""
        config = CompanyMemoryConfig()
        with pytest.raises(MemoryConfigError, match="resolve"):
            resolve_embedder_config(
                config,
                available_models=("unknown-model-xyz",),
            )

    def test_partial_settings_override_fills_from_auto(self) -> None:
        """Provider-only override uses auto-select for model/dims."""
        top = LMEB_RANKINGS[0]
        override = EmbedderOverrideConfig(provider="custom-provider")
        config = CompanyMemoryConfig()
        result = resolve_embedder_config(
            config,
            available_models=(top.model_id,),
            settings_override=override,
        )
        assert result.provider == "custom-provider"
        assert result.model == top.model_id
        assert result.dims == top.output_dims

    def test_partial_yaml_override_fills_from_auto(self) -> None:
        """YAML provider-only override fills model/dims from auto."""
        top = LMEB_RANKINGS[0]
        yaml_override = EmbedderOverrideConfig(provider="yaml-prov")
        config = CompanyMemoryConfig(embedder=yaml_override)
        result = resolve_embedder_config(
            config,
            available_models=(top.model_id,),
        )
        assert result.provider == "yaml-prov"
        assert result.model == top.model_id

    def test_default_provider_from_ranking(self) -> None:
        """When no provider override, provider defaults to model_id."""
        top = LMEB_RANKINGS[0]
        config = CompanyMemoryConfig()
        result = resolve_embedder_config(
            config,
            available_models=(top.model_id,),
        )
        assert result.provider == top.model_id
