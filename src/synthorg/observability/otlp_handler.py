"""OTLP handler for shipping structured logs as OpenTelemetry log records.

Batches log records in a thread-safe queue and exports them as OTLP
log records to a configurable endpoint using a background daemon thread.
Uses existing correlation IDs (request_id, task_id, agent_id) as
trace context attributes.
"""

import json
import logging
import queue
import sys
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

import structlog
from structlog.stdlib import ProcessorFormatter

from synthorg.observability.enums import OtlpProtocol

if TYPE_CHECKING:
    from synthorg.observability.config import SinkConfig

# Correlation ID field names injected by structlog contextvars
_CORRELATION_FIELDS = ("request_id", "task_id", "agent_id")

# Mapping from Python log levels to OTLP severity numbers.
# Python's CRITICAL maps to OTEL's FATAL range (21-24).
# https://opentelemetry.io/docs/specs/otel/logs/data-model/#severity-fields
_SEVERITY_MAP: dict[int, int] = {
    logging.DEBUG: 5,
    logging.INFO: 9,
    logging.WARNING: 13,
    logging.ERROR: 17,
    logging.CRITICAL: 21,
}


class OtlpHandler(logging.Handler):
    """Handler that batches log records and exports them as OTLP log records.

    A background daemon thread periodically flushes the queue.  Records
    are also flushed when the batch size is reached or when the handler
    is closed.

    Only HTTP/JSON transport is implemented. gRPC is rejected at
    both config validation (``SinkConfig``) and handler init.
    This is an approved deviation from issue #1122 which originally
    specified HTTP/protobuf -- the implementation uses JSON encoding
    with ``Content-Type: application/json``.

    Args:
        endpoint: OTLP collector endpoint URL.
        protocol: OTLP transport protocol (only ``HTTP_JSON`` supported).
        headers: Extra HTTP headers as ``(name, value)`` pairs.
        batch_size: Number of records per export batch.
        flush_interval: Seconds between automatic flushes.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(  # noqa: PLR0913
        self,
        endpoint: str,
        *,
        protocol: OtlpProtocol = OtlpProtocol.HTTP_JSON,
        headers: tuple[tuple[str, str], ...] = (),
        batch_size: int = 100,
        flush_interval: float = 5.0,
        timeout: float = 10.0,
        _start_flusher: bool = True,
    ) -> None:
        super().__init__()
        if protocol == OtlpProtocol.GRPC:
            msg = "gRPC transport is not implemented; use HTTP_JSON"
            raise NotImplementedError(msg)
        self._endpoint = endpoint
        self._protocol = protocol
        self._extra_headers = dict(headers)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._timeout = timeout
        self._queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
        self._pending_count = 0
        self._pending_lock = threading.Lock()
        self._dropped_count = 0
        self._shutdown = threading.Event()
        self._batch_ready = threading.Event()
        self._flusher = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="log-otlp-flusher",
        )
        if _start_flusher:
            self._flusher.start()

    def emit(self, record: logging.LogRecord) -> None:
        """Queue a record for batched OTLP export."""
        try:
            self._queue.put_nowait(record)
            with self._pending_lock:
                self._pending_count += 1
                if self._pending_count >= self._batch_size:
                    self._batch_ready.set()
        except MemoryError, RecursionError:
            raise
        except Exception:
            self.handleError(record)

    def _increment_dropped(self, count: int) -> None:
        """Atomically increment the dropped record counter.

        Acquires ``_pending_lock`` to ensure thread-safe updates.
        """
        with self._pending_lock:
            self._dropped_count += count

    def _format_as_otlp_dict(self, record: logging.LogRecord) -> dict[str, Any]:
        """Convert a log record to an OTLP-compatible dictionary.

        Maps correlation IDs to trace attributes and Python log levels
        to OTLP severity numbers.

        Args:
            record: The log record to convert.

        Returns:
            Dictionary with OTLP log record fields.
        """
        attributes: list[dict[str, Any]] = [
            {
                "key": "logger.name",
                "value": {"stringValue": record.name},
            },
        ]
        for field in _CORRELATION_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                attributes.append(
                    {
                        "key": field,
                        "value": {"stringValue": str(value)},
                    }
                )

        # Use self.format(record) so the ProcessorFormatter and
        # foreign_pre_chain run, producing structured JSON output.
        body = self.format(record) if self.formatter else record.getMessage()

        return {
            "body": {"stringValue": body},
            "severityNumber": _SEVERITY_MAP.get(record.levelno, 0),
            "severityText": record.levelname,
            "timeUnixNano": str(int(record.created * 1_000_000_000)),
            "attributes": attributes,
        }

    def _flush_loop(self) -> None:
        """Background loop: flush on interval, batch-ready, or shutdown."""
        while not self._shutdown.is_set():
            self._batch_ready.wait(timeout=self._flush_interval)
            self._batch_ready.clear()
            if self._shutdown.is_set():
                break
            try:
                self._drain_and_flush()
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                print(  # noqa: T201
                    f"ERROR: log-otlp-flusher encountered unexpected error: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

    def _drain_and_flush(self) -> None:
        """Drain all queued records and export as OTLP batches."""
        records: list[logging.LogRecord] = []
        while True:
            try:
                records.append(self._queue.get_nowait())
            except queue.Empty:
                break

        with self._pending_lock:
            self._pending_count = max(0, self._pending_count - len(records))

        for start in range(0, len(records), self._batch_size):
            batch = records[start : start + self._batch_size]
            if batch:
                self._export_batch(batch)

    def _export_batch(self, records: list[logging.LogRecord]) -> None:
        """Export a batch of records as OTLP JSON log records."""
        log_records: list[dict[str, Any]] = []
        for record in records:
            try:
                log_records.append(self._format_as_otlp_dict(record))
            except MemoryError, RecursionError:
                raise
            except Exception:
                self.handleError(record)
                self._increment_dropped(1)

        if not log_records:
            return

        # OTLP JSON format: wrap in resourceLogs envelope
        payload = {
            "resourceLogs": [
                {
                    "resource": {"attributes": []},
                    "scopeLogs": [
                        {
                            "scope": {"name": "synthorg"},
                            "logRecords": log_records,
                        },
                    ],
                },
            ],
        }
        body = json.dumps(payload).encode()

        # Use /v1/logs path for OTLP HTTP JSON
        url = self._endpoint.rstrip("/") + "/v1/logs"
        request = urllib.request.Request(url, data=body, method="POST")  # noqa: S310
        request.add_header("Content-Type", "application/json")
        for name, value in self._extra_headers.items():
            request.add_header(name, value)

        try:
            with urllib.request.urlopen(  # noqa: S310
                request,
                timeout=self._timeout,
            ):
                pass
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            # urllib.error.HTTPError wraps a file pointer to the response
            # body.  Close it explicitly to avoid leaking file descriptors.
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()
            self._increment_dropped(len(log_records))
            with self._pending_lock:
                total_dropped = self._dropped_count
            print(  # noqa: T201
                f"WARNING: OTLP log export failed to {url}: {exc} "
                f"(dropped {len(log_records)} records, "
                f"total dropped: {total_dropped})",
                file=sys.stderr,
                flush=True,
            )

    def close(self) -> None:
        """Signal shutdown, flush remaining records, stop thread."""
        self._shutdown.set()
        self._batch_ready.set()
        join_timeout = self._timeout * 2
        if self._flusher.is_alive():
            self._flusher.join(timeout=join_timeout)
            if self._flusher.is_alive():
                print(  # noqa: T201
                    "WARNING: log-otlp-flusher thread did not stop "
                    f"within {join_timeout:.1f}s timeout",
                    file=sys.stderr,
                    flush=True,
                )
        # Always drain remaining records regardless of thread state.
        self._drain_and_flush()
        super().close()


def build_otlp_handler(
    sink: SinkConfig,
    foreign_pre_chain: list[Any],
) -> OtlpHandler:
    """Build an OtlpHandler from an OTLP sink configuration.

    Args:
        sink: The OTLP sink configuration.
        foreign_pre_chain: Processor chain for stdlib-originated logs.

    Returns:
        A configured ``OtlpHandler`` with JSON formatting.
    """
    if not sink.otlp_endpoint:
        msg = "OTLP sink requires a non-empty otlp_endpoint"
        raise ValueError(msg)
    handler = OtlpHandler(
        endpoint=sink.otlp_endpoint,
        protocol=sink.otlp_protocol,
        headers=sink.otlp_headers,
        batch_size=sink.otlp_batch_size,
        flush_interval=sink.otlp_export_interval_seconds,
        timeout=sink.otlp_timeout_seconds,
    )
    handler.setLevel(sink.level.value)

    renderer: Any = structlog.processors.JSONRenderer()
    processors: list[Any] = [
        ProcessorFormatter.remove_processors_meta,
        structlog.processors.format_exc_info,
        renderer,
    ]
    formatter = ProcessorFormatter(
        processors=processors,
        foreign_pre_chain=foreign_pre_chain,
    )
    handler.setFormatter(formatter)

    return handler
