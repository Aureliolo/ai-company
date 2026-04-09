"""Tests for telemetry configuration."""

import pytest

from synthorg.telemetry.config import TelemetryBackend, TelemetryConfig


@pytest.mark.unit
class TestTelemetryConfig:
    """TelemetryConfig model validation."""

    def test_defaults(self) -> None:
        config = TelemetryConfig()
        assert config.enabled is False
        assert config.backend == TelemetryBackend.LOGFIRE
        assert config.heartbeat_interval_hours == 6.0
        assert config.token is None

    def test_enabled_with_token(self) -> None:
        config = TelemetryConfig(
            enabled=True,
            token="test-token-123",
        )
        assert config.enabled is True
        assert config.token == "test-token-123"

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

    @pytest.mark.parametrize("hours", [0.0, -1.0])
    def test_rejects_non_positive_heartbeat(self, hours: float) -> None:
        with pytest.raises(ValueError, match="greater than"):
            TelemetryConfig(heartbeat_interval_hours=hours)

    def test_rejects_excessive_heartbeat(self) -> None:
        with pytest.raises(ValueError, match="less than or equal"):
            TelemetryConfig(heartbeat_interval_hours=200.0)


@pytest.mark.unit
class TestTelemetryBackend:
    """TelemetryBackend enum values."""

    def test_values(self) -> None:
        assert TelemetryBackend.LOGFIRE.value == "logfire"
        assert TelemetryBackend.NOOP.value == "noop"

    def test_from_string(self) -> None:
        assert TelemetryBackend("logfire") == TelemetryBackend.LOGFIRE
        assert TelemetryBackend("noop") == TelemetryBackend.NOOP
