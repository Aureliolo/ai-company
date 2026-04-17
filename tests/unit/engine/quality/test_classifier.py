"""Tests for the rule-based step quality classifier."""

import pytest

from synthorg.engine.loop_protocol import TerminationReason, TurnRecord
from synthorg.engine.quality.classifier import RuleBasedStepClassifier
from synthorg.engine.quality.models import StepQuality
from synthorg.engine.stagnation.models import (
    StagnationReason,
    StagnationResult,
    StagnationVerdict,
)
from synthorg.providers.enums import FinishReason


def _turn(
    *,
    number: int = 1,
    finish: FinishReason = FinishReason.STOP,
    tools: tuple[str, ...] = (),
) -> TurnRecord:
    """Helper to build a minimal TurnRecord."""
    return TurnRecord(
        turn_number=number,
        input_tokens=100,
        output_tokens=50,
        cost=0.01,
        tool_calls_made=tools,
        finish_reason=finish,
    )


@pytest.mark.unit
class TestRuleBasedStepClassifier:
    """RuleBasedStepClassifier classification rules."""

    @pytest.fixture
    def classifier(self) -> RuleBasedStepClassifier:
        return RuleBasedStepClassifier()

    async def test_stagnation_terminate_is_incorrect(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        stagnation = StagnationResult(
            verdict=StagnationVerdict.TERMINATE,
            repetition_ratio=0.8,
        )
        signal = await classifier.classify(
            step_index=0,
            turns=(_turn(number=1, tools=("read",)),),
            termination_reason=TerminationReason.STAGNATION,
            stagnation_result=stagnation,
        )
        assert signal.quality == StepQuality.INCORRECT
        assert signal.confidence == 1.0
        assert "stagnation" in signal.reason.lower()

    async def test_stagnation_inject_prompt_not_incorrect(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        """INJECT_PROMPT is not TERMINATE -- step continues."""
        stagnation = StagnationResult(
            verdict=StagnationVerdict.INJECT_PROMPT,
            corrective_message="Try a different approach",
            repetition_ratio=0.6,
        )
        signal = await classifier.classify(
            step_index=0,
            turns=(
                _turn(number=1, tools=("read",)),
                _turn(number=2, tools=("write",)),
            ),
            termination_reason=TerminationReason.COMPLETED,
            stagnation_result=stagnation,
        )
        assert signal.quality == StepQuality.CORRECT

    async def test_error_termination_is_incorrect(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=1,
            turns=(_turn(number=3),),
            termination_reason=TerminationReason.ERROR,
        )
        assert signal.quality == StepQuality.INCORRECT
        assert signal.confidence == 0.7
        assert "ERROR" in signal.reason

    async def test_final_turn_error_finish_is_incorrect(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=0,
            turns=(
                _turn(number=1, finish=FinishReason.STOP),
                _turn(number=2, finish=FinishReason.ERROR),
            ),
            termination_reason=TerminationReason.COMPLETED,
        )
        assert signal.quality == StepQuality.INCORRECT
        assert signal.confidence == 0.7

    async def test_completed_with_tools_is_correct(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=0,
            turns=(
                _turn(number=1, tools=("read",)),
                _turn(number=2, tools=("write",)),
            ),
            termination_reason=TerminationReason.COMPLETED,
        )
        assert signal.quality == StepQuality.CORRECT
        assert signal.confidence == 0.7
        assert "tool calls" in signal.reason.lower()

    async def test_completed_without_tools_is_neutral(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=0,
            turns=(_turn(number=1),),
            termination_reason=TerminationReason.COMPLETED,
        )
        assert signal.quality == StepQuality.NEUTRAL
        assert signal.confidence == 0.5

    async def test_empty_turns_is_neutral(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=0,
            turns=(),
            termination_reason=TerminationReason.COMPLETED,
        )
        assert signal.quality == StepQuality.NEUTRAL
        assert signal.confidence == 0.5
        assert "empty" in signal.reason.lower()

    async def test_max_turns_with_tools_is_neutral(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        """MAX_TURNS termination with tool calls is neutral (not completed)."""
        signal = await classifier.classify(
            step_index=0,
            turns=(
                _turn(number=1, tools=("read",)),
                _turn(number=2, tools=("write",)),
            ),
            termination_reason=TerminationReason.MAX_TURNS,
        )
        assert signal.quality == StepQuality.NEUTRAL

    async def test_budget_exhausted_without_tools_is_neutral(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=0,
            turns=(_turn(number=1),),
            termination_reason=TerminationReason.BUDGET_EXHAUSTED,
        )
        assert signal.quality == StepQuality.NEUTRAL

    async def test_step_index_preserved(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=4,
            turns=(_turn(number=10, tools=("read",)),),
            termination_reason=TerminationReason.COMPLETED,
        )
        assert signal.step_index == 4

    async def test_turn_range_computed(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=0,
            turns=(
                _turn(number=5),
                _turn(number=6),
                _turn(number=7),
            ),
            termination_reason=TerminationReason.COMPLETED,
        )
        assert signal.turn_range == (5, 7)

    async def test_empty_turns_turn_range_defaults(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        signal = await classifier.classify(
            step_index=0,
            turns=(),
            termination_reason=TerminationReason.COMPLETED,
        )
        assert signal.turn_range == (1, 1)

    async def test_stagnation_takes_priority_over_error(
        self, classifier: RuleBasedStepClassifier
    ) -> None:
        """Stagnation (definitive) should take priority over error termination."""
        stagnation = StagnationResult(
            verdict=StagnationVerdict.TERMINATE,
            reason=StagnationReason.TOOL_REPETITION,
            repetition_ratio=0.9,
        )
        signal = await classifier.classify(
            step_index=0,
            turns=(_turn(number=1, finish=FinishReason.ERROR),),
            termination_reason=TerminationReason.ERROR,
            stagnation_result=stagnation,
        )
        assert signal.quality == StepQuality.INCORRECT
        assert signal.confidence == 1.0  # Definitive, not 0.7
