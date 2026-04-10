"""Tests for the noop telemetry reporter."""

from datetime import UTC, datetime

import pytest

from synthorg.telemetry.protocol import TelemetryEvent, TelemetryReporter
from synthorg.telemetry.reporters.noop import NoopReporter


@pytest.mark.unit
class TestNoopReporter:
    """NoopReporter does nothing, safely."""

    def test_is_telemetry_reporter(self) -> None:
        assert isinstance(NoopReporter(), TelemetryReporter)

    async def test_report(self) -> None:
        reporter = NoopReporter()
        event = TelemetryEvent(
            event_type="deployment.heartbeat",
            deployment_id="test-id",
            synthorg_version="0.6.4",
            python_version="3.14.0",
            os_platform="Linux",
            timestamp=datetime.now(UTC),
        )
        await reporter.report(event)

    async def test_flush(self) -> None:
        await NoopReporter().flush()

    async def test_shutdown(self) -> None:
        await NoopReporter().shutdown()
