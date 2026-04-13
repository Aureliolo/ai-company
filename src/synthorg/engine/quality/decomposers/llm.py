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
    """LLM-targeted decomposer (stub -- currently identity fallback).

    Intended to call the medium-tier provider for multi-probe
    decomposition.  Currently uses identity decomposition
    (one probe per criterion) as a placeholder.
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
        """Decompose criteria into atomic probes.

        LLM-based decomposition not yet wired; currently uses
        identity decomposition (one probe per criterion).
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
