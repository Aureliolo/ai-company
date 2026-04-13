"""LLM-based rubric grader (not yet implemented)."""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.verification import (
    VERIFICATION_GRADING_STARTED,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.quality.verification import (
        AtomicProbe,
        VerificationResult,
        VerificationRubric,
    )
    from synthorg.engine.workflow.handoff import HandoffArtifact

logger = get_logger(__name__)


class LLMRubricGrader:
    """LLM-targeted grader (not yet implemented).

    Will evaluate artifacts via LLM with parallel probe workers
    once provider injection is wired.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "llm"

    async def grade(
        self,
        *,
        artifact: HandoffArtifact,  # noqa: ARG002
        rubric: VerificationRubric,
        probes: tuple[AtomicProbe, ...],  # noqa: ARG002
        generator_agent_id: NotBlankStr,  # noqa: ARG002
        evaluator_agent_id: NotBlankStr,  # noqa: ARG002
    ) -> VerificationResult:
        """Grade artifact against rubric via LLM.

        Raises:
            NotImplementedError: Always -- LLM provider not yet wired.
        """
        logger.error(
            VERIFICATION_GRADING_STARTED,
            rubric_name=rubric.name,
            grader=self.name,
            note="LLM grader not implemented",
        )
        msg = "LLM-based rubric grading not yet implemented"
        raise NotImplementedError(msg)
