"""Span context-manager helpers for LLM and tool instrumentation.

``llm_span`` wraps an LLM provider call; ``tool_span`` wraps a tool
invocation. Both use OTel's GenAI semantic conventions
(``gen_ai.*``) and tool semantic conventions (``tool.*``) so
Jaeger / Tempo / Honeycomb / Grafana display structured fields in
the UI.

The helpers read their tracer via :func:`get_tracer`, which in turn
forwards to the globally installed :class:`TracerProvider`. With
tracing disabled, ``get_tracer`` returns OTel's built-in
:class:`NoOpTracer` and these context managers cost effectively
nothing.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from opentelemetry import trace as _ot_trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from opentelemetry.trace import Span, Tracer

_INSTRUMENTATION_NAME = "synthorg"


def get_tracer(name: str = _INSTRUMENTATION_NAME) -> Tracer:
    """Return the globally configured tracer for *name*.

    With no provider installed, this yields OTel's built-in
    :class:`~opentelemetry.trace.NoOpTracer`.
    """
    return _ot_trace.get_tracer(name)


@asynccontextmanager
async def llm_span(
    *,
    provider: str,
    model: str,
    input_tokens: int | None = None,
    tracer: Tracer | None = None,
) -> AsyncIterator[Span]:
    """Wrap an LLM completion call in a ``chat {model}`` span.

    Attributes set on entry follow OTel's GenAI semantic conventions
    (``gen_ai.system``, ``gen_ai.request.model``, and when known
    ``gen_ai.usage.input_tokens``). Callers should set
    ``gen_ai.response.model`` / ``gen_ai.usage.output_tokens`` /
    ``gen_ai.response.finish_reasons`` on the span once the response
    is available via :meth:`Span.set_attribute`.

    Exceptions raised inside the context manager are recorded on the
    span and the span status is set to ``ERROR`` before the
    exception re-raises.
    """
    tracer = tracer or get_tracer()
    with tracer.start_as_current_span(f"chat {model}") as span:
        span.set_attribute("gen_ai.system", provider)
        span.set_attribute("gen_ai.request.model", model)
        if input_tokens is not None:
            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        try:
            yield span
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


@asynccontextmanager
async def tool_span(
    *,
    tool_name: str,
    tool_call_id: str,
    tracer: Tracer | None = None,
) -> AsyncIterator[Span]:
    """Wrap a tool invocation in a ``tool {tool_name}`` span.

    When this context manager is entered inside an active
    :func:`llm_span`, OTel's context propagation links the tool span
    as a child in the waterfall view -- no explicit parent wiring
    needed.

    Callers must set ``tool.outcome`` (``"success"`` / ``"error"`` /
    ``"timeout"``) on the span once the invocation completes so
    operators can filter by outcome in the tracing UI.
    """
    tracer = tracer or get_tracer()
    with tracer.start_as_current_span(f"tool {tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("tool.call_id", tool_call_id)
        try:
            yield span
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
