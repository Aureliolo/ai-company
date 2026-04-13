"""Integration test: decomposer -> grader verification pipeline."""

from datetime import UTC, datetime

import pytest

from synthorg.core.task import AcceptanceCriterion
from synthorg.engine.quality.decomposers.identity import (
    IdentityCriteriaDecomposer,
)
from synthorg.engine.quality.graders.heuristic import HeuristicRubricGrader
from synthorg.engine.quality.rubric_catalog import get_rubric
from synthorg.engine.quality.verification import VerificationVerdict
from synthorg.engine.workflow.handoff import HandoffArtifact


@pytest.mark.integration
class TestVerificationPipelineIntegration:
    async def test_pass_flow_with_matching_criteria(self) -> None:
        decomposer = IdentityCriteriaDecomposer()
        grader = HeuristicRubricGrader()
        rubric = get_rubric("default-task")

        criteria = (
            AcceptanceCriterion(description="correctness verified"),
            AcceptanceCriterion(description="completeness checked"),
        )

        probes = await decomposer.decompose(
            criteria, task_id="task-int-1", agent_id="gen-agent"
        )
        assert len(probes) == 2

        artifact = HandoffArtifact(
            from_agent_id="gen-agent",
            to_agent_id="eval-agent",
            from_stage="generator",
            to_stage="evaluator",
            payload={
                "output": "correctness verified and completeness checked",
            },
            acceptance_probes=probes,
            rubric=rubric,
            created_at=datetime.now(UTC),
        )

        result = await grader.grade(
            artifact=artifact,
            rubric=rubric,
            probes=probes,
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )

        assert result.verdict == VerificationVerdict.PASS
        assert 0.0 < result.confidence <= 1.0
        assert len(result.per_criterion_grades) == len(rubric.criteria)
        assert result.evaluator_agent_id != result.generator_agent_id

    async def test_fail_flow_with_non_matching_criteria(self) -> None:
        decomposer = IdentityCriteriaDecomposer()
        grader = HeuristicRubricGrader()
        rubric = get_rubric("default-task")

        criteria = (AcceptanceCriterion(description="specific requirement xyz"),)

        probes = await decomposer.decompose(
            criteria, task_id="task-int-2", agent_id="gen-agent"
        )

        artifact = HandoffArtifact(
            from_agent_id="gen-agent",
            to_agent_id="eval-agent",
            from_stage="generator",
            to_stage="evaluator",
            payload={"output": "completely unrelated content"},
            acceptance_probes=probes,
            rubric=rubric,
            created_at=datetime.now(UTC),
        )

        result = await grader.grade(
            artifact=artifact,
            rubric=rubric,
            probes=probes,
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )

        assert result.verdict == VerificationVerdict.REFER

    async def test_refer_flow_with_high_confidence_threshold(self) -> None:
        decomposer = IdentityCriteriaDecomposer()
        grader = HeuristicRubricGrader()
        rubric = get_rubric("default-task").model_copy(
            update={"min_confidence": 0.99},
        )

        criteria = (AcceptanceCriterion(description="partial match"),)

        probes = await decomposer.decompose(
            criteria, task_id="task-int-3", agent_id="gen-agent"
        )

        artifact = HandoffArtifact(
            from_agent_id="gen-agent",
            to_agent_id="eval-agent",
            from_stage="generator",
            to_stage="evaluator",
            payload={"output": "partial match content"},
            acceptance_probes=probes,
            rubric=rubric,
            created_at=datetime.now(UTC),
        )

        result = await grader.grade(
            artifact=artifact,
            rubric=rubric,
            probes=probes,
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )

        assert result.verdict == VerificationVerdict.REFER

    async def test_frontend_design_rubric_pipeline(self) -> None:
        decomposer = IdentityCriteriaDecomposer()
        grader = HeuristicRubricGrader()
        rubric = get_rubric("frontend-design")

        criteria = (
            AcceptanceCriterion(description="design quality"),
            AcceptanceCriterion(description="originality"),
        )

        probes = await decomposer.decompose(
            criteria, task_id="task-int-4", agent_id="gen-agent"
        )

        artifact = HandoffArtifact(
            from_agent_id="gen-agent",
            to_agent_id="eval-agent",
            from_stage="generator",
            to_stage="evaluator",
            payload={
                "output": "design quality and originality achieved",
            },
            acceptance_probes=probes,
            rubric=rubric,
            created_at=datetime.now(UTC),
        )

        result = await grader.grade(
            artifact=artifact,
            rubric=rubric,
            probes=probes,
            generator_agent_id="gen-agent",
            evaluator_agent_id="eval-agent",
        )

        assert result.verdict == VerificationVerdict.PASS
        assert len(result.per_criterion_grades) == 4
        assert result.rubric_name == "frontend-design"
