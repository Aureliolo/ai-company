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

    def test_config_environment_threaded_into_logfire_reporter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``config.environment`` must reach ``LogfireReporter.__init__``."""
        pytest.importorskip(
            "logfire",
            reason="logfire extra not installed in this environment",
        )
        from unittest.mock import patch

        monkeypatch.setenv(
            "SYNTHORG_LOGFIRE_PROJECT_TOKEN",
            "pylf_v1_test_000000000000000000000000000000000000000000",
        )
        config = TelemetryConfig(
            enabled=True,
            backend=TelemetryBackend.LOGFIRE,
            environment="staging",
        )

        import synthorg.telemetry.reporters.logfire as logfire_module

        with patch.object(logfire_module, "LogfireReporter") as mock_reporter_cls:
            create_reporter(config)

        mock_reporter_cls.assert_called_once_with(environment="staging")
