"""Tests for the telemetry collector."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from synthorg.telemetry.collector import (
    TelemetryCollector,
    _HeartbeatParams,
    _SessionSummaryParams,
)
from synthorg.telemetry.config import TelemetryBackend, TelemetryConfig
from synthorg.telemetry.protocol import TelemetryEvent


@pytest.mark.unit
class TestTelemetryCollector:
    """TelemetryCollector unit tests."""

    def test_disabled_by_default(self, tmp_path: Path) -> None:
        config = TelemetryConfig()
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        assert collector.enabled is False

    def test_generates_deployment_id(self, tmp_path: Path) -> None:
        config = TelemetryConfig()
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        assert len(collector.deployment_id) == 36  # UUID format

    def test_persists_deployment_id(self, tmp_path: Path) -> None:
        config = TelemetryConfig()
        c1 = TelemetryCollector(config=config, data_dir=tmp_path)
        c2 = TelemetryCollector(config=config, data_dir=tmp_path)
        assert c1.deployment_id == c2.deployment_id

    def test_deployment_id_file_created(self, tmp_path: Path) -> None:
        config = TelemetryConfig()
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        id_file = tmp_path / "telemetry_id"
        assert id_file.exists()
        assert id_file.read_text(encoding="utf-8").strip() == collector.deployment_id

    @pytest.mark.asyncio
    async def test_send_heartbeat_disabled(self, tmp_path: Path) -> None:
        """Heartbeat should be a no-op when disabled."""
        config = TelemetryConfig(enabled=False)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.send_heartbeat(
            _HeartbeatParams(agent_count=5),
        )

    @pytest.mark.asyncio
    async def test_send_heartbeat_enabled_noop(self, tmp_path: Path) -> None:
        """Heartbeat with noop backend should succeed silently."""
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.send_heartbeat(
            _HeartbeatParams(
                agent_count=5,
                department_count=3,
                template_name="startup",
            ),
        )

    @pytest.mark.asyncio
    async def test_send_session_summary_noop(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.send_session_summary(
            _SessionSummaryParams(
                tasks_created=10,
                tasks_completed=8,
                tasks_failed=2,
                provider_count=2,
            ),
        )

    @pytest.mark.asyncio
    async def test_start_and_shutdown(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.start()
        assert collector._heartbeat_task is not None
        await collector.shutdown()
        assert collector._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_start_disabled_no_task(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=False)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.start()
        assert collector._heartbeat_task is None
        await collector.shutdown()


@pytest.mark.unit
class TestTelemetryCollectorWithMockReporter:
    """Collector tests with a mock reporter to verify event content."""

    @pytest.mark.asyncio
    async def test_heartbeat_event_structure(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)

        mock_reporter = AsyncMock()
        collector._reporter = mock_reporter

        await collector.send_heartbeat(
            _HeartbeatParams(
                agent_count=5,
                department_count=3,
                team_count=1,
                template_name="startup",
                persistence_backend="sqlite",
                memory_backend="mem0",
                features_enabled="meeting",
            ),
        )

        mock_reporter.report.assert_awaited_once()
        event: TelemetryEvent = mock_reporter.report.call_args[0][0]
        assert event.event_type == "deployment.heartbeat"
        assert event.deployment_id == collector.deployment_id
        assert event.properties["agent_count"] == 5
        assert event.properties["department_count"] == 3
        assert event.properties["template_name"] == "startup"
        assert "uptime_hours" in event.properties
        assert isinstance(event.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_session_summary_event_structure(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)

        mock_reporter = AsyncMock()
        collector._reporter = mock_reporter

        await collector.send_session_summary(
            _SessionSummaryParams(
                tasks_created=10,
                tasks_completed=8,
                tasks_failed=2,
                error_rate_limit=1,
                provider_count=2,
                meetings_held=3,
            ),
        )

        mock_reporter.report.assert_awaited_once()
        event: TelemetryEvent = mock_reporter.report.call_args[0][0]
        assert event.event_type == "deployment.session_summary"
        assert event.properties["tasks_created"] == 10
        assert event.properties["tasks_completed"] == 8
        assert event.properties["meetings_held"] == 3
