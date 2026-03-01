"""Unit tests for LiteLLMDriver.

All tests mock ``litellm.acompletion`` — no real API calls are made.
"""

from unittest.mock import AsyncMock, patch

import pytest

from ai_company.config.schema import ProviderConfig, ProviderModelConfig
from ai_company.providers.drivers.litellm_driver import LiteLLMDriver
from ai_company.providers.enums import (
    FinishReason,
    MessageRole,
    StreamEventType,
)
from ai_company.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderInternalError,
    ProviderTimeoutError,
    RateLimitError,
)
from ai_company.providers.models import (
    ChatMessage,
    CompletionConfig,
    ToolDefinition,
)

from .conftest import (
    make_mock_response,
    make_mock_tool_call,
    make_provider_config,
    make_stream_chunk,
    make_stream_tool_call_delta,
    mock_stream_response,
)

# ── Helpers ──────────────────────────────────────────────────────

_PATCH_ACOMPLETION = "ai_company.providers.drivers.litellm_driver._litellm.acompletion"
_PATCH_MODEL_INFO = (
    "ai_company.providers.drivers.litellm_driver._litellm.get_model_info"
)


def _make_driver(
    provider_name: str = "anthropic",
    config: ProviderConfig | None = None,
) -> LiteLLMDriver:
    return LiteLLMDriver(
        provider_name,
        config or make_provider_config(),
    )


def _user_message(
    content: str = "Hello",
) -> list[ChatMessage]:
    return [ChatMessage(role=MessageRole.USER, content=content)]


async def _collect_stream(
    driver: LiteLLMDriver,
    mock_call: AsyncMock,
    chunks: list,
    model: str = "sonnet",
) -> list:
    mock_call.return_value = mock_stream_response(chunks)
    stream = await driver.stream(_user_message(), model)
    return [chunk async for chunk in stream]


# ── Non-streaming completion ─────────────────────────────────────


@pytest.mark.unit
class TestDoComplete:
    async def test_basic_completion(self):
        driver = _make_driver()
        mock_resp = make_mock_response()

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            result = await driver.complete(_user_message(), "sonnet")

        assert result.content == "Hello! How can I help?"
        assert result.finish_reason == FinishReason.STOP
        assert result.model == "claude-sonnet-4-6"
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 50

    async def test_completion_with_tool_calls(self):
        driver = _make_driver()
        tc = make_mock_tool_call()
        mock_resp = make_mock_response(
            content=None,
            tool_calls=[tc],
            finish_reason="tool_calls",
        )

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            result = await driver.complete(_user_message(), "sonnet")

        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call_001"
        assert result.tool_calls[0].name == "get_weather"
        assert result.finish_reason == FinishReason.TOOL_USE

    async def test_model_alias_resolution(self):
        driver = _make_driver()
        mock_resp = make_mock_response()

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await driver.complete(_user_message(), "haiku")

        kw = m.call_args.kwargs
        assert kw["model"] == "anthropic/claude-haiku-4-5"

    async def test_model_id_resolution(self):
        driver = _make_driver()
        mock_resp = make_mock_response()

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await driver.complete(
                _user_message(),
                "claude-sonnet-4-6",
            )

        kw = m.call_args.kwargs
        assert kw["model"] == "anthropic/claude-sonnet-4-6"

    async def test_unknown_model_raises(self):
        driver = _make_driver()

        with pytest.raises(ModelNotFoundError, match="nonexistent"):
            await driver.complete(_user_message(), "nonexistent")

    async def test_api_key_passed_to_litellm(self):
        driver = _make_driver()
        mock_resp = make_mock_response()

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await driver.complete(_user_message(), "sonnet")

        assert m.call_args.kwargs["api_key"] == "sk-test-key"

    async def test_base_url_passed_to_litellm(self):
        config = make_provider_config(
            base_url="https://custom.api.example.com",
        )
        driver = _make_driver(config=config)
        mock_resp = make_mock_response()

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await driver.complete(_user_message(), "sonnet")

        kw = m.call_args.kwargs
        assert kw["api_base"] == "https://custom.api.example.com"

    async def test_completion_config_parameters(self):
        driver = _make_driver()
        mock_resp = make_mock_response()
        comp_config = CompletionConfig(
            temperature=0.5,
            max_tokens=1024,
            stop_sequences=("END",),
            top_p=0.9,
            timeout=30.0,
        )

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await driver.complete(
                _user_message(),
                "sonnet",
                config=comp_config,
            )

        kw = m.call_args.kwargs
        assert kw["temperature"] == 0.5
        assert kw["max_tokens"] == 1024
        assert kw["stop"] == ["END"]
        assert kw["top_p"] == 0.9
        assert kw["timeout"] == 30.0

    async def test_tools_passed_to_litellm(self):
        driver = _make_driver()
        mock_resp = make_mock_response()
        tools = [
            ToolDefinition(
                name="search",
                description="Search code",
                parameters_schema={"type": "object"},
            ),
        ]

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            await driver.complete(
                _user_message(),
                "sonnet",
                tools=tools,
            )

        kw = m.call_args.kwargs
        assert "tools" in kw
        assert kw["tools"][0]["function"]["name"] == "search"

    async def test_provider_request_id_captured(self):
        driver = _make_driver()
        mock_resp = make_mock_response(request_id="req_xyz789")

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            result = await driver.complete(_user_message(), "sonnet")

        assert result.provider_request_id == "req_xyz789"

    async def test_cost_computed_from_config(self):
        driver = _make_driver()
        mock_resp = make_mock_response(
            prompt_tokens=1000,
            completion_tokens=500,
        )

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            m.return_value = mock_resp
            result = await driver.complete(_user_message(), "sonnet")

        # sonnet: 0.003/1k in + 0.015/1k out = 0.0105
        assert result.usage.cost_usd == 0.0105


# ── Streaming ────────────────────────────────────────────────────


@pytest.mark.unit
class TestDoStream:
    async def test_basic_streaming(self):
        driver = _make_driver()
        chunks = [
            make_stream_chunk(content="Hello"),
            make_stream_chunk(content=" world"),
            make_stream_chunk(
                finish_reason="stop",
                prompt_tokens=100,
                completion_tokens=50,
            ),
        ]

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            collected = await _collect_stream(driver, m, chunks)

        content_chunks = [
            c for c in collected if c.event_type == StreamEventType.CONTENT_DELTA
        ]
        assert len(content_chunks) == 2
        assert content_chunks[0].content == "Hello"
        assert content_chunks[1].content == " world"
        assert collected[-1].event_type == StreamEventType.DONE

    async def test_streaming_with_tool_calls(self):
        driver = _make_driver()
        td1 = make_stream_tool_call_delta(
            index=0,
            call_id="call_001",
            name="search",
            arguments='{"qu',
        )
        td2 = make_stream_tool_call_delta(
            index=0,
            arguments='ery": "test"}',
        )
        chunks = [
            make_stream_chunk(tool_calls=[td1]),
            make_stream_chunk(tool_calls=[td2]),
            make_stream_chunk(finish_reason="tool_calls"),
        ]

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            collected = await _collect_stream(driver, m, chunks)

        tc_chunks = [
            c for c in collected if c.event_type == StreamEventType.TOOL_CALL_DELTA
        ]
        assert len(tc_chunks) == 1
        tc = tc_chunks[0].tool_call_delta
        assert tc is not None
        assert tc.id == "call_001"
        assert tc.name == "search"
        assert tc.arguments == {"query": "test"}

    async def test_streaming_usage_chunk(self):
        driver = _make_driver()
        chunks = [
            make_stream_chunk(content="Hi"),
            make_stream_chunk(
                finish_reason="stop",
                prompt_tokens=50,
                completion_tokens=10,
            ),
        ]

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            collected = await _collect_stream(driver, m, chunks)

        usage_chunks = [c for c in collected if c.event_type == StreamEventType.USAGE]
        assert len(usage_chunks) == 1
        assert usage_chunks[0].usage is not None
        assert usage_chunks[0].usage.input_tokens == 50
        assert usage_chunks[0].usage.output_tokens == 10

    async def test_stream_sets_stream_option(self):
        driver = _make_driver()
        chunks = [make_stream_chunk(content="ok")]

        with patch(_PATCH_ACOMPLETION, new_callable=AsyncMock) as m:
            await _collect_stream(driver, m, chunks)

        kw = m.call_args.kwargs
        assert kw["stream"] is True
        assert kw["stream_options"] == {"include_usage": True}


# ── Exception mapping ────────────────────────────────────────────


@pytest.mark.unit
class TestExceptionMapping:
    @pytest.mark.parametrize(
        ("litellm_exc_name", "expected_type"),
        [
            ("AuthenticationError", AuthenticationError),
            ("RateLimitError", RateLimitError),
            ("NotFoundError", ModelNotFoundError),
            ("ContextWindowExceededError", InvalidRequestError),
            ("ContentPolicyViolationError", ContentFilterError),
            ("BadRequestError", InvalidRequestError),
            ("Timeout", ProviderTimeoutError),
            ("ServiceUnavailableError", ProviderInternalError),
            ("InternalServerError", ProviderInternalError),
            ("APIConnectionError", ProviderConnectionError),
        ],
    )
    async def test_exception_mapping(
        self,
        litellm_exc_name: str,
        expected_type: type,
    ):
        import litellm as _litellm

        driver = _make_driver()
        exc_class = getattr(_litellm, litellm_exc_name)
        kwargs = _litellm_exc_kwargs(litellm_exc_name)
        litellm_exc = exc_class(**kwargs)

        with patch(
            _PATCH_ACOMPLETION,
            new_callable=AsyncMock,
        ) as m:
            m.side_effect = litellm_exc
            with pytest.raises(expected_type) as exc_info:
                await driver.complete(_user_message(), "sonnet")

        assert exc_info.value.context["provider"] == "anthropic"

    async def test_rate_limit_retry_after_extracted(self):
        import litellm as _litellm

        driver = _make_driver()
        exc = _litellm.RateLimitError(
            message="Rate limited",
            model="test",
            llm_provider="anthropic",
        )
        exc.headers = {"retry-after": "30"}

        with patch(
            _PATCH_ACOMPLETION,
            new_callable=AsyncMock,
        ) as m:
            m.side_effect = exc
            with pytest.raises(RateLimitError) as exc_info:
                await driver.complete(_user_message(), "sonnet")

        assert exc_info.value.retry_after == 30.0

    async def test_unknown_exception_maps_to_internal(self):
        driver = _make_driver()

        with patch(
            _PATCH_ACOMPLETION,
            new_callable=AsyncMock,
        ) as m:
            m.side_effect = RuntimeError("something broke")
            with pytest.raises(
                ProviderInternalError,
                match="Unexpected",
            ):
                await driver.complete(
                    _user_message(),
                    "sonnet",
                )

    async def test_stream_exception_during_iteration(self):
        import litellm as _litellm

        driver = _make_driver()

        async def _failing_stream():
            yield make_stream_chunk(content="Hi")
            raise _litellm.Timeout(
                message="Stream timed out",
                model="test",
                llm_provider="anthropic",
            )

        with patch(
            _PATCH_ACOMPLETION,
            new_callable=AsyncMock,
        ) as m:
            m.return_value = _failing_stream()
            stream = await driver.stream(
                _user_message(),
                "sonnet",
            )
            with pytest.raises(ProviderTimeoutError):
                async for _ in stream:
                    pass


# ── Model capabilities ───────────────────────────────────────────


@pytest.mark.unit
class TestGetModelCapabilities:
    async def test_basic_capabilities(self):
        driver = _make_driver()
        model_info = {
            "max_output_tokens": 8192,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_system_messages": True,
        }

        with patch(
            _PATCH_MODEL_INFO,
            return_value=model_info,
        ):
            caps = await driver.get_model_capabilities("sonnet")

        assert caps.model_id == "claude-sonnet-4-6"
        assert caps.provider == "anthropic"
        assert caps.max_context_tokens == 200_000
        assert caps.max_output_tokens == 8192
        assert caps.supports_tools is True
        assert caps.supports_vision is True
        assert caps.cost_per_1k_input == 0.003
        assert caps.cost_per_1k_output == 0.015

    async def test_capabilities_fallback_on_litellm_error(self):
        driver = _make_driver()

        with patch(
            _PATCH_MODEL_INFO,
            side_effect=Exception("Unknown model"),
        ):
            caps = await driver.get_model_capabilities("sonnet")

        assert caps.model_id == "claude-sonnet-4-6"
        assert caps.max_output_tokens == 4096  # default

    async def test_max_output_capped_at_context(self):
        config = make_provider_config(
            models=(
                ProviderModelConfig(
                    id="small-model",
                    max_context=1024,
                    cost_per_1k_input=0.001,
                    cost_per_1k_output=0.002,
                ),
            ),
        )
        driver = _make_driver(config=config)
        model_info = {"max_output_tokens": 999_999}

        with patch(
            _PATCH_MODEL_INFO,
            return_value=model_info,
        ):
            caps = await driver.get_model_capabilities(
                "small-model",
            )

        assert caps.max_output_tokens == 1024


# ── Helpers ──────────────────────────────────────────────────────


def _litellm_exc_kwargs(exc_name: str) -> dict:
    """Build constructor kwargs for litellm exceptions."""
    return {
        "message": f"Test {exc_name}",
        "model": "test-model",
        "llm_provider": "test",
    }
