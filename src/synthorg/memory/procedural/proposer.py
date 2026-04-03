"""LLM-based proposer for procedural memory entries.

Uses a SEPARATE completion provider call (not the failed agent) to
analyse a structured failure payload and produce a procedural memory
proposal.  Follows the ``AbstractiveSummarizer`` error-handling
pattern from ``memory.consolidation.abstractive``.
"""

import json
import re
from typing import Any

from synthorg.memory.procedural.models import (
    FailureAnalysisPayload,
    ProceduralMemoryConfig,
    ProceduralMemoryProposal,
)
from synthorg.observability import get_logger
from synthorg.observability.events.procedural_memory import (
    PROCEDURAL_MEMORY_LOW_CONFIDENCE,
    PROCEDURAL_MEMORY_PROPOSED,
    PROCEDURAL_MEMORY_SKIPPED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.errors import ProviderError
from synthorg.providers.models import ChatMessage, CompletionConfig
from synthorg.providers.protocol import CompletionProvider  # noqa: TC001

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a failure analysis assistant. Given a structured description "
    "of an agent task failure, produce a procedural memory entry that "
    "helps future agents avoid the same failure.\n\n"
    "Respond with a JSON object containing exactly these fields:\n"
    '- "discovery": A one-sentence summary (~100 tokens) for retrieval.\n'
    '- "condition": When this knowledge should be applied.\n'
    '- "action": What to do differently next time.\n'
    '- "rationale": Why this approach helps.\n'
    '- "confidence": Your confidence in this proposal (0.0-1.0).\n'
    '- "tags": List of semantic tags (e.g. ["timeout", "tool_failure"]).\n\n'
    "Respond ONLY with the JSON object, no markdown fences or explanation."
)

_JSON_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```",
    re.DOTALL,
)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from LLM response text.

    Handles plain JSON and markdown-fenced JSON blocks.
    Returns ``None`` on parse failure.
    """
    stripped = text.strip()
    if not stripped:
        return None

    # Try stripping markdown fences first.
    match = _JSON_FENCE_PATTERN.search(stripped)
    candidate = match.group(1).strip() if match else stripped

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _build_user_message(payload: FailureAnalysisPayload) -> str:
    """Format the payload into a user message for the proposer LLM."""
    tools = ", ".join(payload.tool_calls_made) if payload.tool_calls_made else "none"
    return (
        f"Task: {payload.task_title}\n"
        f"Description: {payload.task_description}\n"
        f"Type: {payload.task_type.value}\n"
        f"Error: {payload.error_message}\n"
        f"Termination: {payload.termination_reason}\n"
        f"Recovery strategy: {payload.strategy_type}\n"
        f"Turns completed: {payload.turn_count}\n"
        f"Tools used: {tools}\n"
        f"Retry {payload.retry_count}/{payload.max_retries} "
        f"(can reassign: {payload.can_reassign})"
    )


class ProceduralMemoryProposer:
    """Generates procedural memory proposals from failure analysis.

    Uses a separate LLM call to analyse a structured failure payload
    and produce a ``ProceduralMemoryProposal``.  Non-retryable
    provider errors propagate; retryable errors return ``None``.

    Args:
        provider: Completion provider for the proposer LLM call.
        config: Procedural memory configuration.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        config: ProceduralMemoryConfig,
    ) -> None:
        self._provider = provider
        self._config = config
        self._completion_config = CompletionConfig(
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    async def propose(
        self,
        payload: FailureAnalysisPayload,
    ) -> ProceduralMemoryProposal | None:
        """Analyse failure and propose a procedural memory entry.

        Returns ``None`` when the LLM response is empty, malformed,
        or below the confidence threshold.  Non-retryable provider
        errors propagate to the caller.

        Args:
            payload: Structured failure context.

        Returns:
            A validated proposal, or ``None`` if skipped.
        """
        try:
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT),
                ChatMessage(
                    role=MessageRole.USER,
                    content=_build_user_message(payload),
                ),
            ]
            response = await self._provider.complete(
                messages,
                self._config.model,
                config=self._completion_config,
            )
        except MemoryError, RecursionError:
            raise
        except ProviderError as exc:
            if not exc.is_retryable:
                raise
            logger.warning(
                PROCEDURAL_MEMORY_SKIPPED,
                task_id=payload.task_id,
                error=str(exc),
                reason="retryable_provider_error",
            )
            return None
        except Exception as exc:
            logger.warning(
                PROCEDURAL_MEMORY_SKIPPED,
                task_id=payload.task_id,
                error=f"{type(exc).__name__}: {exc}",
                reason="unexpected_error",
            )
            return None

        return self._parse_response(response.content, payload.task_id)

    def _parse_response(
        self,
        content: str | None,
        task_id: str,
    ) -> ProceduralMemoryProposal | None:
        """Parse and validate the LLM response into a proposal."""
        if not content or not content.strip():
            logger.debug(
                PROCEDURAL_MEMORY_SKIPPED,
                task_id=task_id,
                reason="empty_response",
            )
            return None

        data = _extract_json(content)
        if data is None:
            logger.warning(
                PROCEDURAL_MEMORY_SKIPPED,
                task_id=task_id,
                reason="malformed_json",
            )
            return None

        try:
            proposal = ProceduralMemoryProposal(**data)
        except Exception as exc:
            logger.warning(
                PROCEDURAL_MEMORY_SKIPPED,
                task_id=task_id,
                error=str(exc),
                reason="validation_failed",
            )
            return None

        if proposal.confidence < self._config.min_confidence:
            logger.info(
                PROCEDURAL_MEMORY_LOW_CONFIDENCE,
                task_id=task_id,
                confidence=proposal.confidence,
                min_confidence=self._config.min_confidence,
            )
            return None

        logger.info(
            PROCEDURAL_MEMORY_PROPOSED,
            task_id=task_id,
            confidence=proposal.confidence,
            tags=proposal.tags,
        )
        return proposal
