"""Real :data:`AgentCaller` factory for meeting orchestration.

The meeting orchestrator invokes agents through an :data:`AgentCaller`
callable with the signature ``(agent_id, prompt, max_tokens) ->
AgentResponse``.  This module produces that callable by composing an
:class:`AgentRegistryService` (for agent identity lookup) with a
:class:`ProviderRegistry` (for LLM dispatch).

One turn = one LLM call.  Meeting protocols (round robin, position
papers, structured phases) are responsible for sequencing turns; this
module only runs a single agent's inference.
"""

from typing import TYPE_CHECKING

from synthorg.communication.meeting.models import AgentResponse
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.meeting import (
    MEETING_AGENT_CALLED,
    MEETING_AGENT_RESPONDED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, CompletionConfig

if TYPE_CHECKING:
    from synthorg.communication.meeting.protocol import AgentCaller
    from synthorg.core.agent import AgentIdentity
    from synthorg.hr.registry import AgentRegistryService
    from synthorg.providers.registry import ProviderRegistry

logger = get_logger(__name__)


class UnknownMeetingAgentError(LookupError):
    """Raised when the meeting orchestrator invokes an unregistered agent."""


def build_meeting_agent_caller(
    *,
    agent_registry: AgentRegistryService,
    provider_registry: ProviderRegistry,
) -> AgentCaller:
    """Construct a meeting :data:`AgentCaller` backed by real services.

    Args:
        agent_registry: Source of truth for agent identities.
        provider_registry: Source of truth for LLM providers.

    Returns:
        An async callback matching the :data:`AgentCaller` contract.
    """

    async def _caller(
        agent_id: str,
        prompt: str,
        max_tokens: int,
    ) -> AgentResponse:
        logger.info(
            MEETING_AGENT_CALLED,
            agent_id=agent_id,
            max_tokens=max_tokens,
            prompt_length=len(prompt),
        )
        identity = await agent_registry.get(NotBlankStr(agent_id))
        if identity is None:
            msg = (
                f"Meeting agent {agent_id!r} is not registered in the "
                f"agent registry; cannot dispatch LLM call"
            )
            raise UnknownMeetingAgentError(msg)

        provider = provider_registry.get(str(identity.model.provider))
        messages = _build_messages(identity, prompt)
        config = CompletionConfig(
            temperature=identity.model.temperature,
            max_tokens=max_tokens,
        )
        response = await provider.complete(
            messages,
            str(identity.model.model_id),
            config=config,
        )
        agent_response = AgentResponse(
            agent_id=NotBlankStr(agent_id),
            content=response.content or "",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=response.usage.cost_usd,
        )
        logger.info(
            MEETING_AGENT_RESPONDED,
            agent_id=agent_id,
            input_tokens=agent_response.input_tokens,
            output_tokens=agent_response.output_tokens,
            cost_usd=agent_response.cost_usd,
        )
        return agent_response

    return _caller


def _build_messages(
    identity: AgentIdentity,
    prompt: str,
) -> list[ChatMessage]:
    """Assemble the minimal ``system`` + ``user`` pair for a meeting turn.

    The system message is derived from the agent identity (role +
    personality traits) so the LLM stays in character across the
    meeting.  Protocols inject the full turn context into ``prompt``
    (agenda, prior contributions, lens), so the system prompt only
    carries agent-stable identity.
    """
    system_content = _render_system_prompt(identity)
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=system_content),
        ChatMessage(role=MessageRole.USER, content=prompt),
    ]


def _render_system_prompt(identity: AgentIdentity) -> str:
    """Render a compact system prompt from an :class:`AgentIdentity`."""
    lines: list[str] = [
        f"You are {identity.name}, a {identity.role} "
        f"in the {identity.department} department.",
        f"Seniority level: {identity.level.value}.",
    ]
    traits = identity.personality.traits
    if traits:
        lines.append("Personality traits: " + ", ".join(traits) + ".")
    communication_style = identity.personality.communication_style
    if communication_style:
        lines.append(f"Communication style: {communication_style}.")
    return "\n".join(lines)


class MeetingAgentCallerNotConfiguredError(RuntimeError):
    """Raised when a meeting runs without an agent + provider registry.

    The meeting orchestrator is structurally wired during Phase 1 so
    the REST surface is never 503, but calling an agent requires the
    agent registry (for identity lookup) and the provider registry
    (for LLM dispatch).  When either is absent at wire time, meetings
    that try to invoke an agent receive this error instead of the
    previous silent empty-response stub.
    """


def build_unconfigured_meeting_agent_caller(
    *,
    missing_dependencies: tuple[str, ...],
) -> AgentCaller:
    """Return a caller that raises loudly if invoked.

    Used when the orchestrator is wired before the agent / provider
    registries are available.  Surfaces the root cause to operators
    at first use rather than silently succeeding with empty content.
    """

    async def _caller(agent_id: str, _prompt: str, _max_tokens: int) -> AgentResponse:
        missing = ", ".join(missing_dependencies)
        msg = (
            f"Meeting agent caller invoked for {agent_id!r} but the "
            f"following dependencies were missing at wire time: "
            f"{missing}.  Provide them via create_app(...) so meeting "
            f"turns can dispatch real LLM calls."
        )
        raise MeetingAgentCallerNotConfiguredError(msg)

    return _caller


__all__ = [
    "MeetingAgentCallerNotConfiguredError",
    "UnknownMeetingAgentError",
    "build_meeting_agent_caller",
    "build_unconfigured_meeting_agent_caller",
]
