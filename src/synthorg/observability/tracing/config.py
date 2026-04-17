"""Trace subsystem configuration.

``TraceConfig`` is a discriminated union keyed on ``kind``:

* ``"disabled"`` (default) -- tracing is off; helpers return no-op
  spans so call sites never pay for span construction.
* ``"otlp_http"`` -- emits spans via OTLP/HTTP (protobuf) to an
  OpenTelemetry collector endpoint.

New backends (gRPC, ConsoleSpanExporter for local debugging, etc.)
can be added as new ``kind`` variants without touching call sites.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class DisabledTraceConfig(BaseModel):
    """Tracing disabled. Call-site helpers become zero-cost no-ops."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["disabled"] = "disabled"


class OtlpHttpTraceConfig(BaseModel):
    """Exports OTel spans via OTLP/HTTP (protobuf).

    Attributes:
        endpoint: Collector URL (e.g. ``"http://otel-collector:4318"``).
            The exporter appends ``/v1/traces`` automatically.
        headers: Extra HTTP headers as ``(name, value)`` pairs. Use
            for auth tokens (e.g. Honeycomb's ``x-honeycomb-team``).
        sampling_ratio: Fraction of traces to record (0.0-1.0).
            1.0 records every trace; 0.0 records none. Use sampling
            to bound cost at high trace volumes.
        batch_max_queue_size: Upper bound on pending spans before
            new spans are dropped (back-pressure).
        batch_max_export_batch_size: Max spans per exported batch.
        batch_export_timeout_sec: Per-export HTTP timeout.
        schedule_delay_sec: Interval between batch flushes.
        service_name: Value for OTel resource ``service.name``
            attribute. Identifies this process in waterfalls.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["otlp_http"] = "otlp_http"
    endpoint: NotBlankStr
    headers: tuple[tuple[NotBlankStr, NotBlankStr], ...] = ()
    sampling_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    batch_max_queue_size: int = Field(default=2048, ge=1)
    batch_max_export_batch_size: int = Field(default=512, ge=1)
    batch_export_timeout_sec: float = Field(default=30.0, gt=0)
    schedule_delay_sec: float = Field(default=5.0, gt=0)
    service_name: NotBlankStr = "synthorg"


TraceConfig = Annotated[
    DisabledTraceConfig | OtlpHttpTraceConfig,
    Field(discriminator="kind"),
]
