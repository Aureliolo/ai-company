"""Tests for StagnationReason enum and extended StagnationResult."""

import pytest

from synthorg.engine.stagnation.models import (
    StagnationReason,
    StagnationResult,
    StagnationVerdict,
)


@pytest.mark.unit
class TestStagnationReason:
    """StagnationReason enum values."""

    def test_values(self) -> None:
        assert StagnationReason.TOOL_REPETITION.value == "tool_repetition"
        assert StagnationReason.CYCLE_DETECTION.value == "cycle_detection"
        assert StagnationReason.QUALITY_EROSION.value == "quality_erosion"

    def test_member_count(self) -> None:
        assert len(StagnationReason) == 3


@pytest.mark.unit
class TestStagnationResultWithReason:
    """StagnationResult with reason field."""

    def test_no_stagnation_reason_none(self) -> None:
        result = StagnationResult(
            verdict=StagnationVerdict.NO_STAGNATION,
        )
        assert result.reason is None

    def test_inject_prompt_with_reason(self) -> None:
        result = StagnationResult(
            verdict=StagnationVerdict.INJECT_PROMPT,
            reason=StagnationReason.TOOL_REPETITION,
            corrective_message="try something else",
        )
        assert result.reason == StagnationReason.TOOL_REPETITION

    def test_terminate_with_quality_erosion(self) -> None:
        result = StagnationResult(
            verdict=StagnationVerdict.TERMINATE,
            reason=StagnationReason.QUALITY_EROSION,
        )
        assert result.reason == StagnationReason.QUALITY_EROSION

    def test_reason_default_none(self) -> None:
        result = StagnationResult(
            verdict=StagnationVerdict.NO_STAGNATION,
        )
        assert result.reason is None
