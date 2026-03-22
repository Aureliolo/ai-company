"""Integration tests for sink routing with real file handlers."""

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from synthorg.observability.config import LogConfig, SinkConfig
from synthorg.observability.enums import LogLevel, SinkType
from synthorg.observability.setup import configure_logging


def _read_log(path: Path) -> str:
    """Read a log file, returning empty string if not found."""
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _configure_single_sink(
    log_dir: Path,
    file_path: str,
    *,
    level: LogLevel = LogLevel.DEBUG,
) -> None:
    """Configure logging with a single file sink for routing tests."""
    config = LogConfig(
        root_level=LogLevel.DEBUG,
        log_dir=str(log_dir),
        sinks=(
            SinkConfig(
                sink_type=SinkType.FILE,
                level=level,
                file_path=file_path,
                json_format=True,
            ),
        ),
    )
    configure_logging(config)


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    """Provide a temp directory for log files."""
    return tmp_path / "logs"


@pytest.mark.integration
class TestSinkRoutingIntegration:
    def test_security_routed_to_audit_log(self, log_dir: Path) -> None:
        config = LogConfig(
            root_level=LogLevel.DEBUG,
            log_dir=str(log_dir),
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="audit.log",
                    json_format=True,
                ),
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="synthorg.log",
                    json_format=True,
                ),
            ),
        )
        configure_logging(config)

        security_logger = logging.getLogger("synthorg.security.audit")
        core_logger = logging.getLogger("synthorg.core.task")

        security_logger.info("security event")
        core_logger.info("core event")

        audit_content = _read_log(log_dir / "audit.log")
        main_content = _read_log(log_dir / "synthorg.log")

        # Security event should be in audit.log
        assert "security event" in audit_content
        # Core event should NOT be in audit.log
        assert "core event" not in audit_content
        # Both should be in the catch-all synthorg.log
        assert "security event" in main_content
        assert "core event" in main_content

    def test_budget_routed_to_cost_usage_log(self, log_dir: Path) -> None:
        config = LogConfig(
            root_level=LogLevel.DEBUG,
            log_dir=str(log_dir),
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="cost_usage.log",
                    json_format=True,
                ),
            ),
        )
        configure_logging(config)

        budget_logger = logging.getLogger("synthorg.budget.tracker")
        engine_logger = logging.getLogger("synthorg.engine.run")

        budget_logger.info("cost recorded")
        engine_logger.info("engine event")

        cost_content = _read_log(log_dir / "cost_usage.log")
        assert "cost recorded" in cost_content
        assert "engine event" not in cost_content

    @pytest.mark.parametrize(
        ("sink_file", "routed", "excluded"),
        [
            pytest.param(
                "cost_usage.log",
                ("synthorg.providers.driver", "provider call"),
                ("synthorg.engine.run", "engine event"),
                id="providers-to-cost-usage",
            ),
            pytest.param(
                "audit.log",
                ("synthorg.hr.hiring", "hired agent"),
                ("synthorg.engine.run", "engine event"),
                id="hr-to-audit",
            ),
            pytest.param(
                "backup.log",
                ("synthorg.backup.scheduler", "backup completed"),
                ("synthorg.engine.run", "engine event"),
                id="backup-to-backup",
            ),
            pytest.param(
                "configuration.log",
                ("synthorg.settings.service", "setting changed"),
                ("synthorg.engine.run", "engine event"),
                id="settings-to-configuration",
            ),
            pytest.param(
                "configuration.log",
                ("synthorg.config.loader", "config loaded"),
                ("synthorg.engine.run", "engine event"),
                id="config-to-configuration",
            ),
            pytest.param(
                "audit.log",
                ("synthorg.observability.correlation", "correlation misuse"),
                ("synthorg.engine.run", "engine event"),
                id="observability-to-audit",
            ),
            pytest.param(
                "agent_activity.log",
                ("synthorg.communication.bus", "message dispatched"),
                ("synthorg.security.ops", "not here"),
                id="communication-to-agent-activity",
            ),
            pytest.param(
                "agent_activity.log",
                ("synthorg.tools.invoker", "tool invoked"),
                ("synthorg.security.ops", "not here"),
                id="tools-to-agent-activity",
            ),
            pytest.param(
                "agent_activity.log",
                ("synthorg.memory.retrieval", "memory retrieved"),
                ("synthorg.security.ops", "not here"),
                id="memory-to-agent-activity",
            ),
            pytest.param(
                "persistence.log",
                ("synthorg.persistence.sqlite", "row inserted"),
                ("synthorg.engine.run", "engine event"),
                id="persistence-to-persistence",
            ),
        ],
    )
    def test_single_sink_routing(
        self,
        log_dir: Path,
        sink_file: str,
        routed: tuple[str, str],
        excluded: tuple[str, str],
    ) -> None:
        """Verify that each logger prefix routes to its dedicated sink."""
        _configure_single_sink(log_dir, sink_file)

        routed_logger, routed_msg = routed
        excluded_logger, excluded_msg = excluded
        logging.getLogger(routed_logger).info(routed_msg)
        logging.getLogger(excluded_logger).info(excluded_msg)

        content = _read_log(log_dir / sink_file)
        assert routed_msg in content
        assert excluded_msg not in content

    def test_engine_routed_to_agent_activity_log(self, log_dir: Path) -> None:
        """Engine + core both route to agent_activity (multi-prefix sink)."""
        _configure_single_sink(log_dir, "agent_activity.log")

        engine_logger = logging.getLogger("synthorg.engine.runner")
        core_logger = logging.getLogger("synthorg.core.task")
        security_logger = logging.getLogger("synthorg.security.ops")

        engine_logger.info("agent ran")
        core_logger.info("task created")
        security_logger.info("not here")

        content = _read_log(log_dir / "agent_activity.log")
        assert "agent ran" in content
        assert "task created" in content
        assert "not here" not in content

    def test_routing_split_exclusivity(self, log_dir: Path) -> None:
        """Backup/settings must NOT appear in audit.log after the split."""
        config = LogConfig(
            root_level=LogLevel.DEBUG,
            log_dir=str(log_dir),
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="audit.log",
                    json_format=True,
                ),
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="backup.log",
                    json_format=True,
                ),
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="configuration.log",
                    json_format=True,
                ),
            ),
        )
        configure_logging(config)

        logging.getLogger("synthorg.backup.scheduler").info("backup event")
        logging.getLogger("synthorg.settings.service").info("settings event")
        logging.getLogger("synthorg.security.audit").info("security event")

        audit = _read_log(log_dir / "audit.log")
        backup = _read_log(log_dir / "backup.log")
        configuration = _read_log(log_dir / "configuration.log")

        # Security stays in audit
        assert "security event" in audit
        # Backup and settings must NOT leak into audit
        assert "backup event" not in audit
        assert "settings event" not in audit
        # Each goes to its dedicated sink
        assert "backup event" in backup
        assert "settings event" in configuration

    def test_errors_log_only_catches_error_and_above(
        self,
        log_dir: Path,
    ) -> None:
        _configure_single_sink(log_dir, "errors.log", level=LogLevel.ERROR)

        test_logger = logging.getLogger("synthorg.test")
        test_logger.info("info message")
        test_logger.warning("warning message")
        test_logger.error("error message")

        content = _read_log(log_dir / "errors.log")
        assert "info message" not in content
        assert "warning message" not in content
        assert "error message" in content
