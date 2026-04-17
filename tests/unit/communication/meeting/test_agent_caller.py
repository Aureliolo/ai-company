"""Unit tests for the meeting agent caller factory."""

from datetime import UTC, date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import structlog

from synthorg.communication.meeting.agent_caller import (
    UnknownMeetingAgentError,
    build_meeting_agent_caller,
)
from synthorg.communication.meeting.models import AgentResponse
from synthorg.communication.meeting.protocol import AgentCaller
from synthorg.core.agent import (
    AgentIdentity,
    ModelConfig,
    PersonalityConfig,
)
from synthorg.core.enums import AgentStatus, SeniorityLevel
from synthorg.core.types import NotBlankStr
from synthorg.observability.events.meeting import (
    MEETING_AGENT_CALLED,
    MEETING_AGENT_RESPONDED,
)
from synthorg.providers.enums import FinishReason, MessageRole
from synthorg.providers.models import CompletionResponse, TokenUsage

pytestmark = pytest.mark.unit


def _identity(
    *,
    name: str = "Sarah Chen",
    role: str = "engineer",
    department: str = "engineering",
    provider: str = "example-provider",
    model_id: str = "example-medium-001",
) -> AgentIdentity:
    return AgentIdentity(
        id=uuid4(),
        name=NotBlankStr(name),
        role=NotBlankStr(role),
        department=NotBlankStr(department),
        level=SeniorityLevel.MID,
        personality=PersonalityConfig(
            traits=(NotBlankStr("analytical"), NotBlankStr("curious")),
            communication_style=NotBlankStr("concise"),
        ),
        model=ModelConfig(
            provider=NotBlankStr(provider),
            model_id=NotBlankStr(model_id),
            temperature=0.7,
            max_tokens=4096,
        ),
        hiring_date=date(2026, 1, 1),
        status=AgentStatus.ACTIVE,
    )


def _completion(
    *,
    content: str = "Here is my input.",
    input_tokens: int = 17,
    output_tokens: int = 42,
    cost_usd: float = 0.00042,
) -> CompletionResponse:
    return CompletionResponse(
        content=content,
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        ),
        model=NotBlankStr("example-medium-001"),
    )


_AGENT_ID = "agent-sarah"


def _build_caller(
    *,
    identity: AgentIdentity | None = None,
    response: CompletionResponse | None = None,
    provider_error: Exception | None = None,
) -> tuple[AgentCaller, MagicMock, MagicMock]:
    """Produce ``(caller, agent_registry, provider_registry)``."""
    agent_registry = MagicMock()
    agent_registry.get = AsyncMock(return_value=identity)

    provider = MagicMock()
    if provider_error is not None:
        provider.complete = AsyncMock(side_effect=provider_error)
    else:
        provider.complete = AsyncMock(
            return_value=response or _completion(),
        )

    provider_registry = MagicMock()
    provider_registry.get = MagicMock(return_value=provider)

    caller = build_meeting_agent_caller(
        agent_registry=agent_registry,
        provider_registry=provider_registry,
    )
    return caller, agent_registry, provider_registry


class TestBuildMeetingAgentCaller:
    async def test_round_trip_maps_completion_to_agent_response(self) -> None:
        identity = _identity()
        response = _completion(
            content="I propose adding a queue.",
            input_tokens=20,
            output_tokens=30,
            cost_usd=0.001,
        )
        caller, _registry, _providers = _build_caller(
            identity=identity,
            response=response,
        )

        result = await caller(_AGENT_ID, "Agenda: queueing", 500)
        assert isinstance(result, AgentResponse)
        assert result.agent_id == _AGENT_ID
        assert result.content == "I propose adding a queue."
        assert result.input_tokens == 20
        assert result.output_tokens == 30
        assert result.cost_usd == pytest.approx(0.001)

    async def test_unknown_agent_raises(self) -> None:
        caller, _reg, _providers = _build_caller(identity=None)
        with pytest.raises(UnknownMeetingAgentError) as exc_info:
            await caller(_AGENT_ID, "prompt", 100)
        # LookupError-compatible so callers can catch with existing
        # lookup-failure handlers.
        assert isinstance(exc_info.value, LookupError)
        # agent_id must be available as a typed attribute for
        # programmatic handling (logging, retries, metric tagging).
        assert exc_info.value.agent_id == _AGENT_ID

    async def test_empty_content_maps_to_empty_string(self) -> None:
        identity = _identity()
        caller, _reg, _providers = _build_caller(
            identity=identity,
            response=_completion(content=""),
        )
        result = await caller(_AGENT_ID, "prompt", 100)
        assert result.content == ""

    async def test_provider_error_propagates(self) -> None:
        identity = _identity()
        caller, _reg, _providers = _build_caller(
            identity=identity,
            provider_error=RuntimeError("provider boom"),
        )
        with pytest.raises(RuntimeError, match="provider boom"):
            await caller(_AGENT_ID, "prompt", 100)

    async def test_logs_called_and_responded_events(self) -> None:
        identity = _identity()
        caller, _reg, _providers = _build_caller(identity=identity)

        with structlog.testing.capture_logs() as cap:
            await caller(_AGENT_ID, "prompt", 100)
        events = [e.get("event") for e in cap]
        assert MEETING_AGENT_CALLED in events
        assert MEETING_AGENT_RESPONDED in events

    async def test_dispatches_to_agent_provider(self) -> None:
        identity = _identity(provider="example-provider")
        caller, _reg, provider_registry = _build_caller(identity=identity)
        await caller(_AGENT_ID, "prompt", 256)
        provider_registry.get.assert_called_once_with("example-provider")

    async def test_passes_max_tokens_into_completion_config(self) -> None:
        identity = _identity()
        caller, _reg, provider_registry = _build_caller(identity=identity)
        await caller(_AGENT_ID, "agenda", 777)
        provider = provider_registry.get.return_value
        provider.complete.assert_awaited_once()
        call = provider.complete.await_args
        messages = call.args[0]
        config = call.kwargs["config"]
        assert config.max_tokens == 777
        assert messages[0].role == MessageRole.SYSTEM
        assert messages[1].role == MessageRole.USER
        assert "agenda" in (messages[1].content or "")


_ = UTC  # keep datetime-aware reference for future date-sensitive tests
