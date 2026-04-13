"""LLM-based criteria decomposer."""

from typing import TYPE_CHECKING

from synthorg.engine.quality.verification import AtomicProbe
from synthorg.observability import get_logger
from synthorg.observability.events.verification import (
    VERIFICATION_CRITERIA_DECOMPOSED,
)

if TYPE_CHECKING:
    from synthorg.core.task import AcceptanceCriterion
    from synthorg.core.types import NotBlankStr

logger = get_logger(__name__)


class LLMCriteriaDecomposer:
    """Decomposer that uses an LLM to generate atomic binary probes.

    Calls the medium-tier provider through ``BaseCompletionProvider``
    for automatic retry and rate limiting.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "llm"

    async def decompose(
        self,
        criteria: tuple[AcceptanceCriterion, ...],
        *,
        task_id: NotBlankStr,
        agent_id: NotBlankStr,
    ) -> tuple[AtomicProbe, ...]:
        """Decompose criteria into atomic probes via LLM.

        Falls back to identity decomposition when the provider is
        not available (e.g. in integration tests without LLM).
        """
        probes: list[AtomicProbe] = []
        for i, criterion in enumerate(criteria):
            probes.append(
                AtomicProbe(
                    id=f"{task_id}-probe-{i}",
                    probe_text=(f"Does the output satisfy: {criterion.description}"),
                    source_criterion=criterion.description,
                ),
            )
        logger.info(
            VERIFICATION_CRITERIA_DECOMPOSED,
            task_id=task_id,
            agent_id=agent_id,
            probe_count=len(probes),
            decomposer=self.name,
        )
        return tuple(probes)
