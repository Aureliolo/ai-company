"""Tests for telemetry protocol and event model."""

import math
from datetime import UTC, datetime

import pytest

from synthorg.telemetry.protocol import TelemetryEvent, TelemetryReporter
from synthorg.telemetry.reporters.noop import NoopReporter


@pytest.mark.unit
class TestTelemetryEvent:
    """TelemetryEvent model validation."""

    def test_minimal_event(self) -> None:
        event = TelemetryEvent(
            event_type="deployment.heartbeat",
            deployment_id="abc-123",
            synthorg_version="0.6.4",
            python_version="3.14.0",
            os_platform="Linux",
            timestamp=datetime.now(UTC),
        )
        assert event.event_type == "deployment.heartbeat"
        assert event.properties == {}

    def test_event_with_properties(self) -> None:
        event = TelemetryEvent(
            event_type="deployment.heartbeat",
            deployment_id="abc-123",
            synthorg_version="0.6.4",
            python_version="3.14.0",
            os_platform="Linux",
            timestamp=datetime.now(UTC),
            properties={
                "agent_count": 5,
                "uptime_hours": 12.5,
                "template_name": "startup",
                "graceful": True,
            },
        )
        assert event.properties["agent_count"] == 5
        assert event.properties["uptime_hours"] == 12.5
        assert event.properties["template_name"] == "startup"
        assert event.properties["graceful"] is True

    def test_frozen(self) -> None:
        event = TelemetryEvent(
            event_type="deployment.heartbeat",
            deployment_id="abc-123",
            synthorg_version="0.6.4",
            python_version="3.14.0",
            os_platform="Linux",
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(Exception, match="frozen"):
            event.event_type = "changed"  # type: ignore[misc]

    def test_rejects_nan(self) -> None:
        with pytest.raises(ValueError, match="Input should be a finite number"):
            TelemetryEvent(
                event_type="deployment.heartbeat",
                deployment_id="abc-123",
                synthorg_version="0.6.4",
                python_version="3.14.0",
                os_platform="Linux",
                timestamp=datetime.now(UTC),
                properties={"bad": math.nan},
            )

    def test_rejects_inf(self) -> None:
        with pytest.raises(ValueError, match="Input should be a finite number"):
            TelemetryEvent(
                event_type="deployment.heartbeat",
                deployment_id="abc-123",
                synthorg_version="0.6.4",
                python_version="3.14.0",
                os_platform="Linux",
                timestamp=datetime.now(UTC),
                properties={"bad": math.inf},
            )


@pytest.mark.unit
class TestTelemetryReporterProtocol:
    """TelemetryReporter protocol compliance."""

    def test_noop_is_reporter(self) -> None:
        assert isinstance(NoopReporter(), TelemetryReporter)

    @pytest.mark.asyncio
    async def test_noop_report_is_silent(self) -> None:
        reporter = NoopReporter()
        event = TelemetryEvent(
            event_type="deployment.heartbeat",
            deployment_id="abc-123",
            synthorg_version="0.6.4",
            python_version="3.14.0",
            os_platform="Linux",
            timestamp=datetime.now(UTC),
        )
        await reporter.report(event)
        await reporter.flush()
        await reporter.shutdown()
