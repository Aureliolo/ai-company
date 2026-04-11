"""Unit tests for training mode configuration."""

import pytest

from synthorg.hr.training.config import TrainingConfig
from synthorg.hr.training.models import ContentType


@pytest.mark.unit
class TestTrainingConfig:
    """TrainingConfig model tests."""

    def test_defaults(self) -> None:
        config = TrainingConfig()
        assert config.enabled is True
        assert config.source_selector_type == "role_top_performers"
        assert config.curation_strategy_type == "relevance"
        assert config.require_review_by_default is True
        assert config.sanitization_max_length == 2000
        assert config.training_namespace == "training"
        assert config.training_tags == ("learned_from_seniors",)

    def test_default_volume_caps(self) -> None:
        config = TrainingConfig()
        assert config.default_volume_caps[ContentType.PROCEDURAL] == 50
        assert config.default_volume_caps[ContentType.SEMANTIC] == 10
        assert config.default_volume_caps[ContentType.TOOL_PATTERNS] == 20

    def test_default_selector_config(self) -> None:
        config = TrainingConfig()
        assert config.source_selector_config["top_n"] == 3

    def test_default_curation_config(self) -> None:
        config = TrainingConfig()
        assert config.curation_strategy_config["top_k"] == 50

    def test_frozen(self) -> None:
        config = TrainingConfig()
        with pytest.raises(Exception):  # noqa: B017, PT011
            config.enabled = False  # type: ignore[misc]

    def test_custom_values(self) -> None:
        config = TrainingConfig(
            enabled=False,
            source_selector_type="department_diversity",
            curation_strategy_type="llm_curated",
            require_review_by_default=False,
            sanitization_max_length=5000,
            training_namespace="custom_ns",
            training_tags=("custom-tag",),
        )
        assert config.enabled is False
        assert config.source_selector_type == "department_diversity"
        assert config.curation_strategy_type == "llm_curated"
        assert config.require_review_by_default is False
        assert config.sanitization_max_length == 5000
        assert config.training_namespace == "custom_ns"
        assert config.training_tags == ("custom-tag",)

    def test_sanitization_max_length_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="greater than 0"):
            TrainingConfig(sanitization_max_length=0)

    def test_custom_volume_caps(self) -> None:
        config = TrainingConfig(
            default_volume_caps={
                ContentType.PROCEDURAL: 100,
                ContentType.SEMANTIC: 25,
                ContentType.TOOL_PATTERNS: 50,
            },
        )
        assert config.default_volume_caps[ContentType.PROCEDURAL] == 100
        assert config.default_volume_caps[ContentType.SEMANTIC] == 25
        assert config.default_volume_caps[ContentType.TOOL_PATTERNS] == 50
