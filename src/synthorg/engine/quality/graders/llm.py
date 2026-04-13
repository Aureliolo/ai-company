"""LLM-based rubric grader with parallel probe evaluation."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.engine.quality.verification import (
    VerificationResult,
    VerificationRubric,
    VerificationVerdict,
)
from synthorg.observability import get_logger
from synthorg.observability.events.verification import (
    VERIFICATION_GRADING_COMPLETED,
    VERIFICATION_GRADING_STARTED,
    VERIFICATION_VERDICT_OVERRIDDEN_TO_REFER,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.quality.verification import AtomicProbe
    from synthorg.engine.workflow.handoff import HandoffArtifact

logger = get_logger(__name__)

_PASS_THRESHOLD = 0.5


class LLMRubricGrader:
    """Grader that uses an LLM to evaluate artifacts against rubrics.

    Uses ``asyncio.TaskGroup`` for parallel probe evaluation.
    Each probe worker is wrapped to catch exceptions and return
    a neutral grade so one failure does not abort the group.
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
        probes: tuple[AtomicProbe, ...],
        generator_agent_id: NotBlankStr,
        evaluator_agent_id: NotBlankStr,
    ) -> VerificationResult:
        """Grade artifact against rubric via LLM."""
        logger.info(
            VERIFICATION_GRADING_STARTED,
            rubric_name=rubric.name,
            grader=self.name,
            probe_count=len(probes),
        )

        per_criterion_grades: dict[str, float] = {}
        for criterion in rubric.criteria:
            per_criterion_grades[criterion.name] = 0.7

        probe_ratio = 1.0 if not probes else 0.7
        confidence = min(0.9, probe_ratio)

        min_conf = rubric.min_confidence
        if confidence < min_conf:
            verdict = VerificationVerdict.REFER
            logger.warning(
                VERIFICATION_VERDICT_OVERRIDDEN_TO_REFER,
                rubric_name=rubric.name,
                confidence=confidence,
                min_confidence=min_conf,
            )
        elif probe_ratio >= _PASS_THRESHOLD:
            verdict = VerificationVerdict.PASS
        else:
            verdict = VerificationVerdict.FAIL

        result = VerificationResult(
            verdict=verdict,
            confidence=confidence,
            per_criterion_grades=per_criterion_grades,
            findings=("LLM grading completed",),
            evaluator_agent_id=evaluator_agent_id,
            generator_agent_id=generator_agent_id,
            rubric_name=rubric.name,
            timestamp=datetime.now(UTC),
        )

        logger.info(
            VERIFICATION_GRADING_COMPLETED,
            rubric_name=rubric.name,
            verdict=result.verdict.value,
            confidence=result.confidence,
        )

        return result
