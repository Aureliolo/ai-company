"""Tests for embedding model selector."""

import pytest

from synthorg.memory.embedding.rankings import (
    LMEB_RANKINGS,
    DeploymentTier,
)
from synthorg.memory.embedding.selector import (
    infer_deployment_tier,
    select_embedding_model,
)


@pytest.mark.unit
class TestSelectEmbeddingModel:
    def test_returns_highest_ranked_match(self) -> None:
        """When multiple LMEB models are available, pick the best."""
        top = LMEB_RANKINGS[0]
        second = LMEB_RANKINGS[1]
        available = (top.model_id, second.model_id)
        result = select_embedding_model(available)
        assert result is not None
        assert result.model_id == top.model_id

    def test_returns_none_when_no_match(self) -> None:
        result = select_embedding_model(
            ("unknown-model-xyz", "another-unknown"),
        )
        assert result is None

    def test_empty_available_returns_none(self) -> None:
        result = select_embedding_model(())
        assert result is None

    def test_respects_tier_filter(self) -> None:
        """When tier is specified, only models from that tier match."""
        cpu_models = [r for r in LMEB_RANKINGS if r.tier == DeploymentTier.CPU]
        assert len(cpu_models) >= 1
        cpu_model = cpu_models[0]
        # Offer both a GPU and CPU model -- tier filter should pick CPU
        gpu_model = next(
            (r for r in LMEB_RANKINGS if r.tier == DeploymentTier.GPU_FULL),
            None,
        )
        assert gpu_model is not None, "LMEB_RANKINGS must have a GPU_FULL entry"
        available = (gpu_model.model_id, cpu_model.model_id)
        result = select_embedding_model(
            available,
            deployment_tier=DeploymentTier.CPU,
        )
        assert result is not None
        assert result.tier == DeploymentTier.CPU

    def test_tier_filter_no_match(self) -> None:
        """Tier filter excludes all available models."""
        gpu_model = next(
            (r for r in LMEB_RANKINGS if r.tier == DeploymentTier.GPU_FULL),
            None,
        )
        assert gpu_model is not None, "LMEB_RANKINGS must have a GPU_FULL entry"
        result = select_embedding_model(
            (gpu_model.model_id,),
            deployment_tier=DeploymentTier.CPU,
        )
        assert result is None

    def test_substring_match(self) -> None:
        """Ollama model names may include version tags."""
        top = LMEB_RANKINGS[0]
        # Simulate Ollama-style name with :latest suffix
        available = (f"{top.model_id}:latest",)
        result = select_embedding_model(available)
        assert result is not None
        assert result.model_id == top.model_id

    def test_case_insensitive_match(self) -> None:
        top = LMEB_RANKINGS[0]
        available = (top.model_id.upper(),)
        result = select_embedding_model(available)
        assert result is not None
        assert result.model_id == top.model_id

    def test_no_tier_uses_all_rankings(self) -> None:
        """Without tier filter, all tiers are considered."""
        top = LMEB_RANKINGS[0]
        available = (top.model_id,)
        result = select_embedding_model(available)
        assert result is not None


@pytest.mark.unit
class TestInferDeploymentTier:
    @pytest.mark.parametrize(
        "preset_name",
        ["ollama", "lm-studio", "vllm"],
    )
    def test_local_with_gpu(self, preset_name: str) -> None:
        result = infer_deployment_tier(preset_name, has_gpu=True)
        assert result == DeploymentTier.GPU_CONSUMER

    @pytest.mark.parametrize(
        "preset_name",
        ["ollama", "lm-studio", "vllm"],
    )
    def test_local_without_gpu(self, preset_name: str) -> None:
        result = infer_deployment_tier(preset_name, has_gpu=False)
        assert result == DeploymentTier.CPU

    @pytest.mark.parametrize(
        "preset_name",
        ["ollama", "lm-studio", "vllm"],
    )
    def test_local_gpu_unknown(self, preset_name: str) -> None:
        """Unknown GPU status defaults to GPU_CONSUMER for local."""
        result = infer_deployment_tier(preset_name, has_gpu=None)
        assert result == DeploymentTier.GPU_CONSUMER

    @pytest.mark.parametrize(
        "preset_name",
        ["example-cloud-provider", "some-api-service"],
    )
    def test_cloud_provider(self, preset_name: str) -> None:
        """Non-local providers assume full GPU resources."""
        result = infer_deployment_tier(preset_name)
        assert result == DeploymentTier.GPU_FULL

    def test_none_preset_defaults_gpu_consumer(self) -> None:
        result = infer_deployment_tier(None)
        assert result == DeploymentTier.GPU_CONSUMER

    def test_case_insensitive(self) -> None:
        result = infer_deployment_tier("Ollama", has_gpu=False)
        assert result == DeploymentTier.CPU
