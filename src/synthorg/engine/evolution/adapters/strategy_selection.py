"""StrategySelectionAdapter -- stores strategy preferences as procedural memory."""

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


class StrategySelectionAdapter:
    """Stores strategy preferences as procedural memory.

    Converts a strategy selection adaptation into a procedural memory entry
    with the tag "evolution-strategy" for later retrieval and reuse.
    """

    def __init__(self, memory_backend: MemoryBackend) -> None:
        """Initialize StrategySelectionAdapter.

        Args:
            memory_backend: Memory storage backend.
        """
        self._memory_backend = memory_backend

    @property
    def name(self) -> str:
        """Return adapter name."""
        return "StrategySelectionAdapter"

    @property
    def axis(self) -> AdaptationAxis:
        """Return the adaptation axis this adapter handles."""
        return AdaptationAxis.STRATEGY_SELECTION

    async def apply(
        self,
        proposal: AdaptationProposal,
        agent_id: NotBlankStr,
    ) -> None:
        """Apply the strategy selection adaptation.

        Stores the proposal as a procedural memory entry tagged with
        "evolution-strategy" for organizational use.

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
                    tags=("evolution-strategy",),
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
