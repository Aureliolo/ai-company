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
    @pytest.mark.parametrize(
        ("payload_text", "min_confidence", "probe_text", "expected"),
        [
            (
                "feature complete and done",
                0.7,
                "feature complete",
                VerificationVerdict.PASS,
            ),
            (
                "something unrelated",
                0.0,
                "completely different",
                VerificationVerdict.FAIL,
            ),
            (
                "something unrelated",
                0.95,
                "completely different",
                VerificationVerdict.REFER,
            ),
        ],
    )
    async def test_verdict_routing(
        self,
        payload_text: str,
        min_confidence: float,
        probe_text: str,
        expected: VerificationVerdict,
    ) -> None:
        grader = HeuristicRubricGrader()
        result = await grader.grade(
            artifact=_artifact(payload_text),
            rubric=_rubric(min_confidence=min_confidence),
            probes=(_probe(probe_text),),
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )
        assert result.verdict == expected

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
    async def test_name_property(self) -> None:
        from tests.unit.providers.conftest import FakeProvider

        grader = LLMRubricGrader(
            provider=FakeProvider(),
            model_id="test-medium-001",
        )
        assert grader.name == "llm"
