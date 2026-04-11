"""LLM-curated curation strategy.

Opt-in strategy that uses a dedicated analyzer agent to review
candidate items and select the most valuable subset. Falls back
to RelevanceScoreCuration when no provider is available.
"""

from typing import TYPE_CHECKING

from synthorg.hr.training.curation.relevance import (
    RelevanceScoreCuration,
)
from synthorg.hr.training.models import ContentType, TrainingItem  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_CURATION_COMPLETE,
)

if TYPE_CHECKING:
    from synthorg.core.enums import SeniorityLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.providers.protocol import CompletionProvider

from synthorg.providers.enums import MessageRole
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
)

logger = get_logger(__name__)


class LLMCurated:
    """LLM-powered curation via separate analyzer agent.

    Delegates curation to an LLM completion provider. If no
    provider is available, falls back to ``RelevanceScoreCuration``.

    Args:
        provider: LLM completion provider (optional).
        model: Model name for the analyzer.
        temperature: Sampling temperature.
        top_k: Maximum items to return.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider | None = None,
        model: str = "example-small-001",
        temperature: float = 0.3,
        top_k: int = 50,
    ) -> None:
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._top_k = top_k
        self._fallback = RelevanceScoreCuration(top_k=top_k)

    @property
    def name(self) -> str:
        """Strategy name."""
        return "llm_curated"

    async def curate(
        self,
        items: tuple[TrainingItem, ...],
        *,
        new_agent_role: NotBlankStr,
        new_agent_level: SeniorityLevel,
        content_type: ContentType,
    ) -> tuple[TrainingItem, ...]:
        """Curate items using LLM analysis.

        Falls back to relevance scoring when no provider is
        available.

        Args:
            items: Candidate items.
            new_agent_role: Role of new hire.
            new_agent_level: Seniority level.
            content_type: Content type being curated.

        Returns:
            Curated items with updated relevance scores.
        """
        if not items:
            return ()

        if self._provider is None:
            logger.warning(
                HR_TRAINING_CURATION_COMPLETE,
                strategy="llm_curated",
                fallback="relevance",
                reason="no_provider",
            )
            return await self._fallback.curate(
                items,
                new_agent_role=new_agent_role,
                new_agent_level=new_agent_level,
                content_type=content_type,
            )

        # Build prompt for the analyzer.
        item_descriptions = "\n".join(
            f"[{i}] (source: {item.source_agent_id}) {item.content[:200]}"
            for i, item in enumerate(items)
        )
        prompt = (
            f"You are a training content curator for a "
            f"{new_agent_role} ({new_agent_level.value} level).\n\n"
            f"Select the {self._top_k} most valuable "
            f"{content_type.value} items for a new hire.\n\n"
            f"Items:\n{item_descriptions}\n\n"
            f"Return the selected item indices as a "
            f"comma-separated list."
        )

        try:
            response = await self._provider.complete(
                messages=[
                    ChatMessage(
                        role=MessageRole.USER,
                        content=prompt,
                    ),
                ],
                model=self._model,
                config=CompletionConfig(
                    temperature=self._temperature,
                ),
            )
            selected_indices = self._parse_indices(
                str(response.content),
                max_index=len(items) - 1,
            )
        except Exception:
            logger.warning(
                HR_TRAINING_CURATION_COMPLETE,
                strategy="llm_curated",
                fallback="relevance",
                reason="llm_error",
            )
            return await self._fallback.curate(
                items,
                new_agent_role=new_agent_role,
                new_agent_level=new_agent_level,
                content_type=content_type,
            )

        if not selected_indices:
            return await self._fallback.curate(
                items,
                new_agent_role=new_agent_role,
                new_agent_level=new_agent_level,
                content_type=content_type,
            )

        result = tuple(
            items[idx].model_copy(
                update={
                    "relevance_score": 1.0 - (rank / len(selected_indices)),
                },
            )
            for rank, idx in enumerate(selected_indices)
        )

        logger.debug(
            HR_TRAINING_CURATION_COMPLETE,
            strategy="llm_curated",
            content_type=content_type.value,
            input_count=len(items),
            output_count=len(result),
        )
        return result

    @staticmethod
    def _parse_indices(
        text: str,
        *,
        max_index: int,
    ) -> list[int]:
        """Parse comma-separated indices from LLM response."""
        indices: list[int] = []
        for part in text.split(","):
            stripped = part.strip()
            if stripped.isdigit():
                idx = int(stripped)
                if 0 <= idx <= max_index and idx not in indices:
                    indices.append(idx)
        return indices
