"""Unit tests for LLMGenerator."""

import json
from typing import cast

import pytest

from synthorg.client.generators import LLMGenerator
from synthorg.client.models import GenerationContext
from synthorg.client.protocols import RequirementGenerator
from synthorg.providers.enums import FinishReason
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
    CompletionResponse,
    TokenUsage,
    ToolDefinition,
)
from synthorg.providers.protocol import CompletionProvider

pytestmark = pytest.mark.unit


class _StubProvider:
    """Stub CompletionProvider for tests; no network calls."""

    def __init__(self, *, content: str | None) -> None:
        self._content = content
        self.captured_messages: list[ChatMessage] | None = None
        self.captured_model: str | None = None

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        del tools, config
        self.captured_messages = messages
        self.captured_model = model
        if self._content is None:
            return CompletionResponse(
                content=None,
                finish_reason=FinishReason.ERROR,
                usage=TokenUsage(input_tokens=10, output_tokens=0, cost=0.0),
                model=model,
            )
        return CompletionResponse(
            content=self._content,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(input_tokens=10, output_tokens=20, cost=0.0),
            model=model,
        )


def _ctx(count: int = 2) -> GenerationContext:
    return GenerationContext(
        project_id="proj-1",
        domain="backend",
        count=count,
    )


def _payload(requirements: list[dict[str, object]]) -> str:
    return json.dumps(requirements)


class TestLLMGenerator:
    def test_protocol_compatible(self) -> None:
        provider = _StubProvider(content="[]")
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        assert isinstance(gen, RequirementGenerator)

    async def test_parses_valid_json_array(self) -> None:
        provider = _StubProvider(
            content=_payload(
                [
                    {
                        "title": "First",
                        "description": "First desc",
                        "task_type": "development",
                        "priority": "high",
                        "estimated_complexity": "medium",
                        "acceptance_criteria": ["a", "b"],
                    },
                    {
                        "title": "Second",
                        "description": "Second desc",
                    },
                ],
            )
        )
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        result = await gen.generate(_ctx(count=2))
        assert len(result) == 2
        assert result[0].title == "First"
        assert result[0].acceptance_criteria == ("a", "b")
        assert result[1].title == "Second"

    async def test_returns_empty_on_empty_content(self) -> None:
        provider = _StubProvider(content="")
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        result = await gen.generate(_ctx())
        assert result == ()

    async def test_returns_empty_on_none_content(self) -> None:
        provider = _StubProvider(content=None)
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        result = await gen.generate(_ctx())
        assert result == ()

    async def test_returns_empty_on_non_json(self) -> None:
        provider = _StubProvider(content="not json at all")
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        result = await gen.generate(_ctx())
        assert result == ()

    async def test_returns_empty_when_payload_is_not_array(
        self,
    ) -> None:
        provider = _StubProvider(content='{"title": "nope"}')
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        result = await gen.generate(_ctx())
        assert result == ()

    async def test_extracts_array_from_wrapped_prose(self) -> None:
        wrapped = (
            "Here you go:\n"
            + _payload(
                [{"title": "Task", "description": "D"}],
            )
            + "\nHope that helps!"
        )
        provider = _StubProvider(content=wrapped)
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        result = await gen.generate(_ctx(count=1))
        assert len(result) == 1
        assert result[0].title == "Task"

    async def test_skips_invalid_items_in_array(self) -> None:
        provider = _StubProvider(
            content=_payload(
                [
                    {"title": "Good", "description": "D"},
                    {"title": "   ", "description": "D"},
                    {"title": "Also good", "description": "D"},
                ]
            )
        )
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model"
        )
        result = await gen.generate(_ctx(count=3))
        titles = [r.title for r in result]
        assert "Good" in titles
        assert "Also good" in titles
        assert "   " not in titles

    async def test_prompt_includes_context(self) -> None:
        provider = _StubProvider(content="[]")
        gen = LLMGenerator(
            provider=cast(CompletionProvider, provider), model="test-model-123"
        )
        await gen.generate(
            GenerationContext(
                project_id="project-xyz",
                domain="payments",
                count=5,
            )
        )
        assert provider.captured_model == "test-model-123"
        assert provider.captured_messages is not None
        prompt_text = " ".join(m.content or "" for m in provider.captured_messages)
        assert "project-xyz" in prompt_text
        assert "payments" in prompt_text
        assert "5" in prompt_text

    async def test_propagates_provider_errors(self) -> None:
        class _FailingProvider(_StubProvider):
            async def complete(
                self,
                messages: list[ChatMessage],
                model: str,
                *,
                tools: list[ToolDefinition] | None = None,
                config: CompletionConfig | None = None,
            ) -> CompletionResponse:
                del messages, model, tools, config
                msg = "network down"
                raise RuntimeError(msg)

        gen = LLMGenerator(
            provider=cast(CompletionProvider, _FailingProvider(content=None)),
            model="test-model",
        )
        with pytest.raises(RuntimeError, match="network down"):
            await gen.generate(_ctx())
