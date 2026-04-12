"""Experience compressor protocol and LLM implementation.

Defines the ``ExperienceCompressor`` protocol for compressing raw
execution traces into concise strategic learnings (GEMS two-tier
architecture).
"""

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import uuid4

from synthorg.memory.consolidation.models import (
    CompressedExperience,
)
from synthorg.memory.models import MemoryEntry, MemoryMetadata
from synthorg.observability import get_logger
from synthorg.observability.events.consolidation import (
    EXPERIENCE_COMPRESSED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, CompletionConfig

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.consolidation.config import (
        ExperienceCompressorConfig,
    )
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)


@runtime_checkable
class ExperienceCompressor(Protocol):
    """Compresses raw traces into concise experiences.

    Fidelity target: compressed summaries must reproduce at least 80%
    of strategic decisions from raw traces on a held-out test set.
    """

    async def compress(  # noqa: PLR0913
        self,
        prompt: NotBlankStr,
        output: NotBlankStr,
        verification_feedback: NotBlankStr | None,
        reasoning_trace: tuple[NotBlankStr, ...],
        memory_context: tuple[MemoryEntry, ...],
        *,
        agent_id: NotBlankStr = "unknown",
    ) -> CompressedExperience:
        """Compress a single raw experience into strategic learnings.

        Args:
            prompt: Raw prompt sent to the agent.
            output: Raw output produced by the agent.
            verification_feedback: Verification result text
                (``None`` when no verification was performed).
            reasoning_trace: Step-by-step reasoning trace entries.
            memory_context: Related memories for compression context.
            agent_id: Agent owning the experience (for provenance).

        Returns:
            Compressed experience with strategic decisions and
            applicable contexts.

        Raises:
            Exception: On LLM call failure (caller decides fallback
                behaviour).
        """
        ...


_COMPRESSOR_SYSTEM_PROMPT = """\
You are a memory compressor. Given a raw execution trace (prompt, \
output, verification feedback, reasoning steps), extract the strategic \
learnings.

Respond with JSON:
{{
  "strategic_decisions": ["what worked or didn't", ...],
  "applicable_contexts": ["when this applies", ...]
}}

Focus on:
- Key decisions that led to success or failure
- Reusable patterns and anti-patterns
- Context-specific applicability

Be concise. Each decision should be one sentence. \
Each context should describe when the lesson applies.
"""

_COMPRESSOR_VERSION = "llm-v1"


class LLMExperienceCompressor:
    """LLM-based experience compressor (GEMS strategy).

    Uses a medium-tier model to compress raw execution traces into
    strategic learnings with applicable contexts.

    Args:
        provider: Completion provider for LLM calls.
        model: Model identifier (medium-tier recommended).
        config: Compressor configuration.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model: NotBlankStr,
        config: ExperienceCompressorConfig,
    ) -> None:
        self._provider = provider
        self._model = model
        self._config = config

    async def compress(  # noqa: PLR0913
        self,
        prompt: NotBlankStr,
        output: NotBlankStr,
        verification_feedback: NotBlankStr | None,
        reasoning_trace: tuple[NotBlankStr, ...],
        memory_context: tuple[MemoryEntry, ...],
        *,
        agent_id: NotBlankStr = "unknown",
    ) -> CompressedExperience:
        """Compress a single raw experience via LLM.

        Args:
            prompt: Raw prompt sent to the agent.
            output: Raw output produced by the agent.
            verification_feedback: Verification result text.
            reasoning_trace: Step-by-step reasoning trace entries.
            memory_context: Related memories for compression context.
            agent_id: Agent owning the experience (for provenance).

        Returns:
            Compressed experience with strategic decisions.

        Raises:
            Exception: On LLM call failure (not silently swallowed).
        """
        user_parts = [
            f"## Prompt\n{prompt}",
            f"## Output\n{output}",
        ]
        if verification_feedback:
            user_parts.append(
                f"## Verification\n{verification_feedback}",
            )
        if reasoning_trace:
            trace_text = "\n".join(f"- {step}" for step in reasoning_trace)
            user_parts.append(f"## Reasoning\n{trace_text}")
        if memory_context:
            context_text = "\n".join(f"- {m.content[:200]}" for m in memory_context[:5])
            user_parts.append(f"## Memory Context\n{context_text}")

        user_content = "\n\n".join(user_parts)
        raw_len = len(user_content)

        messages: list[ChatMessage] = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=_COMPRESSOR_SYSTEM_PROMPT,
            ),
            ChatMessage(role=MessageRole.USER, content=user_content),
        ]

        completion_config = CompletionConfig(
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        response = await self._provider.complete(
            messages,
            self._model,
            config=completion_config,
        )
        if response.content is None:
            msg = "LLM returned empty content for compression"
            raise ValueError(msg)

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError as exc:
            logger.warning(
                EXPERIENCE_COMPRESSED,
                error=f"JSON decode failed: {exc}",
                raw_content=response.content[:200],
            )
            raise
        if not isinstance(parsed, dict):
            msg = f"LLM returned non-dict: {type(parsed).__name__}"
            logger.warning(
                EXPERIENCE_COMPRESSED,
                error=msg,
            )
            raise TypeError(msg)
        raw_decisions = parsed.get("strategic_decisions", [])
        raw_contexts = parsed.get("applicable_contexts", [])
        if not isinstance(raw_decisions, list) or not all(
            isinstance(d, str) for d in raw_decisions
        ):
            msg = "strategic_decisions must be a list of strings"
            logger.warning(EXPERIENCE_COMPRESSED, error=msg)
            raise ValueError(msg)
        if not isinstance(raw_contexts, list) or not all(
            isinstance(c, str) for c in raw_contexts
        ):
            msg = "applicable_contexts must be a list of strings"
            logger.warning(EXPERIENCE_COMPRESSED, error=msg)
            raise ValueError(msg)
        decisions = tuple(raw_decisions)
        contexts = tuple(raw_contexts)

        if not decisions:
            msg = "LLM produced no strategic decisions"
            logger.warning(EXPERIENCE_COMPRESSED, error=msg)
            raise ValueError(msg)

        compressed_len = len(response.content)
        ratio = compressed_len / max(raw_len, 1)
        ratio = min(ratio, 1.0)

        experience = CompressedExperience(
            id=str(uuid4()),
            agent_id=agent_id,
            strategic_decisions=decisions,
            applicable_contexts=contexts,
            source_artifact_ids=(),
            compression_ratio=max(ratio, 0.01),
            compressor_version=_COMPRESSOR_VERSION,
            metadata=MemoryMetadata(
                tags=("compressed_experience",),
            ),
            created_at=datetime.now(UTC),
        )
        logger.info(
            EXPERIENCE_COMPRESSED,
            decisions_count=len(decisions),
            contexts_count=len(contexts),
            compression_ratio=experience.compression_ratio,
        )
        return experience
