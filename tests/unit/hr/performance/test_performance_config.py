"""Tests for PerformanceConfig quality weight validation."""

import pytest
from pydantic import ValidationError

from synthorg.hr.performance.config import PerformanceConfig


@pytest.mark.unit
class TestQualityWeightValidation:
    """Validate quality_ci_weight + quality_llm_weight == 1.0."""

    @pytest.mark.parametrize(
        ("ci_w", "llm_w"),
        [
            (0.4, 0.6),
            (0.0, 1.0),
            (1.0, 0.0),
            (0.5, 0.5),
            (0.3, 0.7),
        ],
    )
    def test_valid_weight_combinations(
        self,
        ci_w: float,
        llm_w: float,
    ) -> None:
        """Weights summing to 1.0 are accepted."""
        cfg = PerformanceConfig(
            quality_ci_weight=ci_w,
            quality_llm_weight=llm_w,
        )
        assert cfg.quality_ci_weight == ci_w
        assert cfg.quality_llm_weight == llm_w

    @pytest.mark.parametrize(
        ("ci_w", "llm_w"),
        [
            (0.5, 0.6),
            (0.0, 0.0),
            (0.3, 0.3),
            (1.0, 1.0),
        ],
    )
    def test_invalid_weight_combinations(
        self,
        ci_w: float,
        llm_w: float,
    ) -> None:
        """Weights not summing to 1.0 raise ValidationError."""
        with pytest.raises(ValidationError, match=r"must sum to 1\.0"):
            PerformanceConfig(
                quality_ci_weight=ci_w,
                quality_llm_weight=llm_w,
            )

    def test_default_weights_are_valid(self) -> None:
        """Default config weights (0.4 + 0.6) pass validation."""
        cfg = PerformanceConfig()
        assert cfg.quality_ci_weight == 0.4
        assert cfg.quality_llm_weight == 0.6


@pytest.mark.unit
class TestProviderRequiresModelValidation:
    """quality_judge_provider requires quality_judge_model."""

    def test_provider_without_model_raises(self) -> None:
        """Setting provider without model raises ValidationError."""
        with pytest.raises(ValidationError, match="quality_judge_provider requires"):
            PerformanceConfig(
                quality_judge_provider="test-provider",
            )

    def test_provider_with_model_valid(self) -> None:
        """Setting both provider and model is accepted."""
        cfg = PerformanceConfig(
            quality_judge_model="test-small-001",
            quality_judge_provider="test-provider",
        )
        assert cfg.quality_judge_model == "test-small-001"
        assert cfg.quality_judge_provider == "test-provider"

    def test_model_without_provider_valid(self) -> None:
        """Setting model without provider is accepted (auto-resolve)."""
        cfg = PerformanceConfig(
            quality_judge_model="test-small-001",
        )
        assert cfg.quality_judge_model == "test-small-001"
        assert cfg.quality_judge_provider is None
