"""LiteLLM-backed completion driver.

Wraps ``litellm.acompletion`` behind the ``BaseCompletionProvider``
contract, mapping between domain models and LiteLLM's OpenAI-compatible
API.
"""

import json
from typing import TYPE_CHECKING, Any

import litellm as _litellm
from litellm.exceptions import (
    APIConnectionError as LiteLLMConnectionError,
)
from litellm.exceptions import (
    AuthenticationError as LiteLLMAuthError,
)
from litellm.exceptions import (
    BadRequestError as LiteLLMBadRequest,
)
from litellm.exceptions import (
    ContentPolicyViolationError as LiteLLMContentPolicy,
)
from litellm.exceptions import (
    ContextWindowExceededError as LiteLLMContextWindow,
)
from litellm.exceptions import (
    InternalServerError as LiteLLMInternalError,
)
from litellm.exceptions import (
    NotFoundError as LiteLLMNotFound,
)
from litellm.exceptions import (
    RateLimitError as LiteLLMRateLimit,
)
from litellm.exceptions import (
    ServiceUnavailableError as LiteLLMUnavailable,
)
from litellm.exceptions import (
    Timeout as LiteLLMTimeout,
)

from ai_company.providers import errors
from ai_company.providers.base import BaseCompletionProvider
from ai_company.providers.capabilities import ModelCapabilities
from ai_company.providers.enums import StreamEventType
from ai_company.providers.models import (
    CompletionResponse,
    StreamChunk,
    ToolCall,
)

from .mappers import (
    extract_tool_calls,
    map_finish_reason,
    messages_to_dicts,
    tools_to_dicts,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ai_company.config.schema import ProviderConfig, ProviderModelConfig
    from ai_company.providers.models import (
        ChatMessage,
        CompletionConfig,
        ToolDefinition,
    )

# ── Exception mapping table ──────────────────────────────────────

_EXCEPTION_TABLE: tuple[tuple[type[Exception], type[errors.ProviderError]], ...] = (
    (LiteLLMAuthError, errors.AuthenticationError),
    (LiteLLMRateLimit, errors.RateLimitError),
    (LiteLLMNotFound, errors.ModelNotFoundError),
    (LiteLLMContextWindow, errors.InvalidRequestError),
    (LiteLLMContentPolicy, errors.ContentFilterError),
    (LiteLLMBadRequest, errors.InvalidRequestError),
    (LiteLLMTimeout, errors.ProviderTimeoutError),
    (LiteLLMUnavailable, errors.ProviderInternalError),
    (LiteLLMInternalError, errors.ProviderInternalError),
    (LiteLLMConnectionError, errors.ProviderConnectionError),
)


class LiteLLMDriver(BaseCompletionProvider):
    """Completion driver backed by LiteLLM.

    Uses ``litellm.acompletion`` for both streaming and non-streaming
    calls.  Model identifiers are prefixed with the provider name
    (e.g. ``anthropic/claude-sonnet-4-6``) so LiteLLM routes to the
    correct backend.

    Args:
        provider_name: Provider key from config (e.g. ``"anthropic"``).
        config: Provider configuration including API key, base URL,
            and model definitions.
    """

    def __init__(
        self,
        provider_name: str,
        config: ProviderConfig,
    ) -> None:
        self._provider_name = provider_name
        self._config = config
        self._model_lookup = self._build_model_lookup(config.models)

    # ── Hook implementations ─────────────────────────────────────

    async def _do_complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        """Call ``litellm.acompletion`` and map the response."""
        model_config = self._resolve_model(model)
        litellm_model = f"{self._provider_name}/{model_config.id}"
        kwargs = self._build_kwargs(
            messages,
            litellm_model,
            tools=tools,
            config=config,
        )

        try:
            response = await _litellm.acompletion(**kwargs)
        except Exception as exc:
            raise self._map_exception(exc, model) from exc

        return self._map_response(response, model_config)

    async def _do_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Call ``litellm.acompletion(stream=True)``."""
        model_config = self._resolve_model(model)
        litellm_model = f"{self._provider_name}/{model_config.id}"
        kwargs = self._build_kwargs(
            messages,
            litellm_model,
            tools=tools,
            config=config,
            stream=True,
        )

        try:
            raw_stream = await _litellm.acompletion(**kwargs)
        except Exception as exc:
            raise self._map_exception(exc, model) from exc

        return self._wrap_stream(raw_stream, model, model_config)

    async def _do_get_model_capabilities(
        self,
        model: str,
    ) -> ModelCapabilities:
        """Build ``ModelCapabilities`` from config + LiteLLM info."""
        model_config = self._resolve_model(model)
        litellm_model = f"{self._provider_name}/{model_config.id}"
        info = self._get_litellm_model_info(litellm_model)

        max_output = int(
            info.get("max_output_tokens", 0) or info.get("max_tokens", 0) or 4096,
        )

        return ModelCapabilities(
            model_id=model_config.id,
            provider=self._provider_name,
            max_context_tokens=model_config.max_context,
            max_output_tokens=min(max_output, model_config.max_context),
            supports_tools=bool(
                info.get("supports_function_calling", False),
            ),
            supports_vision=bool(
                info.get("supports_vision", False),
            ),
            supports_streaming=True,
            supports_streaming_tool_calls=bool(
                info.get("supports_function_calling", False),
            ),
            supports_system_messages=bool(
                info.get("supports_system_messages", True),
            ),
            cost_per_1k_input=model_config.cost_per_1k_input,
            cost_per_1k_output=model_config.cost_per_1k_output,
        )

    # ── Model resolution ─────────────────────────────────────────

    @staticmethod
    def _build_model_lookup(
        models: tuple[ProviderModelConfig, ...],
    ) -> dict[str, ProviderModelConfig]:
        """Build alias/id -> model config lookup."""
        lookup: dict[str, ProviderModelConfig] = {}
        for m in models:
            lookup[m.id] = m
            if m.alias is not None:
                lookup[m.alias] = m
        return lookup

    def _resolve_model(self, model: str) -> ProviderModelConfig:
        """Resolve a model alias or ID to its config.

        Raises:
            ModelNotFoundError: If not found in this provider.
        """
        config = self._model_lookup.get(model)
        if config is None:
            msg = f"Model {model!r} not found in provider {self._provider_name!r}"
            raise errors.ModelNotFoundError(
                msg,
                context={
                    "provider": self._provider_name,
                    "model": model,
                },
            )
        return config

    # ── Request building ─────────────────────────────────────────

    def _build_kwargs(
        self,
        messages: list[ChatMessage],
        litellm_model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build keyword arguments for ``litellm.acompletion``."""
        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages_to_dicts(messages),
        }
        if tools:
            kwargs["tools"] = tools_to_dicts(tools)
        if stream:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}
        if self._config.api_key is not None:
            kwargs["api_key"] = self._config.api_key
        if self._config.base_url is not None:
            kwargs["api_base"] = self._config.base_url
        _apply_completion_config(kwargs, config)
        return kwargs

    # ── Response mapping ─────────────────────────────────────────

    def _map_response(
        self,
        response: Any,
        model_config: ProviderModelConfig,
    ) -> CompletionResponse:
        """Map a LiteLLM ``ModelResponse`` to ``CompletionResponse``."""
        choice = response.choices[0]
        message = choice.message

        content: str | None = getattr(message, "content", None)
        raw_tc = getattr(message, "tool_calls", None)
        tool_calls = extract_tool_calls(raw_tc)
        finish = map_finish_reason(
            getattr(choice, "finish_reason", None),
        )

        usage_obj = getattr(response, "usage", None)
        input_tok = int(getattr(usage_obj, "prompt_tokens", 0))
        output_tok = int(getattr(usage_obj, "completion_tokens", 0))
        usage = self.compute_cost(
            input_tok,
            output_tok,
            cost_per_1k_input=model_config.cost_per_1k_input,
            cost_per_1k_output=model_config.cost_per_1k_output,
        )

        return CompletionResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
            model=model_config.id,
            provider_request_id=getattr(response, "id", None),
        )

    # ── Streaming ────────────────────────────────────────────────

    def _wrap_stream(
        self,
        raw_stream: Any,
        model: str,
        model_config: ProviderModelConfig,
    ) -> AsyncIterator[StreamChunk]:
        """Return an async iterator that maps raw chunks."""
        process = self._process_chunk
        handle_exc = self._map_exception

        async def _generate() -> AsyncIterator[StreamChunk]:
            pending: dict[int, _ToolCallAccumulator] = {}
            try:
                async for chunk in raw_stream:
                    for sc in process(
                        chunk,
                        pending,
                        model_config,
                    ):
                        yield sc
            except Exception as exc:
                raise handle_exc(exc, model) from exc

            for sc in _emit_pending_tool_calls(pending):
                yield sc
            yield StreamChunk(event_type=StreamEventType.DONE)

        return _generate()

    def _process_chunk(
        self,
        chunk: Any,
        pending: dict[int, _ToolCallAccumulator],
        model_config: ProviderModelConfig,
    ) -> list[StreamChunk]:
        """Extract ``StreamChunk`` events from one raw chunk."""
        result: list[StreamChunk] = []
        choices = getattr(chunk, "choices", [])

        if not choices:
            usage_obj = getattr(chunk, "usage", None)
            if usage_obj is not None:
                result.append(
                    self._make_usage_chunk(usage_obj, model_config),
                )
            return result

        delta = getattr(choices[0], "delta", None)
        if delta is None:
            return result

        text = getattr(delta, "content", None)
        if text:
            result.append(
                StreamChunk(
                    event_type=StreamEventType.CONTENT_DELTA,
                    content=text,
                )
            )

        raw_tc = getattr(delta, "tool_calls", None)
        if raw_tc:
            _accumulate_tool_call_deltas(raw_tc, pending)

        usage_obj = getattr(chunk, "usage", None)
        if usage_obj and getattr(usage_obj, "prompt_tokens", 0):
            result.append(
                self._make_usage_chunk(usage_obj, model_config),
            )

        return result

    def _make_usage_chunk(
        self,
        usage_obj: Any,
        model_config: ProviderModelConfig,
    ) -> StreamChunk:
        """Build a ``USAGE`` stream chunk."""
        input_tok = int(getattr(usage_obj, "prompt_tokens", 0))
        output_tok = int(getattr(usage_obj, "completion_tokens", 0))
        usage = self.compute_cost(
            input_tok,
            output_tok,
            cost_per_1k_input=model_config.cost_per_1k_input,
            cost_per_1k_output=model_config.cost_per_1k_output,
        )
        return StreamChunk(
            event_type=StreamEventType.USAGE,
            usage=usage,
        )

    # ── Exception mapping ────────────────────────────────────────

    def _map_exception(
        self,
        exc: Exception,
        model: str,
    ) -> Exception:
        """Map a LiteLLM exception to the provider error hierarchy."""
        ctx: dict[str, Any] = {
            "provider": self._provider_name,
            "model": model,
        }

        for litellm_type, our_type in _EXCEPTION_TABLE:
            if isinstance(exc, litellm_type):
                if our_type is errors.RateLimitError:
                    return errors.RateLimitError(
                        str(exc),
                        retry_after=self._extract_retry_after(exc),
                        context=ctx,
                    )
                return our_type(str(exc), context=ctx)

        if isinstance(exc, errors.ProviderError):
            return exc

        return errors.ProviderInternalError(
            f"Unexpected error from {self._provider_name}: {exc}",
            context=ctx,
        )

    @staticmethod
    def _extract_retry_after(exc: Exception) -> float | None:
        """Extract ``retry-after`` seconds from exception headers."""
        headers = getattr(exc, "headers", None)
        if not isinstance(headers, dict):
            return None
        raw = headers.get("retry-after")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError, TypeError:
            return None

    # ── LiteLLM model info ───────────────────────────────────────

    @staticmethod
    def _get_litellm_model_info(
        litellm_model: str,
    ) -> dict[str, Any]:
        """Query LiteLLM for static model metadata.

        Returns empty dict if the model is unknown to LiteLLM.
        """
        try:
            raw = _litellm.get_model_info(model=litellm_model)
            info: dict[str, Any] = dict(raw) if raw else {}
        except Exception:
            return {}
        return info if isinstance(info, dict) else {}


# ── Module-level helpers ─────────────────────────────────────────


def _apply_completion_config(
    kwargs: dict[str, Any],
    config: CompletionConfig | None,
) -> None:
    """Merge ``CompletionConfig`` fields into kwargs dict."""
    if config is None:
        return
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.max_tokens is not None:
        kwargs["max_tokens"] = config.max_tokens
    if config.stop_sequences:
        kwargs["stop"] = list(config.stop_sequences)
    if config.top_p is not None:
        kwargs["top_p"] = config.top_p
    if config.timeout is not None:
        kwargs["timeout"] = config.timeout


def _accumulate_tool_call_deltas(
    raw_deltas: list[Any],
    pending: dict[int, _ToolCallAccumulator],
) -> None:
    """Merge streaming tool call deltas into accumulators."""
    for tc_delta in raw_deltas:
        idx: int = getattr(tc_delta, "index", 0)
        if idx not in pending:
            pending[idx] = _ToolCallAccumulator()
        pending[idx].update(tc_delta)


def _emit_pending_tool_calls(
    pending: dict[int, _ToolCallAccumulator],
) -> list[StreamChunk]:
    """Build ``TOOL_CALL_DELTA`` chunks from accumulated data."""
    result: list[StreamChunk] = []
    for idx in sorted(pending):
        tc = pending[idx].build()
        if tc is not None:
            result.append(
                StreamChunk(
                    event_type=StreamEventType.TOOL_CALL_DELTA,
                    tool_call_delta=tc,
                )
            )
    return result


class _ToolCallAccumulator:
    """Accumulates streaming tool call deltas into a ``ToolCall``."""

    def __init__(self) -> None:
        self.id: str = ""
        self.name: str = ""
        self.arguments: str = ""

    def update(self, delta: Any) -> None:
        """Merge a single tool call delta."""
        call_id = getattr(delta, "id", None)
        if call_id:
            self.id = str(call_id)
        func = getattr(delta, "function", None)
        if func is not None:
            name = getattr(func, "name", None)
            if name:
                self.name = str(name)
            args = getattr(func, "arguments", None)
            if args:
                self.arguments += str(args)

    def build(self) -> ToolCall | None:
        """Build a ``ToolCall`` if enough data accumulated."""
        if not self.id or not self.name:
            return None
        try:
            parsed = json.loads(self.arguments) if self.arguments else {}
        except json.JSONDecodeError, ValueError:
            parsed = {}
        args: dict[str, Any] = parsed if isinstance(parsed, dict) else {}
        return ToolCall(id=self.id, name=self.name, arguments=args)
