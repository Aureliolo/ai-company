"""Regression tests for ``LogfireReporter``.

The collector's ``_send`` helper only flips the "delivered" return
value to ``False`` when ``report()`` raises. Earlier revisions of
the Logfire reporter logged and swallowed backend exceptions, so
failed writes surfaced as successful deliveries (``*_SENT``
debug events fired regardless). These tests lock in the re-raise
contract so that regression cannot sneak back in.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from synthorg.observability.events.telemetry import TELEMETRY_REPORT_FAILED
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
    """``report()`` must re-raise backend failures after logging."""

    @pytest.fixture
    def reporter(self) -> Any:
        pytest.importorskip(
            "logfire",
            reason="logfire extra not installed in this environment",
        )
        from synthorg.telemetry.reporters.logfire import LogfireReporter

        return LogfireReporter()

    async def test_backend_exception_is_logged_and_reraised(
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
            patch(
                "synthorg.telemetry.reporters.logfire.logger",
            ) as mock_logger,
            pytest.raises(RuntimeError, match="backend down"),
        ):
            await reporter.report(event)
        mock_logger.warning.assert_called_once()
        call = mock_logger.warning.call_args
        assert call.args[0] == TELEMETRY_REPORT_FAILED
        assert call.kwargs["event_type"] == event.event_type
        assert call.kwargs["error_type"] == "RuntimeError"
        assert call.kwargs["exc_info"] is True
