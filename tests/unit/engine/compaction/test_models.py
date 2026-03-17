"""Tests for compaction configuration and result models."""

import pytest
from pydantic import ValidationError

from synthorg.engine.compaction.models import (
    CompactionConfig,
    CompressionMetadata,
)


@pytest.mark.unit
class TestCompactionConfig:
    """CompactionConfig validation and defaults."""

    def test_defaults(self) -> None:
        config = CompactionConfig()
        assert config.fill_threshold_percent == 80.0
        assert config.min_messages_to_compact == 4
        assert config.preserve_recent_turns == 3

    def test_threshold_bounds(self) -> None:
        CompactionConfig(fill_threshold_percent=0.1)
        CompactionConfig(fill_threshold_percent=100.0)
        with pytest.raises(ValidationError):
            CompactionConfig(fill_threshold_percent=0.0)
        with pytest.raises(ValidationError):
            CompactionConfig(fill_threshold_percent=100.1)

    def test_min_turns_minimum(self) -> None:
        CompactionConfig(min_messages_to_compact=2)
        with pytest.raises(ValidationError):
            CompactionConfig(min_messages_to_compact=1)

    def test_preserve_recent_minimum(self) -> None:
        CompactionConfig(preserve_recent_turns=1)
        with pytest.raises(ValidationError):
            CompactionConfig(preserve_recent_turns=0)

    def test_frozen(self) -> None:
        config = CompactionConfig()
        with pytest.raises(ValidationError):
            config.fill_threshold_percent = 90.0  # type: ignore[misc]


@pytest.mark.unit
class TestCompressionMetadata:
    """CompressionMetadata construction and defaults."""

    def test_defaults(self) -> None:
        meta = CompressionMetadata(
            compression_point=5,
            archived_turns=3,
            summary_tokens=100,
        )
        assert meta.compactions_performed == 1

    def test_custom_compactions(self) -> None:
        meta = CompressionMetadata(
            compression_point=10,
            archived_turns=8,
            summary_tokens=200,
            compactions_performed=3,
        )
        assert meta.compactions_performed == 3

    def test_frozen(self) -> None:
        meta = CompressionMetadata(
            compression_point=5,
            archived_turns=3,
            summary_tokens=100,
        )
        with pytest.raises(ValidationError):
            meta.archived_turns = 0  # type: ignore[misc]
