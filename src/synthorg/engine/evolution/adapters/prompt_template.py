"""PromptTemplateAdapter -- injects learned memories into prompt slots."""

import json
from typing import TYPE_CHECKING

from synthorg.core.enums import MemoryCategory
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
)
from synthorg.memory.models import MemoryMetadata, MemoryStoreRequest
from synthorg.observability import get_logger
from synthorg.observability.events.evolution import EVOLUTION_ADAPTATION_FAILED

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.protocol import MemoryBackend

logger = get_logger(__name__)


class PromptTemplateAdapter:
    """Injects learned memories into prompt slots.

    Stores prompt template changes as procedural memories with the tag
    "evolution-prompt-injection" for injection into future prompts.
    """

    def __init__(self, memory_backend: MemoryBackend) -> None:
        """Initialize PromptTemplateAdapter.

        Args:
            memory_backend: Memory storage backend.
        """
        self._memory_backend = memory_backend

    @property
    def name(self) -> str:
        """Return adapter name."""
        return "PromptTemplateAdapter"

    @property
    def axis(self) -> AdaptationAxis:
        """Return the adaptation axis this adapter handles."""
        return AdaptationAxis.PROMPT_TEMPLATE

    async def apply(
        self,
        proposal: AdaptationProposal,
        agent_id: NotBlankStr,
    ) -> None:
        """Apply the prompt template adaptation.

        Stores the proposal as a procedural memory entry tagged with
        "evolution-prompt-injection" for injection into system prompts.

        Args:
            proposal: The approved proposal to apply.
            agent_id: Target agent.

        Raises:
            Exception: If the memory store operation fails.
        """
        try:
            content_parts = [proposal.description]
            if proposal.changes:
                content_parts.append(
                    "Changes: " + json.dumps(proposal.changes, indent=2),
                )
            content: NotBlankStr = "\n".join(content_parts)

            request = MemoryStoreRequest(
                category=MemoryCategory.PROCEDURAL,
                namespace="default",
                content=content,
                metadata=MemoryMetadata(
                    source=str(proposal.id),
                    confidence=proposal.confidence,
                    tags=("evolution-prompt-injection",),
                ),
            )

            await self._memory_backend.store(agent_id, request)
        except Exception as exc:
            logger.warning(
                EVOLUTION_ADAPTATION_FAILED,
                agent_id=agent_id,
                proposal_id=str(proposal.id),
                axis=proposal.axis.value,
                error=str(exc),
            )
            raise
