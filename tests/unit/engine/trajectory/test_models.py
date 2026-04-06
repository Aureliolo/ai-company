"""Tests for trajectory scoring models."""

import pytest
from pydantic import ValidationError

from synthorg.engine.context import AgentContext
from synthorg.engine.loop_protocol import ExecutionResult, TerminationReason
from synthorg.engine.trajectory.models import (
    CandidateResult,
    TrajectoryConfig,
    TrajectoryScore,
)


@pytest.mark.unit
class TestTrajectoryConfig:
    """TrajectoryConfig frozen model validation."""

    def test_defaults(self) -> None:
        config = TrajectoryConfig()
        assert config.enabled is False
        assert config.k_candidates == 2
        assert config.complexity_gate == ("complex", "epic")
        assert config.budget_guard_margin == 0.2

    def test_frozen(self) -> None:
        config = TrajectoryConfig()
        with pytest.raises(ValidationError):
            config.enabled = True  # type: ignore[misc]

    def test_k_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            TrajectoryConfig(k_candidates=1)

    def test_k_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            TrajectoryConfig(k_candidates=6)

    def test_k_valid_range(self) -> None:
        for k in (2, 3, 4, 5):
            config = TrajectoryConfig(k_candidates=k)
            assert config.k_candidates == k

    def test_margin_bounds(self) -> None:
        TrajectoryConfig(budget_guard_margin=0.0)
        TrajectoryConfig(budget_guard_margin=1.0)
        with pytest.raises(ValidationError):
            TrajectoryConfig(budget_guard_margin=-0.1)
        with pytest.raises(ValidationError):
            TrajectoryConfig(budget_guard_margin=1.1)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrajectoryConfig(unknown_field=True)  # type: ignore[call-arg]


@pytest.mark.unit
class TestTrajectoryScore:
    """TrajectoryScore frozen model validation."""

    def test_joint_score_computed(self) -> None:
        score = TrajectoryScore(
            candidate_index=0,
            vc_score=-0.5,
            len_score=-100.0,
            consistent=True,
        )
        assert score.joint_score == pytest.approx(-100.5)

    def test_zero_scores(self) -> None:
        score = TrajectoryScore(
            candidate_index=0,
            vc_score=0.0,
            len_score=0.0,
            consistent=True,
        )
        assert score.joint_score == 0.0

    def test_positive_len_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrajectoryScore(
                candidate_index=0,
                vc_score=0.0,
                len_score=1.0,
                consistent=True,
            )

    def test_frozen(self) -> None:
        score = TrajectoryScore(
            candidate_index=0,
            vc_score=0.0,
            len_score=-10.0,
            consistent=True,
        )
        with pytest.raises(ValidationError):
            score.vc_score = -1.0  # type: ignore[misc]


@pytest.mark.unit
class TestCandidateResult:
    """CandidateResult frozen model validation."""

    def test_valid_candidate(self, minimal_context: AgentContext) -> None:
        exec_result = ExecutionResult(
            context=minimal_context,
            termination_reason=TerminationReason.COMPLETED,
        )
        candidate = CandidateResult(
            candidate_index=0,
            execution_result=exec_result,
            verbalized_confidence=85.0,
            trace_tokens=500,
        )
        assert candidate.candidate_index == 0
        assert candidate.verbalized_confidence == 85.0
        assert candidate.trace_tokens == 500

    def test_vc_none_allowed(self, minimal_context: AgentContext) -> None:
        exec_result = ExecutionResult(
            context=minimal_context,
            termination_reason=TerminationReason.COMPLETED,
        )
        candidate = CandidateResult(
            candidate_index=0,
            execution_result=exec_result,
            trace_tokens=100,
        )
        assert candidate.verbalized_confidence is None

    def test_vc_out_of_range_rejected(self, minimal_context: AgentContext) -> None:
        exec_result = ExecutionResult(
            context=minimal_context,
            termination_reason=TerminationReason.COMPLETED,
        )
        with pytest.raises(ValidationError):
            CandidateResult(
                candidate_index=0,
                execution_result=exec_result,
                verbalized_confidence=101.0,
                trace_tokens=100,
            )

    def test_negative_trace_tokens_rejected(
        self, minimal_context: AgentContext
    ) -> None:
        exec_result = ExecutionResult(
            context=minimal_context,
            termination_reason=TerminationReason.COMPLETED,
        )
        with pytest.raises(ValidationError):
            CandidateResult(
                candidate_index=0,
                execution_result=exec_result,
                trace_tokens=-1,
            )
