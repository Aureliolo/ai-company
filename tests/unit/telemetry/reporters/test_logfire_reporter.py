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
        timestamp=datetime.now(UTC),
        properties={},
    )


@pytest.mark.unit
class TestLogfireReporterReportRaises:
    """``report()`` must propagate backend failures, not swallow them."""

    @pytest.fixture
    def reporter(self) -> Any:
        pytest.importorskip(
            "logfire",
            reason="logfire extra not installed in this environment",
        )
        from synthorg.telemetry.reporters.logfire import LogfireReporter

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
