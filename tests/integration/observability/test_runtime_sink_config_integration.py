"""Integration tests for runtime sink configuration (hot reload)."""

import json
import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from synthorg.observability.config import DEFAULT_SINKS, LogConfig
from synthorg.observability.enums import LogLevel
from synthorg.observability.setup import configure_logging
from synthorg.observability.sink_config_builder import build_log_config_from_settings


def _read_log(path: Path) -> str:
    """Read a log file, returning empty string if not found."""
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _configure_defaults(log_dir: Path) -> None:
    """Configure logging with all DEFAULT_SINKS."""
    config = LogConfig(
        root_level=LogLevel.DEBUG,
        sinks=DEFAULT_SINKS,
        log_dir=str(log_dir),
    )
    configure_logging(config)


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    """Provide a temp directory for log files."""
    return tmp_path / "logs"


@pytest.mark.integration
class TestHotReloadDisableSink:
    """Disabling a file sink stops messages from reaching it."""

    def test_disable_audit_sink_stops_messages(self, log_dir: Path) -> None:
        _configure_defaults(log_dir)

        security_logger = logging.getLogger("synthorg.security.audit")
        security_logger.info("before disable")

        content = _read_log(log_dir / "audit.log")
        assert "before disable" in content

        # Hot reload: disable audit.log
        overrides = json.dumps({"audit.log": {"enabled": False}})
        result = build_log_config_from_settings(
            root_level=LogLevel.DEBUG,
            enable_correlation=True,
            sink_overrides_json=overrides,
            custom_sinks_json="[]",
            log_dir=str(log_dir),
        )
        configure_logging(result.config)

        security_logger.info("after disable")

        content = _read_log(log_dir / "audit.log")
        assert "before disable" in content
        assert "after disable" not in content


@pytest.mark.integration
class TestHotReloadLevelChange:
    """Changing a sink's level filters messages appropriately."""

    def test_raise_level_filters_lower_messages(self, log_dir: Path) -> None:
        _configure_defaults(log_dir)

        security_logger = logging.getLogger("synthorg.security.scanner")
        security_logger.info("info before level change")

        content = _read_log(log_dir / "audit.log")
        assert "info before level change" in content

        # Hot reload: raise audit.log to ERROR
        overrides = json.dumps({"audit.log": {"level": "error"}})
        result = build_log_config_from_settings(
            root_level=LogLevel.DEBUG,
            enable_correlation=True,
            sink_overrides_json=overrides,
            custom_sinks_json="[]",
            log_dir=str(log_dir),
        )
        configure_logging(result.config)

        security_logger.info("info after level change")
        security_logger.error("error after level change")

        content = _read_log(log_dir / "audit.log")
        assert "info after level change" not in content
        assert "error after level change" in content


@pytest.mark.integration
class TestHotReloadAddCustomSink:
    """Adding a custom sink routes messages to the new file."""

    def test_custom_sink_receives_messages(self, log_dir: Path) -> None:
        _configure_defaults(log_dir)

        custom = json.dumps(
            [
                {
                    "file_path": "custom_test.log",
                    "level": "debug",
                }
            ]
        )
        result = build_log_config_from_settings(
            root_level=LogLevel.DEBUG,
            enable_correlation=True,
            sink_overrides_json="{}",
            custom_sinks_json=custom,
            log_dir=str(log_dir),
        )
        configure_logging(result.config)

        test_logger = logging.getLogger("synthorg.test.custom")
        test_logger.info("custom sink message")

        content = _read_log(log_dir / "custom_test.log")
        assert "custom sink message" in content

    def test_custom_sink_with_routing_filters(self, log_dir: Path) -> None:
        custom = json.dumps(
            [
                {
                    "file_path": "routed_custom.log",
                    "level": "debug",
                    "routing_prefixes": ["synthorg.tools."],
                }
            ]
        )
        result = build_log_config_from_settings(
            root_level=LogLevel.DEBUG,
            enable_correlation=True,
            sink_overrides_json="{}",
            custom_sinks_json=custom,
            log_dir=str(log_dir),
        )
        configure_logging(
            result.config,
            routing_overrides=dict(result.routing_overrides),
        )

        tools_logger = logging.getLogger("synthorg.tools.invoker")
        engine_logger = logging.getLogger("synthorg.engine.run")
        tools_logger.info("tool invoked")
        engine_logger.info("engine event")

        content = _read_log(log_dir / "routed_custom.log")
        assert "tool invoked" in content
        assert "engine event" not in content


@pytest.mark.integration
class TestHotReloadModuleLevelLoggers:
    """Module-level loggers route correctly after pipeline rebuild."""

    def test_module_level_logger_routes_after_rebuild(
        self,
        log_dir: Path,
    ) -> None:
        # Create logger BEFORE first configure
        budget_logger = logging.getLogger("synthorg.budget.tracker")

        _configure_defaults(log_dir)
        budget_logger.info("first message")

        content = _read_log(log_dir / "cost_usage.log")
        assert "first message" in content

        # Rebuild with modified config
        overrides = json.dumps({"cost_usage.log": {"level": "error"}})
        result = build_log_config_from_settings(
            root_level=LogLevel.DEBUG,
            enable_correlation=True,
            sink_overrides_json=overrides,
            custom_sinks_json="[]",
            log_dir=str(log_dir),
        )
        configure_logging(result.config)

        # Same logger still works after rebuild
        budget_logger.info("info after rebuild")
        budget_logger.error("error after rebuild")

        content = _read_log(log_dir / "cost_usage.log")
        assert "info after rebuild" not in content
        assert "error after rebuild" in content


@pytest.mark.integration
class TestHotReloadPreservesMessages:
    """Messages emitted before and after rebuild both reach their sinks."""

    def test_messages_before_and_after_rebuild(self, log_dir: Path) -> None:
        _configure_defaults(log_dir)

        main_logger = logging.getLogger("synthorg.core.test")
        main_logger.info("message before rebuild")

        # Rebuild with same config (no changes)
        result = build_log_config_from_settings(
            root_level=LogLevel.DEBUG,
            enable_correlation=True,
            sink_overrides_json="{}",
            custom_sinks_json="[]",
            log_dir=str(log_dir),
        )
        configure_logging(result.config)

        main_logger.info("message after rebuild")

        # Both messages in the catch-all synthorg.log
        content = _read_log(log_dir / "synthorg.log")
        assert "message before rebuild" in content
        assert "message after rebuild" in content
