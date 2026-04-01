"""Tests for rotation overrides and field type rejection in sink builder."""

import json

import pytest

from synthorg.observability.enums import LogLevel
from synthorg.observability.sink_config_builder import (
    SinkBuildResult,
    build_log_config_from_settings,
)


def _build(
    *,
    overrides: str = "{}",
    custom: str = "[]",
    root_level: LogLevel = LogLevel.DEBUG,
    enable_correlation: bool = True,
) -> SinkBuildResult:
    """Shorthand builder with sensible defaults."""
    return build_log_config_from_settings(
        root_level=root_level,
        enable_correlation=enable_correlation,
        sink_overrides_json=overrides,
        custom_sinks_json=custom,
    )


@pytest.mark.unit
class TestCompressRotatedOverrides:
    """compress_rotated can be overridden in rotation settings."""

    def test_compress_rotated_override(self) -> None:
        overrides = json.dumps(
            {
                "audit.log": {
                    "rotation": {"compress_rotated": True},
                },
            }
        )
        result = _build(overrides=overrides)
        audit = next(s for s in result.config.sinks if s.file_path == "audit.log")
        assert audit.rotation is not None
        assert audit.rotation.compress_rotated is True

    def test_compress_rotated_with_external_rejects(self) -> None:
        overrides = json.dumps(
            {
                "audit.log": {
                    "rotation": {
                        "strategy": "external",
                        "compress_rotated": True,
                    },
                },
            }
        )
        with pytest.raises(ValueError, match="compress_rotated"):
            _build(overrides=overrides)


@pytest.mark.unit
class TestBooleanRejection:
    """Boolean values are rejected for integer and number fields."""

    def test_http_batch_size_boolean_raises(self) -> None:
        custom = json.dumps(
            [
                {
                    "sink_type": "http",
                    "http_url": "http://example.com/logs",
                    "http_batch_size": True,
                }
            ]
        )
        with pytest.raises(ValueError, match="integer"):
            _build(custom=custom)
