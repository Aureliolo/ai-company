"""Tests for the telemetry reporter factory."""

import pytest

from synthorg.telemetry.config import TelemetryBackend, TelemetryConfig
from synthorg.telemetry.reporters import create_reporter
from synthorg.telemetry.reporters.noop import NoopReporter


@pytest.mark.unit
class TestCreateReporter:
    """Reporter factory tests."""

    def test_disabled_returns_noop(self) -> None:
        config = TelemetryConfig(enabled=False)
        reporter = create_reporter(config)
        assert isinstance(reporter, NoopReporter)

    def test_noop_backend_returns_noop(self) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        reporter = create_reporter(config)
        assert isinstance(reporter, NoopReporter)

    def test_logfire_backend_returns_reporter_or_noop(self) -> None:
        """Logfire backend returns a reporter or NoopReporter."""
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.LOGFIRE)
        reporter = create_reporter(config)
        # Factory catches exceptions and falls back to NoopReporter
        # when logfire is not installed or init fails.
        reporter_name = type(reporter).__name__
        assert reporter_name in {"LogfireReporter", "NoopReporter"}
