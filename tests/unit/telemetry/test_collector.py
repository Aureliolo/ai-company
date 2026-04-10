"""Tests for the telemetry collector."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from synthorg.telemetry.collector import (
    TelemetryCollector,
    _HeartbeatParams,
    _SessionSummaryParams,
)
from synthorg.telemetry.config import TelemetryBackend, TelemetryConfig
from synthorg.telemetry.protocol import TelemetryEvent


@pytest.fixture(autouse=True)
def clear_synthorg_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SYNTHORG_TELEMETRY is unset so tests are deterministic."""
    monkeypatch.delenv("SYNTHORG_TELEMETRY", raising=False)


@pytest.mark.unit
class TestTelemetryCollector:
    """TelemetryCollector unit tests."""

    def test_disabled_by_default(self, tmp_path: Path) -> None:
        config = TelemetryConfig()
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        assert collector.enabled is False
        assert collector.deployment_id is None

    def test_generates_deployment_id(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        assert collector.deployment_id is not None
        assert len(collector.deployment_id) == 36  # UUID4 with hyphens: 8-4-4-4-12

    def test_persists_deployment_id(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        c1 = TelemetryCollector(config=config, data_dir=tmp_path)
        c2 = TelemetryCollector(config=config, data_dir=tmp_path)
        assert c1.deployment_id == c2.deployment_id

    def test_deployment_id_file_created(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        id_file = tmp_path / "telemetry_id"
        assert id_file.exists()
        assert id_file.read_text(encoding="utf-8").strip() == collector.deployment_id

    def test_deployment_id_read_error_generates_new(self, tmp_path: Path) -> None:
        """OSError on read falls back to generating a new ID."""
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        deployment_file = tmp_path / "telemetry_id"
        original_exists = Path.exists
        read_error = OSError("permission denied")

        def exists_side_effect(self: Path) -> bool:
            if self == deployment_file:
                raise read_error
            return original_exists(self)

        with patch.object(
            Path, "exists", autospec=True, side_effect=exists_side_effect
        ):
            collector = TelemetryCollector(config=config, data_dir=tmp_path)
            assert collector.deployment_id is not None
            assert len(collector.deployment_id) == 36  # UUID4 with hyphens: 8-4-4-4-12

    def test_deployment_id_write_error_still_returns(self, tmp_path: Path) -> None:
        """OSError on write still returns the generated ID."""
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        deployment_file = tmp_path / "telemetry_id"
        original_write_text = Path.write_text
        write_error = OSError("disk full")

        def write_text_side_effect(
            self: Path, data: str, encoding: str | None = None, **kwargs: object
        ) -> int:
            if self == deployment_file:
                raise write_error
            return original_write_text(self, data, encoding=encoding, **kwargs)  # type: ignore[arg-type]

        with patch.object(
            Path, "write_text", autospec=True, side_effect=write_text_side_effect
        ):
            collector = TelemetryCollector(config=config, data_dir=tmp_path)
            assert collector.deployment_id is not None
            assert len(collector.deployment_id) == 36  # UUID4 with hyphens: 8-4-4-4-12

    async def test_send_heartbeat_disabled(self, tmp_path: Path) -> None:
        """Heartbeat should be a no-op when disabled."""
        config = TelemetryConfig(enabled=False)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.send_heartbeat(
            _HeartbeatParams(agent_count=5),
        )

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

    async def test_start_and_shutdown(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.start()
        assert collector._heartbeat_task is not None
        await collector.shutdown()
        assert collector._heartbeat_task is None

    async def test_start_disabled_no_task(self, tmp_path: Path) -> None:
        config = TelemetryConfig(enabled=False)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)
        await collector.start()
        assert collector._heartbeat_task is None
        await collector.shutdown()


@pytest.mark.unit
class TestTelemetryCollectorWithMockReporter:
    """Collector tests with a mock reporter to verify event content."""

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

    async def test_reporter_exception_is_caught(self, tmp_path: Path) -> None:
        """Reporter raising Exception should not crash the collector."""
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)

        mock_reporter = AsyncMock()
        mock_reporter.report.side_effect = RuntimeError("network down")
        collector._reporter = mock_reporter

        # Should not raise.
        await collector.send_heartbeat(
            _HeartbeatParams(agent_count=1),
        )

        mock_reporter.report.assert_awaited_once()

    async def test_reporter_exception_does_not_block_subsequent(
        self, tmp_path: Path
    ) -> None:
        """After reporter failure, next send still works."""
        config = TelemetryConfig(enabled=True, backend=TelemetryBackend.NOOP)
        collector = TelemetryCollector(config=config, data_dir=tmp_path)

        mock_reporter = AsyncMock()
        mock_reporter.report.side_effect = [
            RuntimeError("fail"),
            None,
        ]
        collector._reporter = mock_reporter

        await collector.send_heartbeat()
        await collector.send_heartbeat()

        assert mock_reporter.report.await_count == 2


@pytest.mark.unit
class TestHeartbeatParams:
    """Frozen dataclass parameter bundles."""

    def test_defaults(self) -> None:
        p = _HeartbeatParams()
        assert p.agent_count == 0
        assert p.template_name == ""

    def test_frozen(self) -> None:
        p = _HeartbeatParams(agent_count=5)
        with pytest.raises(AttributeError, match="cannot assign"):
            p.agent_count = 10  # type: ignore[misc]


@pytest.mark.unit
class TestSessionSummaryParams:
    """Frozen dataclass parameter bundles."""

    def test_defaults(self) -> None:
        p = _SessionSummaryParams()
        assert p.tasks_created == 0
        assert p.provider_count == 0

    def test_frozen(self) -> None:
        p = _SessionSummaryParams(tasks_created=5)
        with pytest.raises(AttributeError, match="cannot assign"):
            p.tasks_created = 10  # type: ignore[misc]
