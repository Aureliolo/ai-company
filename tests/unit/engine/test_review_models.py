"""Unit tests for review pipeline domain models."""

import pytest
from pydantic import ValidationError

from synthorg.engine.review.models import (
    PipelineResult,
    ReviewStageResult,
    ReviewVerdict,
)

pytestmark = pytest.mark.unit


class TestReviewVerdict:
    """Tests for the ReviewVerdict enum."""

    def test_has_three_members(self) -> None:
        assert len(ReviewVerdict) == 3

    def test_values(self) -> None:
        assert ReviewVerdict.PASS.value == "pass"
        assert ReviewVerdict.FAIL.value == "fail"
        assert ReviewVerdict.SKIP.value == "skip"


class TestReviewStageResult:
    """Tests for the ReviewStageResult model."""

    def test_valid_result(self) -> None:
        result = ReviewStageResult(
            stage_name="internal",
            verdict=ReviewVerdict.PASS,
        )
        assert result.stage_name == "internal"
        assert result.verdict == ReviewVerdict.PASS
        assert result.reason is None
        assert result.duration_ms == 0

    def test_with_reason(self) -> None:
        result = ReviewStageResult(
            stage_name="client",
            verdict=ReviewVerdict.FAIL,
            reason="Missing error handling",
        )
        assert result.reason == "Missing error handling"

    def test_blank_stage_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewStageResult(
                stage_name="   ",
                verdict=ReviewVerdict.PASS,
            )

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewStageResult(
                stage_name="test",
                verdict=ReviewVerdict.PASS,
                duration_ms=-1,
            )

    def test_frozen(self) -> None:
        result = ReviewStageResult(
            stage_name="test",
            verdict=ReviewVerdict.PASS,
        )
        with pytest.raises(ValidationError):
            result.verdict = ReviewVerdict.FAIL  # type: ignore[misc]


class TestPipelineResult:
    """Tests for the PipelineResult model."""

    def test_valid_result(self) -> None:
        result = PipelineResult(
            task_id="task-1",
            final_verdict=ReviewVerdict.PASS,
        )
        assert result.task_id == "task-1"
        assert result.stage_results == ()
        assert result.total_duration_ms == 0

    def test_with_stages(self) -> None:
        stages = (
            ReviewStageResult(
                stage_name="internal",
                verdict=ReviewVerdict.PASS,
                duration_ms=100,
            ),
            ReviewStageResult(
                stage_name="client",
                verdict=ReviewVerdict.PASS,
                duration_ms=200,
            ),
        )
        result = PipelineResult(
            task_id="task-1",
            final_verdict=ReviewVerdict.PASS,
            stage_results=stages,
            total_duration_ms=300,
        )
        assert len(result.stage_results) == 2
        assert result.total_duration_ms == 300

    def test_frozen(self) -> None:
        result = PipelineResult(
            task_id="task-1",
            final_verdict=ReviewVerdict.PASS,
        )
        with pytest.raises(ValidationError):
            result.task_id = "changed"  # type: ignore[misc]
