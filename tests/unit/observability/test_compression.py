"""Tests for compressing rotating file handler."""

import gzip
import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from synthorg.observability.config import RotationConfig, SinkConfig
from synthorg.observability.enums import RotationStrategy, SinkType
from synthorg.observability.sinks import (
    _build_file_handler,
    _CompressingRotatingFileHandler,
    _FlushingRotatingFileHandler,
)


@pytest.fixture
def handler_cleanup() -> Iterator[list[logging.Handler]]:
    """Collect handlers and close them after the test."""
    handlers: list[logging.Handler] = []
    yield handlers
    for h in handlers:
        h.close()


@pytest.mark.unit
class TestCompressingRotatingFileHandler:
    """Tests for _CompressingRotatingFileHandler."""

    def test_rotated_file_compressed_to_gzip(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        log_file = tmp_path / "app.log"
        handler = _CompressingRotatingFileHandler(
            filename=str(log_file),
            maxBytes=200,
            backupCount=3,
            compress=True,
        )
        handler_cleanup.append(handler)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="x" * 100,
            args=(),
            exc_info=None,
        )
        # Emit enough to trigger at least one rotation
        for _ in range(10):
            handler.emit(record)

        gz_files = list(tmp_path.glob("*.gz"))
        assert len(gz_files) > 0
        # The plain .log.1 should NOT exist (replaced by .gz)
        assert not (tmp_path / "app.log.1").exists()

    def test_compress_false_skips_compression(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        log_file = tmp_path / "app.log"
        handler = _CompressingRotatingFileHandler(
            filename=str(log_file),
            maxBytes=200,
            backupCount=3,
            compress=False,
        )
        handler_cleanup.append(handler)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="x" * 100,
            args=(),
            exc_info=None,
        )
        for _ in range(10):
            handler.emit(record)

        gz_files = list(tmp_path.glob("*.gz"))
        assert len(gz_files) == 0

    def test_gzip_content_matches_original(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        log_file = tmp_path / "app.log"
        handler = _CompressingRotatingFileHandler(
            filename=str(log_file),
            maxBytes=200,
            backupCount=3,
            compress=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler_cleanup.append(handler)

        # Use long messages to guarantee rotation triggers
        for i in range(20):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"line-{i}-" + "x" * 80,
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        # At least one .gz file should exist and be valid gzip
        gz_files = sorted(tmp_path.glob("*.gz"))
        assert len(gz_files) > 0
        for gz_file in gz_files:
            content = gzip.decompress(gz_file.read_bytes())
            # Must be non-empty and contain some of our messages
            assert len(content) > 0
            assert b"line-" in content

    def test_flush_after_emit_preserved(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        """Verify the flushing behavior from the parent class."""
        log_file = tmp_path / "app.log"
        handler = _CompressingRotatingFileHandler(
            filename=str(log_file),
            maxBytes=10_000,
            backupCount=1,
            compress=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler_cleanup.append(handler)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="flushed",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        # File should contain data immediately (flushed)
        assert log_file.stat().st_size > 0

    def test_compression_error_handled_gracefully(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        log_file = tmp_path / "app.log"
        handler = _CompressingRotatingFileHandler(
            filename=str(log_file),
            maxBytes=200,
            backupCount=3,
            compress=True,
        )
        handler_cleanup.append(handler)

        with patch("gzip.open", side_effect=OSError("disk full")):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="x" * 100,
                args=(),
                exc_info=None,
            )
            # Should not raise -- rotation completes, compression fails
            # gracefully and the uncompressed backup remains
            for _ in range(10):
                handler.emit(record)

        # The main log file should still exist and be writable
        assert log_file.exists()

    def test_is_subclass_of_flushing_handler(self) -> None:
        assert issubclass(
            _CompressingRotatingFileHandler,
            _FlushingRotatingFileHandler,
        )


@pytest.mark.unit
class TestBuildFileHandlerCompression:
    """Tests for _build_file_handler with compress_rotated."""

    def test_compress_true_returns_compressing_handler(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            rotation=RotationConfig(compress_rotated=True),
        )
        handler = _build_file_handler(sink, tmp_path)
        handler_cleanup.append(handler)
        assert isinstance(handler, _CompressingRotatingFileHandler)

    def test_compress_false_returns_flushing_handler(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            rotation=RotationConfig(compress_rotated=False),
        )
        handler = _build_file_handler(sink, tmp_path)
        handler_cleanup.append(handler)
        assert isinstance(handler, _FlushingRotatingFileHandler)
        assert not isinstance(handler, _CompressingRotatingFileHandler)

    def test_external_rotation_ignores_compress(
        self,
        tmp_path: Path,
        handler_cleanup: list[logging.Handler],
    ) -> None:
        sink = SinkConfig(
            sink_type=SinkType.FILE,
            file_path="app.log",
            rotation=RotationConfig(
                strategy=RotationStrategy.EXTERNAL,
                compress_rotated=True,
            ),
        )
        handler = _build_file_handler(sink, tmp_path)
        handler_cleanup.append(handler)
        # External rotation does not use compressing handler
        assert not isinstance(handler, _CompressingRotatingFileHandler)
