"""OTLP trace handler -- exports OpenTelemetry spans via HTTP/protobuf.

Owns the process-global ``TracerProvider`` + ``BatchSpanProcessor``
+ :class:`OTLPSpanExporter`. Constructing this handler installs its
provider as the global default so third-party libraries that read
``opentelemetry.trace.get_tracer_provider()`` also emit through this
exporter.

Called from startup wiring; the rest of the codebase accesses
tracers via :func:`synthorg.observability.tracing.get_tracer` which
forwards to the global provider.
"""

import asyncio
from typing import TYPE_CHECKING

from opentelemetry import trace as _ot_trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from synthorg.observability import get_logger
from synthorg.observability.events.metrics import (
    METRICS_OTLP_EXPORT_FAILED,
    METRICS_OTLP_FLUSHER_STARTED,
    METRICS_OTLP_FLUSHER_STOPPED,
)

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

    from synthorg.observability.tracing.config import OtlpHttpTraceConfig

logger = get_logger(__name__)

_TRACES_ENDPOINT_SUFFIX = "/v1/traces"


class OtlpTraceHandler:
    """Process-singleton OTLP trace exporter.

    Args:
        config: OTLP HTTP trace configuration.
    """

    def __init__(self, config: OtlpHttpTraceConfig) -> None:
        endpoint = _resolve_traces_endpoint(config.endpoint)
        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=dict(config.headers),
            timeout=int(config.batch_export_timeout_sec),
        )
        resource = Resource.create({"service.name": config.service_name})
        sampler = TraceIdRatioBased(config.sampling_ratio)
        self._provider = TracerProvider(resource=resource, sampler=sampler)
        self._processor = BatchSpanProcessor(
            exporter,
            max_queue_size=config.batch_max_queue_size,
            max_export_batch_size=config.batch_max_export_batch_size,
            schedule_delay_millis=int(config.schedule_delay_sec * 1000),
            export_timeout_millis=int(config.batch_export_timeout_sec * 1000),
        )
        self._provider.add_span_processor(self._processor)
        _ot_trace.set_tracer_provider(self._provider)
        logger.info(
            METRICS_OTLP_FLUSHER_STARTED,
            component="trace",
            endpoint=endpoint,
            sampling_ratio=config.sampling_ratio,
        )

    def get_tracer(self, name: str) -> Tracer:
        """Return a tracer bound to this handler's provider."""
        return self._provider.get_tracer(name)

    async def force_flush(self, timeout_sec: float = 5.0) -> None:
        """Block until pending spans are exported or the deadline fires."""
        timeout_ms = int(timeout_sec * 1000)
        flushed = await asyncio.to_thread(
            self._provider.force_flush,
            timeout_ms,
        )
        if not flushed:
            logger.warning(
                METRICS_OTLP_EXPORT_FAILED,
                component="trace",
                reason="flush_timeout",
                timeout_sec=timeout_sec,
            )

    async def shutdown(self) -> None:
        """Stop the exporter. The handler is unusable afterwards."""
        await asyncio.to_thread(self._provider.shutdown)
        logger.info(METRICS_OTLP_FLUSHER_STOPPED, component="trace")


def _resolve_traces_endpoint(base_endpoint: str) -> str:
    """Append ``/v1/traces`` to *base_endpoint* if not already present."""
    if base_endpoint.endswith(_TRACES_ENDPOINT_SUFFIX):
        return base_endpoint
    return base_endpoint.rstrip("/") + _TRACES_ENDPOINT_SUFFIX
