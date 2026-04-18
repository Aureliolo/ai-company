"""Tests for telemetry configuration."""

import pytest
from pydantic import ValidationError

from synthorg.telemetry.config import (
    MAX_STRING_LENGTH,
    TelemetryBackend,
    TelemetryConfig,
)


@pytest.mark.unit
class TestTelemetryConfig:
    """TelemetryConfig model validation."""

    def test_defaults(self) -> None:
        config = TelemetryConfig()
        assert config.enabled is False
        assert config.backend == TelemetryBackend.LOGFIRE
        assert config.heartbeat_interval_hours == 6.0
        assert config.environment == "dev"

    def test_enabled(self) -> None:
        config = TelemetryConfig(enabled=True)
        assert config.enabled is True

    def test_noop_backend(self) -> None:
        config = TelemetryConfig(
            enabled=True,
            backend=TelemetryBackend.NOOP,
        )
        assert config.backend == TelemetryBackend.NOOP

    def test_frozen(self) -> None:
        config = TelemetryConfig()
        with pytest.raises(Exception, match="frozen"):
            config.enabled = True  # type: ignore[misc]

    def test_token_field_is_removed(self) -> None:
        with pytest.raises(ValidationError):
            TelemetryConfig(token="anything")  # type: ignore[call-arg]

    @pytest.mark.parametrize("hours", [0.0, -1.0])
    def test_rejects_non_positive_heartbeat(self, hours: float) -> None:
        with pytest.raises(ValueError, match="greater than"):
            TelemetryConfig(heartbeat_interval_hours=hours)

    def test_rejects_excessive_heartbeat(self) -> None:
        with pytest.raises(ValueError, match="less than or equal"):
            TelemetryConfig(heartbeat_interval_hours=200.0)

    @pytest.mark.parametrize("tag", ["dev", "pre-release", "prod", "ci", "staging"])
    def test_environment_accepts_common_tags(self, tag: str) -> None:
        config = TelemetryConfig(environment=tag)
        assert config.environment == tag

    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_environment_rejects_blank(self, blank: str) -> None:
        with pytest.raises(ValidationError):
            TelemetryConfig(environment=blank)

    def test_environment_rejects_over_cap(self) -> None:
        """Reject values longer than :data:`MAX_STRING_LENGTH`."""
        with pytest.raises(ValidationError):
            TelemetryConfig(environment="x" * (MAX_STRING_LENGTH + 1))


@pytest.mark.unit
class TestTelemetryBackend:
    """TelemetryBackend enum values."""

    def test_values(self) -> None:
        assert TelemetryBackend.LOGFIRE.value == "logfire"
        assert TelemetryBackend.NOOP.value == "noop"

    def test_from_string(self) -> None:
        assert TelemetryBackend("logfire") == TelemetryBackend.LOGFIRE
        assert TelemetryBackend("noop") == TelemetryBackend.NOOP
