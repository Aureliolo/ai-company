"""Tests for logging system setup."""

import json
import logging
from typing import TYPE_CHECKING

import pytest
import structlog

if TYPE_CHECKING:
    from pathlib import Path

from synthorg.observability.config import LogConfig, SinkConfig
from synthorg.observability.correlation import bind_correlation_id
from synthorg.observability.enums import LogLevel, SinkType
from synthorg.observability.setup import (
    _DEFAULT_LOGGER_LEVELS,
    _apply_console_level_override,
    _attach_handlers,
    configure_logging,
)

pytestmark = pytest.mark.timeout(30)


def _console_only_config() -> LogConfig:
    return LogConfig(
        sinks=(
            SinkConfig(
                sink_type=SinkType.CONSOLE,
                level=LogLevel.DEBUG,
                json_format=False,
            ),
        ),
    )


def _file_config(tmp_path: Path) -> LogConfig:
    return LogConfig(
        sinks=(
            SinkConfig(
                sink_type=SinkType.FILE,
                level=LogLevel.DEBUG,
                file_path="test.log",
                json_format=True,
            ),
        ),
        log_dir=str(tmp_path),
    )


@pytest.mark.unit
class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_default_config_creates_handlers(self) -> None:
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 8

    def test_custom_config_creates_handlers(self) -> None:
        configure_logging(_console_only_config())
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_idempotent_no_duplicate_handlers(self) -> None:
        configure_logging(_console_only_config())
        configure_logging(_console_only_config())
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_root_logger_set_to_debug(self) -> None:
        configure_logging(_console_only_config())
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_custom_root_level_applied(self) -> None:
        config = LogConfig(
            sinks=(_console_only_config().sinks),
            root_level=LogLevel.WARNING,
        )
        configure_logging(config)
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_default_logger_levels_applied(self) -> None:
        configure_logging(_console_only_config())
        for name, level in _DEFAULT_LOGGER_LEVELS:
            logger = logging.getLogger(name)
            assert logger.level == getattr(logging, level.value), (
                f"{name} expected {level.value}"
            )

    def test_config_overrides_default_levels(self) -> None:
        config = LogConfig(
            sinks=(
                SinkConfig(
                    sink_type=SinkType.CONSOLE,
                    level=LogLevel.DEBUG,
                    json_format=False,
                ),
            ),
            logger_levels=(("synthorg.engine", LogLevel.CRITICAL),),
        )
        configure_logging(config)
        logger = logging.getLogger("synthorg.engine")
        assert logger.level == logging.CRITICAL

    def test_none_config_uses_defaults(self) -> None:
        configure_logging(None)
        root = logging.getLogger()
        assert len(root.handlers) == 8


@pytest.mark.unit
class TestConfigureLoggingFileOutput:
    """Tests for file output from configure_logging."""

    def test_file_sink_creates_log_file(self, tmp_path: Path) -> None:
        configure_logging(_file_config(tmp_path))
        logger = logging.getLogger("test.file_output")
        logger.info("hello file")
        log_file = tmp_path / "test.log"
        assert log_file.exists()

    def test_json_output_is_parseable(self, tmp_path: Path) -> None:
        configure_logging(_file_config(tmp_path))
        logger = logging.getLogger("test.json_output")
        logger.info("json test message")
        log_file = tmp_path / "test.log"
        content = log_file.read_text().strip()
        assert content
        record = json.loads(content)
        assert record["event"] == "json test message"


@pytest.mark.unit
class TestStdlibBridge:
    """Tests for stdlib logging bridge (foreign log records)."""

    def test_stdlib_logger_captured(self, tmp_path: Path) -> None:
        configure_logging(_file_config(tmp_path))
        stdlib_logger = logging.getLogger("uvicorn.access")
        stdlib_logger.setLevel(logging.DEBUG)
        stdlib_logger.info("stdlib bridge test")
        log_file = tmp_path / "test.log"
        content = log_file.read_text().strip()
        assert content
        record = json.loads(content)
        assert record["event"] == "stdlib bridge test"


@pytest.mark.unit
class TestDefaultLoggerLevels:
    """Tests for the _DEFAULT_LOGGER_LEVELS constant."""

    def test_has_twelve_entries(self) -> None:
        assert len(_DEFAULT_LOGGER_LEVELS) == 12

    def test_all_start_with_synthorg(self) -> None:
        for name, _ in _DEFAULT_LOGGER_LEVELS:
            assert name.startswith("synthorg."), name

    def test_all_levels_are_valid(self) -> None:
        for _, level in _DEFAULT_LOGGER_LEVELS:
            assert isinstance(level, LogLevel)


@pytest.mark.unit
class TestSanitizationPipeline:
    """E2E tests for sensitive field sanitization through the pipeline."""

    def test_sensitive_fields_redacted_in_log_file(self, tmp_path: Path) -> None:
        configure_logging(_file_config(tmp_path))
        logger = structlog.get_logger("test.sanitize")
        logger.info("login attempt", password="s3cret", user="alice")
        log_file = tmp_path / "test.log"
        content = log_file.read_text().strip()
        assert content
        record = json.loads(content)
        assert record["password"] == "**REDACTED**"
        assert record["user"] == "alice"


@pytest.mark.unit
class TestCorrelationPipeline:
    """E2E tests for correlation IDs appearing in log file output."""

    def test_correlation_id_in_log_output(self, tmp_path: Path) -> None:
        configure_logging(_file_config(tmp_path))
        bind_correlation_id(request_id="test-req-123")
        logger = structlog.get_logger("test.correlation")
        logger.info("correlated event")
        log_file = tmp_path / "test.log"
        content = log_file.read_text().strip()
        assert content
        record = json.loads(content)
        assert record["request_id"] == "test-req-123"


@pytest.mark.unit
class TestApplyConsoleLevelOverride:
    """Tests for _apply_console_level_override."""

    def test_no_env_var_returns_unchanged(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("SYNTHORG_LOG_LEVEL", raising=False)
        config = _console_only_config()
        result = _apply_console_level_override(config)
        assert result is config

    def test_valid_level_overrides_console_sink(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SYNTHORG_LOG_LEVEL", "warning")
        config = _console_only_config()
        result = _apply_console_level_override(config)
        assert result.sinks[0].level == LogLevel.WARNING

    def test_invalid_level_falls_back_to_info(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("SYNTHORG_LOG_LEVEL", "bogus")
        config = _console_only_config()
        result = _apply_console_level_override(config)
        assert result.sinks[0].level == LogLevel.INFO
        captured = capsys.readouterr()
        assert "Invalid SYNTHORG_LOG_LEVEL" in captured.err

    def test_file_sinks_unaffected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SYNTHORG_LOG_LEVEL", "error")
        config = LogConfig(
            sinks=(
                SinkConfig(
                    sink_type=SinkType.CONSOLE,
                    level=LogLevel.INFO,
                    json_format=False,
                ),
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="test.log",
                    json_format=True,
                ),
            ),
        )
        result = _apply_console_level_override(config)
        assert result.sinks[0].level == LogLevel.ERROR
        assert result.sinks[1].level == LogLevel.DEBUG

    def test_no_console_sink_warns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("SYNTHORG_LOG_LEVEL", "debug")
        config = LogConfig(
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.INFO,
                    file_path="only-file.log",
                    json_format=True,
                ),
            ),
        )
        result = _apply_console_level_override(config)
        assert result.sinks[0].level == LogLevel.INFO
        captured = capsys.readouterr()
        assert "no CONSOLE sink found" in captured.err


@pytest.mark.unit
class TestCriticalSinkFailure:
    """Tests for critical sink failure enforcement in _attach_handlers."""

    def test_non_critical_sink_failure_skipped(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-critical sink failure is tolerated."""
        import synthorg.observability.setup as _setup

        config = LogConfig(
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.DEBUG,
                    file_path="debug.log",
                    json_format=True,
                ),
            ),
        )

        def _boom(**_kwargs: object) -> None:
            msg = "disk full"
            raise OSError(msg)

        monkeypatch.setattr(_setup, "build_handler", _boom)
        root = logging.getLogger()
        initial_count = len(root.handlers)
        # Should not raise -- non-critical sink failures are skipped.
        _attach_handlers(config, root, [])
        assert len(root.handlers) == initial_count

    def test_critical_audit_sink_failure_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """audit.log failure raises RuntimeError."""
        import synthorg.observability.setup as _setup

        config = LogConfig(
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.INFO,
                    file_path="audit.log",
                    json_format=True,
                ),
            ),
        )

        def _boom(**_kwargs: object) -> None:
            msg = "permission denied"
            raise OSError(msg)

        monkeypatch.setattr(_setup, "build_handler", _boom)
        root = logging.getLogger()
        with pytest.raises(RuntimeError, match=r"audit\.log"):
            _attach_handlers(config, root, [])

    def test_critical_access_sink_failure_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """access.log failure raises RuntimeError."""
        import synthorg.observability.setup as _setup

        config = LogConfig(
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.INFO,
                    file_path="access.log",
                    json_format=True,
                ),
            ),
        )

        def _boom(**_kwargs: object) -> None:
            msg = "permission denied"
            raise OSError(msg)

        monkeypatch.setattr(_setup, "build_handler", _boom)
        root = logging.getLogger()
        with pytest.raises(RuntimeError, match=r"access\.log"):
            _attach_handlers(config, root, [])

    def test_critical_sink_failure_chains_original_cause(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """RuntimeError chains the original OS error."""
        import synthorg.observability.setup as _setup

        config = LogConfig(
            sinks=(
                SinkConfig(
                    sink_type=SinkType.FILE,
                    level=LogLevel.INFO,
                    file_path="audit.log",
                    json_format=True,
                ),
            ),
        )

        def _boom(**_kwargs: object) -> None:
            msg = "permission denied"
            raise OSError(msg)

        monkeypatch.setattr(_setup, "build_handler", _boom)
        root = logging.getLogger()
        with pytest.raises(RuntimeError) as exc_info:
            _attach_handlers(config, root, [])
        assert isinstance(exc_info.value.__cause__, OSError)


@pytest.mark.unit
class TestConfigureLoggingIntegration:
    """Integration tests for configure_logging with env var overrides."""

    def test_synthorg_log_level_applied_end_to_end(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SYNTHORG_LOG_LEVEL env var takes effect through configure_logging."""
        monkeypatch.setenv("SYNTHORG_LOG_LEVEL", "warning")
        configure_logging(_console_only_config())
        root = logging.getLogger()
        # The console handler level should reflect the override.
        assert any(h.level == logging.WARNING for h in root.handlers)
