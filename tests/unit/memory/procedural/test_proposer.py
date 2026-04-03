"""Tests for the procedural memory proposer (LLM-based analysis)."""

import json
from unittest.mock import AsyncMock

import pytest
import structlog.testing

from synthorg.core.enums import TaskType
from synthorg.memory.procedural.models import (
    FailureAnalysisPayload,
    ProceduralMemoryConfig,
    ProceduralMemoryProposal,
)
from synthorg.memory.procedural.proposer import ProceduralMemoryProposer
from synthorg.observability.events.procedural_memory import (
    PROCEDURAL_MEMORY_LOW_CONFIDENCE,
    PROCEDURAL_MEMORY_PROPOSED,
    PROCEDURAL_MEMORY_SKIPPED,
)
from synthorg.providers.enums import FinishReason
from synthorg.providers.errors import (
    AuthenticationError,
    ProviderTimeoutError,
)
from synthorg.providers.models import CompletionResponse, TokenUsage, ToolCall


def _make_payload(**overrides: object) -> FailureAnalysisPayload:
    defaults: dict[str, object] = {
        "task_id": "task-001",
        "task_title": "Implement auth module",
        "task_description": "Create JWT authentication.",
        "task_type": TaskType.DEVELOPMENT,
        "error_message": "LLM timeout after 30s",
        "strategy_type": "fail_reassign",
        "termination_reason": "error",
        "turn_count": 5,
        "tool_calls_made": ("code_search", "run_tests"),
        "retry_count": 0,
        "max_retries": 2,
        "can_reassign": True,
    }
    defaults.update(overrides)
    return FailureAnalysisPayload(**defaults)


_VALID_PROPOSAL_JSON = json.dumps(
    {
        "discovery": "When facing LLM timeouts, break task into smaller steps.",
        "condition": "Task exceeds 10 turns without progress.",
        "action": "Decompose the task into subtasks before retrying.",
        "rationale": "Smaller tasks reduce context window pressure.",
        "confidence": 0.85,
        "tags": ["timeout", "decomposition"],
    },
)

_LOW_CONFIDENCE_JSON = json.dumps(
    {
        "discovery": "Unclear pattern.",
        "condition": "Unknown.",
        "action": "Try again.",
        "rationale": "Maybe it works.",
        "confidence": 0.2,
        "tags": [],
    },
)


def _make_response(content: str | None = _VALID_PROPOSAL_JSON) -> CompletionResponse:
    return CompletionResponse(
        content=content,
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.001),
        model="test-small-001",
    )


def _make_proposer(
    response: CompletionResponse | None = None,
    *,
    side_effect: Exception | None = None,
    min_confidence: float = 0.5,
) -> tuple[ProceduralMemoryProposer, AsyncMock]:
    provider = AsyncMock()
    if side_effect is not None:
        provider.complete = AsyncMock(side_effect=side_effect)
    else:
        provider.complete = AsyncMock(
            return_value=response or _make_response(),
        )
    config = ProceduralMemoryConfig(
        model="test-small-001",
        min_confidence=min_confidence,
    )
    proposer = ProceduralMemoryProposer(provider=provider, config=config)
    return proposer, provider


@pytest.mark.unit
class TestProceduralMemoryProposer:
    async def test_happy_path_returns_proposal(self) -> None:
        proposer, provider = _make_proposer()
        result = await proposer.propose(_make_payload())

        assert result is not None
        assert isinstance(result, ProceduralMemoryProposal)
        assert result.discovery.startswith("When facing")
        assert result.confidence == 0.85
        assert result.tags == ("timeout", "decomposition")
        provider.complete.assert_awaited_once()

    async def test_uses_configured_model(self) -> None:
        proposer, provider = _make_proposer()
        await proposer.propose(_make_payload())

        call_args = provider.complete.call_args
        assert call_args[0][1] == "test-small-001"

    async def test_sends_system_and_user_messages(self) -> None:
        proposer, provider = _make_proposer()
        await proposer.propose(_make_payload())

        messages = provider.complete.call_args[0][0]
        assert len(messages) == 2
        assert messages[0].role.value == "system"
        assert messages[1].role.value == "user"

    async def test_user_message_contains_task_context(self) -> None:
        proposer, provider = _make_proposer()
        payload = _make_payload(task_title="Fix database migration")
        await proposer.propose(payload)

        user_msg = provider.complete.call_args[0][0][1].content
        assert "Fix database migration" in user_msg
        assert "LLM timeout after 30s" in user_msg

    async def test_low_confidence_returns_none(self) -> None:
        response = _make_response(_LOW_CONFIDENCE_JSON)
        proposer, _ = _make_proposer(response, min_confidence=0.5)

        with structlog.testing.capture_logs() as logs:
            result = await proposer.propose(_make_payload())

        assert result is None
        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_LOW_CONFIDENCE in events

    async def test_retryable_provider_error_returns_none(self) -> None:
        proposer, _ = _make_proposer(
            side_effect=ProviderTimeoutError("timeout"),
        )

        with structlog.testing.capture_logs() as logs:
            result = await proposer.propose(_make_payload())

        assert result is None
        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_SKIPPED in events

    async def test_non_retryable_provider_error_raises(self) -> None:
        proposer, _ = _make_proposer(
            side_effect=AuthenticationError("bad key"),
        )

        with pytest.raises(AuthenticationError):
            await proposer.propose(_make_payload())

    async def test_malformed_json_returns_none(self) -> None:
        response = _make_response("not valid json {{{")
        proposer, _ = _make_proposer(response)

        with structlog.testing.capture_logs() as logs:
            result = await proposer.propose(_make_payload())

        assert result is None
        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_SKIPPED in events

    async def test_empty_response_returns_none(self) -> None:
        """Provider returns content=None via tool_calls path."""
        response = CompletionResponse(
            content=None,
            finish_reason=FinishReason.TOOL_USE,
            usage=TokenUsage(input_tokens=100, output_tokens=0, cost_usd=0.0),
            model="test-small-001",
            tool_calls=(ToolCall(id="tc-1", name="noop", arguments={}),),
        )
        proposer, _ = _make_proposer(response)

        result = await proposer.propose(_make_payload())
        assert result is None

    async def test_whitespace_response_returns_none(self) -> None:
        response = _make_response("   ")
        proposer, _ = _make_proposer(response)

        result = await proposer.propose(_make_payload())
        assert result is None

    async def test_markdown_fenced_json_parsed(self) -> None:
        fenced = f"```json\n{_VALID_PROPOSAL_JSON}\n```"
        response = _make_response(fenced)
        proposer, _ = _make_proposer(response)

        result = await proposer.propose(_make_payload())
        assert result is not None
        assert result.confidence == 0.85

    async def test_logs_proposed_event(self) -> None:
        proposer, _ = _make_proposer()

        with structlog.testing.capture_logs() as logs:
            await proposer.propose(_make_payload())

        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_PROPOSED in events

    async def test_generic_exception_returns_none(self) -> None:
        proposer, _ = _make_proposer(side_effect=RuntimeError("unexpected"))

        with structlog.testing.capture_logs() as logs:
            result = await proposer.propose(_make_payload())

        assert result is None
        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_SKIPPED in events
