"""Tests for LlmJudgeQualityStrategy."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.performance.llm_judge_quality_strategy import (
    LlmJudgeQualityStrategy,
)
from synthorg.providers.enums import FinishReason
from synthorg.providers.models import CompletionResponse, TokenUsage

from .conftest import make_acceptance_criterion, make_task_metric

NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)


def _make_provider(
    *,
    content: str = '{"score": 7.5, "rationale": "Good quality output"}',
    cost: float = 0.001,
    input_tokens: int = 200,
    output_tokens: int = 50,
) -> AsyncMock:
    """Build a mock CompletionProvider returning the given content."""
    provider = AsyncMock()
    provider.complete.return_value = CompletionResponse(
        content=content,
        tool_calls=(),
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        ),
        model=NotBlankStr("test-small-001"),
    )
    return provider


@pytest.mark.unit
class TestName:
    """Strategy name property."""

    def test_name(self) -> None:
        """Strategy name is 'llm_judge'."""
        strategy = LlmJudgeQualityStrategy(
            provider=_make_provider(),
            model=NotBlankStr("test-small-001"),
        )

        assert strategy.name == "llm_judge"


@pytest.mark.unit
class TestScoring:
    """Successful scoring via LLM judge."""

    async def test_successful_scoring(self) -> None:
        """LLM returns valid JSON and score is used."""
        provider = _make_provider(
            content='{"score": 8.5, "rationale": "All criteria met well"}',
        )
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)
        criteria = (
            make_acceptance_criterion(description="Tests pass", met=True),
            make_acceptance_criterion(description="Code reviewed", met=True),
        )

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=criteria,
        )

        assert result.score == 8.5
        assert result.strategy_name == "llm_judge"
        assert result.confidence == 0.8

    async def test_empty_criteria(self) -> None:
        """Scoring works with no acceptance criteria (lower confidence)."""
        provider = _make_provider(
            content='{"score": 6.0, "rationale": "No criteria to evaluate"}',
        )
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.score == 6.0
        assert result.confidence == 0.5

    async def test_criteria_present_higher_confidence_than_empty(self) -> None:
        """Criteria present -> higher confidence than empty."""
        provider = _make_provider()
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)
        criteria = (make_acceptance_criterion(),)

        with_criteria = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=criteria,
        )
        without_criteria = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert with_criteria.confidence > without_criteria.confidence

    async def test_score_clamped_to_range(self) -> None:
        """LLM score outside [0, 10] is clamped."""
        provider = _make_provider(
            content='{"score": 12.0, "rationale": "Very generous LLM"}',
        )
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.score == 10.0

    async def test_negative_score_clamped(self) -> None:
        """Negative LLM score is clamped to 0."""
        provider = _make_provider(
            content='{"score": -3.0, "rationale": "Very harsh LLM"}',
        )
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.score == 0.0

    async def test_breakdown_contains_llm_score(self) -> None:
        """Breakdown includes the LLM score component."""
        provider = _make_provider(
            content='{"score": 7.0, "rationale": "Solid work overall"}',
        )
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        breakdown_dict = dict(result.breakdown)
        assert "llm_score" in breakdown_dict


@pytest.mark.unit
class TestErrorHandling:
    """Error handling and graceful degradation."""

    async def test_malformed_json(self) -> None:
        """Malformed JSON returns confidence=0.0 fallback."""
        provider = _make_provider(content="not json at all")
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.confidence == 0.0
        assert result.strategy_name == "llm_judge"

    async def test_missing_score_key(self) -> None:
        """JSON without 'score' key returns confidence=0.0 fallback."""
        provider = _make_provider(content='{"rationale": "oops no score"}')
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.confidence == 0.0

    async def test_blank_rationale(self) -> None:
        """Blank rationale returns confidence=0.0 fallback."""
        provider = _make_provider(content='{"score": 7.0, "rationale": ""}')
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.confidence == 0.0

    async def test_provider_exception(self) -> None:
        """Provider exception returns confidence=0.0 fallback."""
        provider = AsyncMock()
        provider.complete.side_effect = RuntimeError("Connection failed")
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.confidence == 0.0

    async def test_empty_content(self) -> None:
        """LLM returning None content returns confidence=0.0 fallback."""
        provider = AsyncMock()
        provider.complete.return_value = CompletionResponse(
            content=None,
            tool_calls=(),
            finish_reason=FinishReason.ERROR,
            usage=TokenUsage(input_tokens=0, output_tokens=0, cost=0.0),
            model=NotBlankStr("test-small-001"),
        )
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.confidence == 0.0


@pytest.mark.unit
class TestCostTracking:
    """Cost recording via CostTracker."""

    async def test_cost_recorded_on_success(self) -> None:
        """Successful scoring records cost via CostTracker."""
        provider = _make_provider(cost=0.002)
        cost_tracker = MagicMock()
        cost_tracker.record = AsyncMock()
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
            cost_tracker=cost_tracker,
        )
        record = make_task_metric(completed_at=NOW)

        await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        cost_tracker.record.assert_awaited_once()
        cost_record = cost_tracker.record.await_args[0][0]
        assert cost_record.cost == 0.002
        assert cost_record.agent_id == "agent-001"
        assert cost_record.task_id == "task-001"
        assert cost_record.model == "test-small-001"

    async def test_no_cost_recorded_on_failure(self) -> None:
        """Failed scoring does not record cost."""
        provider = AsyncMock()
        provider.complete.side_effect = RuntimeError("fail")
        cost_tracker = MagicMock()
        cost_tracker.record = AsyncMock()
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
            cost_tracker=cost_tracker,
        )
        record = make_task_metric(completed_at=NOW)

        await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        cost_tracker.record.assert_not_called()

    async def test_no_cost_tracker_is_fine(self) -> None:
        """Works without a cost tracker (cost tracking optional)."""
        provider = _make_provider()
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
            cost_tracker=None,
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.score == 7.5


@pytest.mark.unit
class TestPromptConstruction:
    """Prompt construction for the LLM."""

    async def test_criteria_included_in_prompt(self) -> None:
        """Acceptance criteria descriptions appear in the LLM prompt."""
        provider = _make_provider()
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)
        criteria = (
            make_acceptance_criterion(description="All tests pass", met=True),
            make_acceptance_criterion(description="No lint errors", met=False),
        )

        await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=criteria,
        )

        # Inspect the prompt sent to the provider.
        call_args = provider.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        prompt_text = messages[0].content
        assert "All tests pass" in prompt_text
        assert "No lint errors" in prompt_text
        assert "[MET]" in prompt_text
        assert "[NOT MET]" in prompt_text

    async def test_delimiters_in_prompt(self) -> None:
        """Prompt uses delimiters for user-controlled text."""
        provider = _make_provider()
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)
        criteria = (make_acceptance_criterion(),)

        await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=criteria,
        )

        call_args = provider.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        prompt_text = messages[0].content
        assert "---BEGIN CRITERIA---" in prompt_text
        assert "---END CRITERIA---" in prompt_text

    async def test_braces_in_criteria_escaped(self) -> None:
        """Curly braces in criteria descriptions are escaped for str.format()."""
        provider = _make_provider()
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
        )
        record = make_task_metric(completed_at=NOW)
        criteria = (
            make_acceptance_criterion(
                description="Output must be {valid JSON}",
                met=True,
            ),
        )

        await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=criteria,
        )

        call_args = provider.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        prompt_text = messages[0].content
        assert "{valid JSON}" in prompt_text


@pytest.mark.unit
class TestCostRecordingResilience:
    """Cost recording failures do not discard valid scores."""

    async def test_cost_failure_does_not_discard_score(self) -> None:
        """If cost recording fails, the LLM score is still returned."""
        provider = _make_provider(
            content='{"score": 8.0, "rationale": "Great work"}',
        )
        cost_tracker = MagicMock()
        cost_tracker.record = AsyncMock(
            side_effect=RuntimeError("DB unavailable"),
        )
        strategy = LlmJudgeQualityStrategy(
            provider=provider,
            model=NotBlankStr("test-small-001"),
            cost_tracker=cost_tracker,
        )
        record = make_task_metric(completed_at=NOW)

        result = await strategy.score(
            agent_id=NotBlankStr("agent-001"),
            task_id=NotBlankStr("task-001"),
            task_result=record,
            acceptance_criteria=(),
        )

        assert result.score == 8.0
        assert result.confidence > 0.0
