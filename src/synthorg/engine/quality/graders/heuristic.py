"""Heuristic rubric grader -- rule-based, deterministic."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.engine.quality.verification import (
    VerificationResult,
    VerificationRubric,
    VerificationVerdict,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.quality.verification import AtomicProbe
    from synthorg.engine.workflow.handoff import HandoffArtifact

_PASS_THRESHOLD = 0.5


class HeuristicRubricGrader:
    """Rule-based grader for testing and deterministic fallback.

    Grades binary probes by checking whether the probe text
    appears (case-insensitive) in the payload values.  Scores
    each rubric criterion at a fixed 0.8 for PASS, 0.3 for FAIL.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "heuristic"

    async def grade(
        self,
        *,
        artifact: HandoffArtifact,
        rubric: VerificationRubric,
        probes: tuple[AtomicProbe, ...],
        generator_agent_id: NotBlankStr,
        evaluator_agent_id: NotBlankStr,
    ) -> VerificationResult:
        """Grade via simple heuristic matching."""
        payload_text = " ".join(str(v) for v in artifact.payload.values()).lower()

        probe_pass_count = sum(
            1 for p in probes if p.source_criterion.lower() in payload_text
        )
        probe_ratio = probe_pass_count / len(probes) if probes else 1.0

        per_criterion_grades: dict[str, float] = {}
        for criterion in rubric.criteria:
            per_criterion_grades[criterion.name] = (
                0.8 if probe_ratio >= _PASS_THRESHOLD else 0.3
            )

        confidence = min(0.9, probe_ratio + 0.1)

        min_conf = rubric.min_confidence
        if confidence < min_conf:
            verdict = VerificationVerdict.REFER
        elif probe_ratio >= _PASS_THRESHOLD:
            verdict = VerificationVerdict.PASS
        else:
            verdict = VerificationVerdict.FAIL

        return VerificationResult(
            verdict=verdict,
            confidence=confidence,
            per_criterion_grades=per_criterion_grades,
            findings=(f"Heuristic: {probe_pass_count}/{len(probes)} probes matched",),
            evaluator_agent_id=evaluator_agent_id,
            generator_agent_id=generator_agent_id,
            rubric_name=rubric.name,
            timestamp=datetime.now(UTC),
        )
