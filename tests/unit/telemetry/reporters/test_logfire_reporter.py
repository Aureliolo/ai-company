"""Regression tests for ``LogfireReporter``.

The collector's ``_send`` helper only flips the "delivered" return
value to ``False`` when ``report()`` raises. Earlier revisions of
the Logfire reporter logged and swallowed backend exceptions, so
failed writes surfaced as successful deliveries (``*_SENT``
debug events fired regardless). These tests lock in the
propagate-don't-swallow contract so that regression cannot sneak
back in. The reporter does **not** log ``TELEMETRY_REPORT_FAILED``
itself -- :meth:`TelemetryCollector._send` owns that alert and
duplicate logs would double-count failures.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from synthorg.telemetry.protocol import TelemetryEvent


def _event() -> TelemetryEvent:
    return TelemetryEvent(
        event_type="deployment.heartbeat",
        deployment_id="00000000-0000-0000-0000-000000000001",
        synthorg_version="test",
        python_version="3.14.0",
        os_platform="Linux",
        environment="test",
        timestamp=datetime.now(UTC),
        properties={},
    )


@pytest.mark.unit
class TestLogfireReporterReportRaises:
    """``report()`` must propagate backend failures, not swallow them."""

    @pytest.fixture
    def reporter(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        pytest.importorskip(
            "logfire",
            reason="logfire extra not installed in this environment",
        )
        from synthorg.telemetry.reporters.logfire import LogfireReporter

        # Reporter refuses to initialise without a token; a dummy
        # value exercises the construction path without enabling
        # delivery (the SDK handles an unauthenticated token by
        # dropping events).
        monkeypatch.setenv(
            "SYNTHORG_LOGFIRE_PROJECT_TOKEN",
            "pylf_v1_test_000000000000000000000000000000000000000000",
        )
        return LogfireReporter()

    async def test_backend_exception_propagates(
        self,
        reporter: Any,
    ) -> None:
        event = _event()
        with (
            patch.object(
                reporter._logfire,
                "info",
                side_effect=RuntimeError("backend down"),
            ),
            pytest.raises(RuntimeError, match="backend down"),
        ):
            await reporter.report(event)

    async def test_reporter_does_not_emit_report_failed_alert(
        self,
        reporter: Any,
    ) -> None:
        """The collector owns ``TELEMETRY_REPORT_FAILED``; reporter stays quiet."""
        event = _event()
        with (
            patch.object(
                reporter._logfire,
                "info",
                side_effect=RuntimeError("backend down"),
            ),
            patch(
                "synthorg.telemetry.reporters.logfire.logger",
            ) as mock_logger,
            pytest.raises(RuntimeError),
        ):
            await reporter.report(event)
        mock_logger.warning.assert_not_called()


@pytest.mark.unit
class TestLogfireReporterConfigure:
    """``configure()`` call shape: silences introspection + tags environment."""

    def test_configure_receives_inspect_arguments_false_and_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``configure()`` silences the introspection warning and tags env.

        The ``assert_called_once_with`` form locks the full kwarg
        set: an accidental extra kwarg (e.g. a future ``tags=...``
        slip) would break this test instead of sneaking past a
        partial-kwargs check.
        """
        pytest.importorskip(
            "logfire",
            reason="logfire extra not installed in this environment",
        )
        import logfire as real_logfire

        from synthorg.telemetry.reporters.logfire import LogfireReporter

        monkeypatch.setenv(
            "SYNTHORG_LOGFIRE_PROJECT_TOKEN",
            "pylf_v1_test_000000000000000000000000000000000000000000",
        )

        with patch.object(real_logfire, "configure") as mock_configure:
            LogfireReporter(environment="pre-release")

        mock_configure.assert_called_once()
        kwargs = mock_configure.call_args.kwargs
        expected_keys = {
            "token",
            "send_to_logfire",
            "service_name",
            "service_version",
            "environment",
            "inspect_arguments",
        }
        assert set(kwargs) == expected_keys, (
            f"configure() kwarg drift: got {set(kwargs)}, want {expected_keys}"
        )
        assert kwargs["inspect_arguments"] is False
        assert kwargs["environment"] == "pre-release"
        assert kwargs["service_name"] == "synthorg-telemetry"
        assert kwargs["send_to_logfire"] == "if-token-present"

    async def test_report_includes_environment_kwarg(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Per-record ``environment`` kwarg is attached to every ``info()`` call."""
        pytest.importorskip(
            "logfire",
            reason="logfire extra not installed in this environment",
        )
        import logfire as real_logfire

        from synthorg.telemetry.reporters.logfire import LogfireReporter

        monkeypatch.setenv(
            "SYNTHORG_LOGFIRE_PROJECT_TOKEN",
            "pylf_v1_test_000000000000000000000000000000000000000000",
        )
        with patch.object(real_logfire, "configure"):
            reporter = LogfireReporter(environment="ci")

        event = TelemetryEvent(
            event_type="deployment.heartbeat",
            deployment_id="00000000-0000-0000-0000-000000000002",
            synthorg_version="test",
            python_version="3.14.0",
            os_platform="Linux",
            environment="ci",
            timestamp=datetime.now(UTC),
            properties={},
        )
        with patch.object(reporter._logfire, "info") as mock_info:
            await reporter.report(event)

        mock_info.assert_called_once()
        kwargs = mock_info.call_args.kwargs
        assert kwargs["environment"] == "ci"
        assert kwargs["deployment_id"] == "00000000-0000-0000-0000-000000000002"
