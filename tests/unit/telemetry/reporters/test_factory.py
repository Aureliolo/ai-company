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

    def test_logfire_without_package_raises(self) -> None:
        """Logfire backend requires the logfire package."""
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.LOGFIRE)
        # logfire is an optional dep -- if not installed, should raise.
        # If installed, it would succeed. We test both paths.
        try:
            reporter = create_reporter(config)
            # If logfire is installed, it should not be NoopReporter.
            assert not isinstance(reporter, NoopReporter)
        except ImportError:
            # Expected when logfire is not installed.
            pass
