"""Factory that resolves :class:`TraceConfig` to a :class:`TraceHandler`.

Dispatches on the config's ``kind`` discriminator so new backends
plug in with a single ``elif`` here -- the rest of the codebase
never sees the concrete handler class.
"""

from synthorg.observability.tracing.config import (
    DisabledTraceConfig,
    OtlpHttpTraceConfig,
    TraceConfig,
)
from synthorg.observability.tracing.protocol import (
    NoopTraceHandler,
    TraceHandler,
)


def build_trace_handler(config: TraceConfig) -> TraceHandler:
    """Resolve *config* into an active :class:`TraceHandler`.

    Returns a :class:`NoopTraceHandler` when tracing is disabled (the
    helpers in :mod:`...instrumentation` become zero-cost) and a
    concrete exporter-backed handler otherwise.

    Args:
        config: A :class:`TraceConfig` discriminated union variant.

    Returns:
        The resolved handler, ready for use.

    Raises:
        ValueError: If *config* is not one of the supported variants
            (defensive guard against runtime misuse from tests or
            dynamic construction).
    """
    if isinstance(config, DisabledTraceConfig):
        return NoopTraceHandler()
    if isinstance(config, OtlpHttpTraceConfig):
        # Lazy import -- OTel SDK only imported when actually
        # constructing an exporter-backed handler.
        from synthorg.observability.otlp_trace_handler import (  # noqa: PLC0415
            OtlpTraceHandler,
        )

        return OtlpTraceHandler(config)
    msg = f"Unsupported TraceConfig variant: {type(config).__name__}"  # type: ignore[unreachable]
    raise ValueError(msg)
