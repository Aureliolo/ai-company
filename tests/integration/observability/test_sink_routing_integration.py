"""Integration tests for sink routing with real file handlers."""

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from ai_company.observability.config import LogConfig, SinkConfig
from ai_company.observability.enums import LogLevel, SinkType
from ai_company.observability.setup import configure_logging

pytestmark = pytest.mark.timeout(30)


def _read_log(path: Path) -> str:
    """Read a log file, returning empty string if not found."""
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


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
                    file_path="ai_company.log",
                    json_format=True,
                ),
            ),
        )
        configure_logging(config)

        security_logger = logging.getLogger("ai_company.security.audit")
        core_logger = logging.getLogger("ai_company.core.task")

        security_logger.info("security event")
        core_logger.info("core event")

        audit_content = _read_log(log_dir / "audit.log")
        main_content = _read_log(log_dir / "ai_company.log")

        # Security event should be in audit.log
        assert "security event" in audit_content
        # Core event should NOT be in audit.log
        assert "core event" not in audit_content
        # Both should be in the catch-all ai_company.log
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

        budget_logger = logging.getLogger("ai_company.budget.tracker")
        engine_logger = logging.getLogger("ai_company.engine.run")

        budget_logger.info("cost recorded")
        engine_logger.info("engine event")

        cost_content = _read_log(log_dir / "cost_usage.log")
        assert "cost recorded" in cost_content
        assert "engine event" not in cost_content

    def test_engine_routed_to_agent_activity_log(self, log_dir: Path) -> None:
        config = LogConfig(
            root_level=LogLevel.DEBUG,
            log_dir=str(log_dir),
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="agent_activity.log",
                    json_format=True,
                ),
            ),
        )
        configure_logging(config)

        engine_logger = logging.getLogger("ai_company.engine.runner")
        core_logger = logging.getLogger("ai_company.core.task")
        security_logger = logging.getLogger("ai_company.security.ops")

        engine_logger.info("agent ran")
        core_logger.info("task created")
        security_logger.info("not here")

        content = _read_log(log_dir / "agent_activity.log")
        assert "agent ran" in content
        assert "task created" in content
        assert "not here" not in content

    def test_errors_log_only_catches_error_and_above(self, log_dir: Path) -> None:
        config = LogConfig(
            root_level=LogLevel.DEBUG,
            log_dir=str(log_dir),
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.ERROR,
                    file_path="errors.log",
                    json_format=True,
                ),
            ),
        )
        configure_logging(config)

        test_logger = logging.getLogger("ai_company.test")
        test_logger.info("info message")
        test_logger.warning("warning message")
        test_logger.error("error message")

        content = _read_log(log_dir / "errors.log")
        assert "info message" not in content
        assert "warning message" not in content
        assert "error message" in content
