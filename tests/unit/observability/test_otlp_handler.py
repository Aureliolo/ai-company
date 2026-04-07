"""Tests for the OTLP log handler."""

import json
import logging
from typing import Any
from unittest.mock import MagicMock

import pytest

from synthorg.observability.config import SinkConfig
from synthorg.observability.enums import OtlpProtocol, SinkType
from synthorg.observability.otlp_handler import OtlpHandler, build_otlp_handler


def _make_record(
    msg: str = "test message",
    *,
    request_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if request_id is not None:
        record.request_id = request_id
    if task_id is not None:
        record.task_id = task_id
    if agent_id is not None:
        record.agent_id = agent_id
    return record


class _JsonFormatter(logging.Formatter):
    """Minimal JSON formatter for test handlers."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {"event": record.getMessage()}
        for key in ("request_id", "task_id", "agent_id"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


def _make_handler(
    *,
    batch_size: int = 5,
    flush_interval: float = 60.0,
) -> OtlpHandler:
    """Create a handler with a long flush interval (manual flush only)."""
    handler = OtlpHandler(
        endpoint="http://localhost:4318",
        batch_size=batch_size,
        flush_interval=flush_interval,
    )
    handler.setFormatter(_JsonFormatter())
    return handler


@pytest.mark.unit
class TestOtlpHandler:
    """Tests for OtlpHandler core behavior."""

    def test_emit_queues_record(self) -> None:
        handler = _make_handler()
        try:
            handler.emit(_make_record())
            with handler._pending_lock:
                assert handler._pending_count == 1
        finally:
            handler.close()

    def test_batch_ready_signal(self) -> None:
        handler = _make_handler(batch_size=2)
        try:
            handler.emit(_make_record("first"))
            assert not handler._batch_ready.is_set()
            handler.emit(_make_record("second"))
            assert handler._batch_ready.is_set()
        finally:
            handler.close()

    def test_close_signals_shutdown(self) -> None:
        handler = _make_handler()
        handler.close()
        assert handler._shutdown.is_set()
        assert not handler._flusher.is_alive()

    def test_drain_collects_records(self) -> None:
        handler = _make_handler()
        try:
            handler.emit(_make_record("one"))
            handler.emit(_make_record("two"))

            records: list[logging.LogRecord] = []
            while True:
                try:
                    records.append(handler._queue.get_nowait())
                except Exception:
                    break
            assert len(records) == 2
        finally:
            handler.close()

    def test_format_record_as_otlp_dict(self) -> None:
        handler = _make_handler()
        try:
            record = _make_record(
                "test event",
                request_id="req-123",
                task_id="task-456",
                agent_id="agent-789",
            )
            handler.setFormatter(_JsonFormatter())
            result = handler._format_as_otlp_dict(record)
            assert result["body"] == record.getMessage()
            assert result["attributes"]["request_id"] == "req-123"
            assert result["attributes"]["task_id"] == "task-456"
            assert result["attributes"]["agent_id"] == "agent-789"
            assert result["severity_text"] == "INFO"
        finally:
            handler.close()

    def test_format_record_without_correlation_ids(self) -> None:
        handler = _make_handler()
        try:
            record = _make_record("plain event")
            result = handler._format_as_otlp_dict(record)
            assert result["body"] == "plain event"
            assert "request_id" not in result["attributes"]
        finally:
            handler.close()


@pytest.mark.unit
class TestOtlpHandlerProtocol:
    """Tests for OTLP protocol configuration."""

    def test_default_protocol_is_http(self) -> None:
        handler = OtlpHandler(
            endpoint="http://localhost:4318",
        )
        try:
            assert handler._protocol == OtlpProtocol.HTTP_PROTOBUF
        finally:
            handler.close()

    def test_grpc_protocol(self) -> None:
        handler = OtlpHandler(
            endpoint="http://localhost:4317",
            protocol=OtlpProtocol.GRPC,
        )
        try:
            assert handler._protocol == OtlpProtocol.GRPC
        finally:
            handler.close()


@pytest.mark.unit
class TestBuildOtlpHandler:
    """Tests for the build_otlp_handler factory function."""

    def test_builds_from_valid_config(self) -> None:
        sink = SinkConfig(
            sink_type=SinkType.OTLP,
            otlp_endpoint="http://localhost:4318",
        )
        handler = build_otlp_handler(sink, [])
        try:
            assert isinstance(handler, OtlpHandler)
            assert handler._endpoint == "http://localhost:4318"
        finally:
            handler.close()

    def test_builds_with_custom_protocol(self) -> None:
        sink = SinkConfig(
            sink_type=SinkType.OTLP,
            otlp_endpoint="http://localhost:4317",
            otlp_protocol=OtlpProtocol.GRPC,
        )
        handler = build_otlp_handler(sink, [])
        try:
            assert handler._protocol == OtlpProtocol.GRPC
        finally:
            handler.close()

    def test_rejects_missing_endpoint(self) -> None:
        sink = MagicMock()
        sink.otlp_endpoint = None
        with pytest.raises(ValueError, match="non-empty otlp_endpoint"):
            build_otlp_handler(sink, [])
