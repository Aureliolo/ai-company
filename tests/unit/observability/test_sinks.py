"""Tests for log handler factory."""

import logging
import logging.handlers
from typing import TYPE_CHECKING

import pytest
import structlog
from structlog.stdlib import ProcessorFormatter

from ai_company.observability.config import RotationConfig, SinkConfig
from ai_company.observability.enums import LogLevel, RotationStrategy, SinkType
from ai_company.observability.sinks import build_handler

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.timeout(30)


def _foreign_pre_chain() -> list[structlog.types.Processor]:
    return [
        structlog.stdlib.add_log_level,
        structlog.processors.format_exc_info,
    ]


@pytest.fixture
def handler_cleanup() -> Iterator[list[logging.Handler]]:
    """Collect handlers and close them after the test."""
    handlers: list[logging.Handler] = []
    yield handlers
    for h in handlers:
        h.close()


@pytest.mark.unit
class TestBuildHandlerConsole:
    """Tests for console handler creation."""

    def test_returns_stream_handler(self, tmp_path: Path) -> None:
        sink = SinkConfig(sink_type=SinkType.CONSOLE, json_format=False)
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        assert isinstance(handler, logging.StreamHandler)

    def test_has_processor_formatter(self, tmp_path: Path) -> None:
        sink = SinkConfig(sink_type=SinkType.CONSOLE, json_format=False)
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        assert isinstance(handler.formatter, ProcessorFormatter)

    def test_console_json_format(self, tmp_path: Path) -> None:
        sink = SinkConfig(sink_type=SinkType.CONSOLE, json_format=True)
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        assert isinstance(handler, logging.StreamHandler)

    def test_handler_level_matches_config(self, tmp_path: Path) -> None:
        sink = SinkConfig(
            sink_type=SinkType.CONSOLE,
            level=LogLevel.ERROR,
            json_format=False,
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        assert handler.level == logging.ERROR


@pytest.mark.unit
class TestBuildHandlerFileBuiltin:
    """Tests for file handler with BUILTIN rotation."""

    def test_returns_rotating_handler(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            rotation=RotationConfig(strategy=RotationStrategy.BUILTIN),
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert isinstance(handler, logging.handlers.RotatingFileHandler)

    def test_creates_parent_directories(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="sub/dir/app.log",
            rotation=RotationConfig(),
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert (tmp_path / "sub" / "dir").is_dir()

    def test_rotation_params_applied(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            rotation=RotationConfig(max_bytes=1_000_000, backup_count=3),
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == 1_000_000
        assert handler.backupCount == 3

    def test_handler_level_matches_config(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            level=LogLevel.WARNING,
            rotation=RotationConfig(),
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert handler.level == logging.WARNING

    def test_has_processor_formatter(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            rotation=RotationConfig(),
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert isinstance(handler.formatter, ProcessorFormatter)

    def test_default_rotation_when_none(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert isinstance(handler, logging.handlers.RotatingFileHandler)


@pytest.mark.unit
class TestBuildHandlerFileExternal:
    """Tests for file handler with EXTERNAL rotation."""

    def test_returns_watched_handler(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            rotation=RotationConfig(strategy=RotationStrategy.EXTERNAL),
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert isinstance(handler, logging.handlers.WatchedFileHandler)

    def test_creates_parent_directories(
        self, tmp_path: Path, handler_cleanup: list[logging.Handler]
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="ext/app.log",
            rotation=RotationConfig(strategy=RotationStrategy.EXTERNAL),
        )
        handler = build_handler(sink, tmp_path, _foreign_pre_chain())
        handler_cleanup.append(handler)
        assert (tmp_path / "ext").is_dir()
