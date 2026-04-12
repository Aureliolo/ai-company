"""Experience compressor protocol and LLM implementation.

Defines the ``ExperienceCompressor`` protocol for compressing raw
execution traces into concise strategic learnings (GEMS two-tier
architecture).
"""

from typing import Protocol, runtime_checkable

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.consolidation.models import (
    CompressedExperience,  # noqa: TC001
)
from synthorg.memory.models import MemoryEntry  # noqa: TC001


@runtime_checkable
class ExperienceCompressor(Protocol):
    """Compresses raw traces into concise experiences.

    Fidelity target: compressed summaries must reproduce at least 80%
    of strategic decisions from raw traces on a held-out test set.
    """

    async def compress(
        self,
        prompt: NotBlankStr,
        output: NotBlankStr,
        verification_feedback: NotBlankStr | None,
        reasoning_trace: tuple[NotBlankStr, ...],
        memory_context: tuple[MemoryEntry, ...],
    ) -> CompressedExperience:
        """Compress a single raw experience into strategic learnings.

        Args:
            prompt: Raw prompt sent to the agent.
            output: Raw output produced by the agent.
            verification_feedback: Verification result text
                (``None`` when no verification was performed).
            reasoning_trace: Step-by-step reasoning trace entries.
            memory_context: Related memories for compression context.

        Returns:
            Compressed experience with strategic decisions and
            applicable contexts.

        Raises:
            ProviderError: On LLM call failure (caller decides
                fallback behaviour).
        """
        ...
