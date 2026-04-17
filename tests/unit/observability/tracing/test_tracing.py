"""Unit tests for the tracing subsystem (#1385).

Covers:

* Factory discriminator: ``DisabledTraceConfig`` -> ``NoopTraceHandler``;
  ``OtlpHttpTraceConfig`` -> ``OtlpTraceHandler``.
* ``NoopTraceHandler`` returns OTel's no-op tracer.
* ``llm_span`` / ``tool_span`` record the expected GenAI/tool
  attributes on the active span (via ``InMemorySpanExporter``).
* Tool span nested under LLM span is linked as a child in the
  exported span graph.
* Exceptions raised inside spans set ``Status(ERROR)`` and record the
  exception.
"""

from collections.abc import Generator

import pytest
from opentelemetry import trace as _ot_trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import NoOpTracer, StatusCode

from synthorg.observability.tracing import (
    DisabledTraceConfig,
    NoopTraceHandler,
    OtlpHttpTraceConfig,
    build_trace_handler,
    llm_span,
    tool_span,
)
from synthorg.observability.tracing.factory import build_trace_handler as _build

pytestmark = pytest.mark.unit


@pytest.fixture
def in_memory_tracer() -> Generator[InMemorySpanExporter]:
    """Install a global ``TracerProvider`` backed by InMemorySpanExporter.

    Cleans up after the test by resetting the global provider. Each
    test starts with a clean exporter.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    original = _ot_trace.get_tracer_provider()
    _ot_trace._TRACER_PROVIDER_SET_ONCE._done = False
    _ot_trace._TRACER_PROVIDER = None
    _ot_trace.set_tracer_provider(provider)
    try:
        yield exporter
    finally:
        provider.shutdown()
        _ot_trace._TRACER_PROVIDER_SET_ONCE._done = False
        _ot_trace._TRACER_PROVIDER = original


# -- Factory dispatch --------------------------------------------------------


def test_disabled_config_builds_noop_handler() -> None:
    handler = build_trace_handler(DisabledTraceConfig())
    assert isinstance(handler, NoopTraceHandler)
    assert isinstance(handler.get_tracer("x"), NoOpTracer)


def test_noop_handler_force_flush_and_shutdown_are_noop() -> None:
    import asyncio

    handler = NoopTraceHandler()
    asyncio.run(handler.force_flush())
    asyncio.run(handler.shutdown())


def test_factory_rejects_unknown_variant() -> None:
    """Defensive branch -- callers can't normally reach this."""
    with pytest.raises(ValueError, match="Unsupported TraceConfig variant"):
        _build("not-a-config")  # type: ignore[arg-type]


def test_otlp_http_config_builds_otlp_handler() -> None:
    from synthorg.observability.otlp_trace_handler import OtlpTraceHandler

    handler = build_trace_handler(
        OtlpHttpTraceConfig(
            endpoint="http://localhost:4318",
            sampling_ratio=0.0,  # Drop everything -- no network calls.
        )
    )
    try:
        assert isinstance(handler, OtlpTraceHandler)
    finally:
        import asyncio

        asyncio.run(handler.shutdown())


# -- llm_span ---------------------------------------------------------------


async def test_llm_span_sets_genai_attributes(
    in_memory_tracer: InMemorySpanExporter,
) -> None:
    async with llm_span(
        provider="TestProvider",
        model="example-large-001",
        input_tokens=42,
    ) as span:
        span.set_attribute("gen_ai.usage.output_tokens", 17)
        span.set_attribute("gen_ai.response.finish_reasons", ("stop",))
    spans = in_memory_tracer.get_finished_spans()
    assert len(spans) == 1
    recorded = spans[0]
    assert recorded.name == "chat example-large-001"
    attrs = dict(recorded.attributes or {})
    assert attrs["gen_ai.system"] == "TestProvider"
    assert attrs["gen_ai.request.model"] == "example-large-001"
    assert attrs["gen_ai.usage.input_tokens"] == 42
    assert attrs["gen_ai.usage.output_tokens"] == 17
    assert attrs["gen_ai.response.finish_reasons"] == ("stop",)
    assert recorded.status.status_code == StatusCode.UNSET


async def test_llm_span_exception_sets_error_status(
    in_memory_tracer: InMemorySpanExporter,
) -> None:
    error_msg = "provider exploded"
    with pytest.raises(RuntimeError, match="provider exploded"):
        async with llm_span(provider="P", model="m"):
            raise RuntimeError(error_msg)
    spans = in_memory_tracer.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert any(e.name == "exception" for e in span.events)


# -- tool_span --------------------------------------------------------------


async def test_tool_span_sets_tool_attributes(
    in_memory_tracer: InMemorySpanExporter,
) -> None:
    async with tool_span(
        tool_name="web_search",
        tool_call_id="call-1",
    ) as span:
        span.set_attribute("tool.outcome", "success")
    spans = in_memory_tracer.get_finished_spans()
    assert len(spans) == 1
    recorded = spans[0]
    assert recorded.name == "tool web_search"
    attrs = dict(recorded.attributes or {})
    assert attrs["tool.name"] == "web_search"
    assert attrs["tool.call_id"] == "call-1"
    assert attrs["tool.outcome"] == "success"


async def test_tool_span_nested_under_llm_span_is_linked(
    in_memory_tracer: InMemorySpanExporter,
) -> None:
    """Tool invocation inside an LLM turn is linked as a child span."""
    async with llm_span(provider="P", model="m") as llm:
        async with tool_span(tool_name="t", tool_call_id="c") as tool:
            pass
        llm_context = llm.get_span_context()
        tool_context = tool.get_span_context()
        assert llm_context.trace_id == tool_context.trace_id
    spans = in_memory_tracer.get_finished_spans()
    # Order: child first (tool), then parent (llm).
    tool_recorded = next(s for s in spans if s.name.startswith("tool "))
    llm_recorded = next(s for s in spans if s.name.startswith("chat "))
    assert tool_recorded.parent is not None
    assert tool_recorded.parent.span_id == llm_recorded.context.span_id
    assert tool_recorded.context.trace_id == llm_recorded.context.trace_id


async def test_tool_span_exception_sets_error_status(
    in_memory_tracer: InMemorySpanExporter,
) -> None:
    error_msg = "tool failed"
    with pytest.raises(RuntimeError, match="tool failed"):
        async with tool_span(tool_name="t", tool_call_id="c"):
            raise RuntimeError(error_msg)
    spans = in_memory_tracer.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
