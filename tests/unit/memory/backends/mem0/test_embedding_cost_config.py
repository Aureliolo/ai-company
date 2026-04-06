"""Tests for EmbeddingCostConfig model."""

import pytest
from pydantic import ValidationError

from synthorg.memory.backends.mem0.config import EmbeddingCostConfig


@pytest.mark.unit
class TestEmbeddingCostConfig:
    """EmbeddingCostConfig defaults, validation, and custom values."""

    def test_defaults(self) -> None:
        config = EmbeddingCostConfig()
        assert config.enabled is False
        assert config.model_pricing == {}
        assert config.default_chars_per_token == 4

    def test_frozen(self) -> None:
        config = EmbeddingCostConfig()
        with pytest.raises(ValidationError):
            config.enabled = True  # type: ignore[misc]

    def test_negative_pricing_rejected(self) -> None:
        with pytest.raises(ValidationError, match="negative"):
            EmbeddingCostConfig(model_pricing={"model-a": -0.5})

    def test_zero_pricing_accepted(self) -> None:
        config = EmbeddingCostConfig(model_pricing={"model-a": 0.0})
        assert config.model_pricing["model-a"] == 0.0

    def test_chars_per_token_below_min(self) -> None:
        with pytest.raises(ValidationError):
            EmbeddingCostConfig(default_chars_per_token=0)

    def test_chars_per_token_above_max(self) -> None:
        with pytest.raises(ValidationError):
            EmbeddingCostConfig(default_chars_per_token=21)

    def test_custom_values(self) -> None:
        config = EmbeddingCostConfig(
            enabled=True,
            model_pricing={"model-a": 0.1, "model-b": 0.05},
            default_chars_per_token=6,
        )
        assert config.enabled is True
        assert config.model_pricing["model-a"] == 0.1
        assert config.model_pricing["model-b"] == 0.05
        assert config.default_chars_per_token == 6

    def test_blank_model_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EmbeddingCostConfig(model_pricing={"": 0.5})
