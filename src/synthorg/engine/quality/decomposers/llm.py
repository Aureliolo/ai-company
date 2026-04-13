"""LLM-based criteria decomposer."""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.verification import (
    VERIFICATION_CRITERIA_DECOMPOSED,
)

if TYPE_CHECKING:
    from synthorg.core.task import AcceptanceCriterion
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.quality.verification import AtomicProbe

logger = get_logger(__name__)


class LLMCriteriaDecomposer:
    """LLM-targeted decomposer (not yet implemented).

    Will call the medium-tier provider for multi-probe
    decomposition once provider injection is wired.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "llm"

    async def decompose(
        self,
        criteria: tuple[AcceptanceCriterion, ...],  # noqa: ARG002
        *,
        task_id: NotBlankStr,
        agent_id: NotBlankStr,
    ) -> tuple[AtomicProbe, ...]:
        """Decompose criteria into atomic probes via LLM.

        Raises:
            NotImplementedError: Always -- LLM provider not yet wired.
        """
        logger.error(
            VERIFICATION_CRITERIA_DECOMPOSED,
            task_id=task_id,
            agent_id=agent_id,
            decomposer=self.name,
            note="LLM decomposer not implemented",
        )
        msg = "LLM-based criteria decomposition not yet implemented"
        raise NotImplementedError(msg)
