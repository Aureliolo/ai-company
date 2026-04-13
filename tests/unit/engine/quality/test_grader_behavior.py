"""Behavioral tests for rubric grader implementations."""

from datetime import UTC, datetime

import pytest

from synthorg.engine.quality.graders.heuristic import HeuristicRubricGrader
from synthorg.engine.quality.graders.llm import LLMRubricGrader
from synthorg.engine.quality.verification import (
    AtomicProbe,
    GradeType,
    RubricCriterion,
    VerificationRubric,
    VerificationVerdict,
)
from synthorg.engine.workflow.handoff import HandoffArtifact


def _rubric(
    min_confidence: float = 0.7,
) -> VerificationRubric:
    return VerificationRubric(
        name="test-rubric",
        criteria=(
            RubricCriterion(
                name="quality",
                description="Quality",
                weight=1.0,
                grade_type=GradeType.SCORE,
            ),
        ),
        min_confidence=min_confidence,
    )


def _artifact(payload_text: str = "feature complete") -> HandoffArtifact:
    return HandoffArtifact(
        from_agent_id="gen-agent",
        to_agent_id="eval-agent",
        from_stage="generator",
        to_stage="evaluator",
        payload={"output": payload_text},
        created_at=datetime.now(UTC),
    )


def _probe(text: str = "Feature complete") -> AtomicProbe:
    return AtomicProbe(
        id="probe-1",
        probe_text=f"Is it done: {text}",
        source_criterion=text,
    )


@pytest.mark.unit
class TestHeuristicGraderBehavior:
    async def test_pass_when_probes_match(self) -> None:
        grader = HeuristicRubricGrader()
        result = await grader.grade(
            artifact=_artifact("feature complete and done"),
            rubric=_rubric(),
            probes=(_probe("feature complete"),),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert result.verdict == VerificationVerdict.PASS

    async def test_fail_when_no_probes_match(self) -> None:
        grader = HeuristicRubricGrader()
        result = await grader.grade(
            artifact=_artifact("something unrelated"),
            rubric=_rubric(min_confidence=0.0),
            probes=(_probe("completely different"),),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert result.verdict == VerificationVerdict.FAIL

    async def test_refer_when_confidence_below_threshold(self) -> None:
        grader = HeuristicRubricGrader()
        result = await grader.grade(
            artifact=_artifact("something unrelated"),
            rubric=_rubric(min_confidence=0.95),
            probes=(_probe("completely different"),),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert result.verdict == VerificationVerdict.REFER

    async def test_empty_probes_refer(self) -> None:
        grader = HeuristicRubricGrader()
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=(),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert result.verdict == VerificationVerdict.REFER

    async def test_per_criterion_grades_populated(self) -> None:
        grader = HeuristicRubricGrader()
        result = await grader.grade(
            artifact=_artifact("feature complete"),
            rubric=_rubric(),
            probes=(_probe("feature complete"),),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert "quality" in result.per_criterion_grades
        assert 0.0 <= result.per_criterion_grades["quality"] <= 1.0

    async def test_rubric_name_in_result(self) -> None:
        grader = HeuristicRubricGrader()
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=(),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert result.rubric_name == "test-rubric"


@pytest.mark.unit
class TestLLMGraderBehavior:
    async def test_produces_result(self) -> None:
        grader = LLMRubricGrader()
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=(_probe(),),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert result.verdict in VerificationVerdict
        assert 0.0 <= result.confidence <= 1.0

    async def test_name_property(self) -> None:
        assert LLMRubricGrader().name == "llm"
