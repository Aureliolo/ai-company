"""LLM-based proposer for adaptation proposals.

Uses a SEPARATE completion provider call to analyze evolution context
and generate adaptation proposals. Follows the EvoSkill principle:
the agent being evolved does NOT propose its own changes.
"""

import json
import re
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from synthorg.engine.evolution.models import (
    AdaptationProposal,
)
from synthorg.observability import get_logger
from synthorg.observability.events.evolution import (
    EVOLUTION_PROPOSER_ANALYZE,
    EVOLUTION_PROPOSER_INIT,
    EVOLUTION_PROPOSER_PARSE_ERROR,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.errors import ProviderError
from synthorg.providers.models import ChatMessage, CompletionConfig
from synthorg.providers.protocol import CompletionProvider  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.evolution.protocols import EvolutionContext

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an agent evolution analyst. Given an agent's current "
    "identity, performance data, and recent task results, propose "
    "zero or more structured adaptations to improve its behavior.\n\n"
    "Respond with a JSON object containing exactly this field:\n"
    '- "proposals": A list of proposed adaptations.\n\n'
    "Each proposal must have:\n"
    '- "axis": "identity", "strategy_selection", or "prompt_template"\n'
    '- "description": A one-sentence description of the change\n'
    '- "changes": A dict with axis-specific changes\n'
    '- "confidence": Your confidence (0.0-1.0)\n'
    '- "source": "failure", "success", "inflection", or "scheduled"\n\n'
    "Return an empty proposals list if no adaptations are warranted.\n"
    "Respond ONLY with the JSON object, no markdown or explanation."
)

_JSON_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```",
    re.DOTALL,
)


def _extract_json_block(text: str) -> str | None:
    """Extract JSON content from markdown fence or plain text.

    Tries to strip markdown fences; falls back to plain text.

    Args:
        text: Response text from LLM.

    Returns:
        Candidate JSON string or None if empty.
    """
    stripped = text.strip()
    if not stripped:
        return None
    match = _JSON_FENCE_PATTERN.search(stripped)
    return match.group(1).strip() if match else stripped


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from LLM response text.

    Handles plain JSON and markdown-fenced JSON blocks.
    Returns None on parse failure.

    Args:
        text: Response text from LLM.

    Returns:
        Parsed dict or None if extraction fails.
    """
    candidate = _extract_json_block(text)
    if candidate is None:
        return None

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        logger.debug(
            EVOLUTION_PROPOSER_PARSE_ERROR,
            reason="json_decode_error",
            detail=str(exc),
        )
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _validate_proposals_list(
    data: dict[str, Any],
    agent_id: NotBlankStr,
) -> list[Any] | None:
    """Validate that data has a "proposals" key with a list value.

    Args:
        data: Parsed JSON dict.
        agent_id: Agent identifier for logging.

    Returns:
        The proposals list or None if validation fails.
    """
    proposals_data = data.get("proposals")
    if proposals_data is None:
        logger.warning(
            EVOLUTION_PROPOSER_PARSE_ERROR,
            agent_id=str(agent_id),
            reason="missing_proposals_key",
        )
        return None

    if not isinstance(proposals_data, list):
        logger.warning(
            EVOLUTION_PROPOSER_PARSE_ERROR,
            agent_id=str(agent_id),
            reason="proposals_not_list",
        )
        return None

    return proposals_data


def _build_user_message(
    agent_id: NotBlankStr,
    context: EvolutionContext,
) -> str:
    """Format the context into a user message for the proposer LLM.

    Args:
        agent_id: Target agent identifier.
        context: Evolution context with identity, performance, and memory data.

    Returns:
        Formatted user message string.
    """
    identity_str = (
        f"Name: {context.identity.name}, Level: "
        f"{context.identity.level}, Role: {context.identity.role}"
    )

    perf_str = "No performance data"
    if context.performance_snapshot:
        perf_str = (
            f"Quality: {context.performance_snapshot.overall_quality_score}, "
            f"Collaboration: "
            f"{context.performance_snapshot.overall_collaboration_score}"
        )

    # TODO: Pass actual task/memory content instead of just counts.
    # Currently the LLM only sees the count of recent tasks and procedural
    # memories, not their actual content. This is a limitation that should be
    # addressed in a follow-up feature to provide richer context for proposals.
    tasks_str = (
        f"{len(context.recent_task_results)} recent tasks"
        if context.recent_task_results
        else "No recent task data"
    )
    memories_str = (
        f"{len(context.recent_procedural_memories)} procedural memories"
        if context.recent_procedural_memories
        else "No procedural memories"
    )

    return (
        "[BEGIN EVOLUTION CONTEXT]\n"
        f"Agent ID: {agent_id}\n"
        f"Identity: {identity_str}\n"
        f"Performance: {perf_str}\n"
        f"Recent Tasks: {tasks_str}\n"
        f"Procedural Memories: {memories_str}\n"
        "[END EVOLUTION CONTEXT]"
    )


class SeparateAnalyzerProposer:
    """Generates adaptation proposals via dedicated LLM analysis.

    Uses a separate completion provider call to analyze evolution context
    and produce adaptation proposals. Follows the EvoSkill principle:
    the target agent does NOT propose its own changes.

    Args:
        provider: Completion provider for the proposer LLM call.
        model: Model identifier to use for analysis.
        temperature: Sampling temperature (default: 0.3).
        max_tokens: Maximum tokens to generate (default: 2000).
    """

    def __init__(
        self,
        provider: CompletionProvider,
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> None:
        self._provider = provider
        self._model = model
        self._completion_config = CompletionConfig(
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.debug(
            EVOLUTION_PROPOSER_INIT,
            proposer="separate_analyzer",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @property
    def name(self) -> str:
        """Human-readable proposer name."""
        return "separate_analyzer"

    async def propose(
        self,
        *,
        agent_id: NotBlankStr,
        context: EvolutionContext,
    ) -> tuple[AdaptationProposal, ...]:
        """Generate zero or more adaptation proposals.

        Args:
            agent_id: Agent to generate proposals for.
            context: Evolution context with identity, performance,
                and memory data.

        Returns:
            Tuple of proposals (empty if no adaptations suggested).
        """
        try:
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT),
                ChatMessage(
                    role=MessageRole.USER,
                    content=_build_user_message(agent_id, context),
                ),
            ]
            response = await self._provider.complete(
                messages,
                self._model,
                config=self._completion_config,
            )
        except MemoryError, RecursionError:
            raise
        except ProviderError as exc:
            if not exc.is_retryable:
                raise
            logger.warning(
                EVOLUTION_PROPOSER_PARSE_ERROR,
                agent_id=str(agent_id),
                error=f"{type(exc).__name__}: {exc}",
                reason="provider_error_retryable",
                is_retryable=True,
                exc_info=True,
            )
            return ()
        except Exception as exc:
            logger.warning(
                EVOLUTION_PROPOSER_PARSE_ERROR,
                agent_id=str(agent_id),
                error=f"{type(exc).__name__}: {exc}",
                reason="provider_error",
                is_retryable=False,
                exc_info=True,
            )
            return ()

        return self._parse_response(response.content, agent_id)

    def _parse_response(
        self,
        content: str | None,
        agent_id: NotBlankStr,
    ) -> tuple[AdaptationProposal, ...]:
        """Parse and validate the LLM response into proposals.

        Args:
            content: Response content from LLM.
            agent_id: Agent identifier for proposal context.

        Returns:
            Tuple of validated proposals (empty on parse/validation failure).
        """
        if not content or not content.strip():
            logger.debug(
                EVOLUTION_PROPOSER_PARSE_ERROR,
                agent_id=str(agent_id),
                reason="empty_response",
            )
            return ()

        data = _extract_json(content)
        if data is None:
            logger.warning(
                EVOLUTION_PROPOSER_PARSE_ERROR,
                agent_id=str(agent_id),
                reason="malformed_json",
            )
            return ()

        proposals_data = _validate_proposals_list(data, agent_id)
        if proposals_data is None:
            return ()

        return self._validate_and_build_proposals(proposals_data, agent_id)

    def _validate_and_build_proposals(
        self,
        proposals_data: list[Any],
        agent_id: NotBlankStr,
    ) -> tuple[AdaptationProposal, ...]:
        """Validate and build AdaptationProposal objects from parsed data.

        Args:
            proposals_data: List of proposal dicts from LLM response.
            agent_id: Agent identifier for proposal context.

        Returns:
            Tuple of validated proposals (skips invalid ones).
        """
        proposals: list[AdaptationProposal] = []
        for idx, item in enumerate(proposals_data):
            try:
                proposal_dict = {
                    "agent_id": str(agent_id),
                    **item,
                }
                proposal = AdaptationProposal(**proposal_dict)
                proposals.append(proposal)
                logger.debug(
                    EVOLUTION_PROPOSER_ANALYZE,
                    agent_id=str(agent_id),
                    axis=proposal.axis,
                    confidence=proposal.confidence,
                    source=proposal.source,
                )
            except ValidationError as exc:
                logger.warning(
                    EVOLUTION_PROPOSER_PARSE_ERROR,
                    agent_id=str(agent_id),
                    proposal_index=idx,
                    error=str(exc),
                    reason="validation_failed",
                    exc_info=True,
                )
                continue

        return tuple(proposals)
