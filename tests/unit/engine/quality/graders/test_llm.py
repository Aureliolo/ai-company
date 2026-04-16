"""Tests for the LLM-based rubric grader."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from synthorg.engine.quality.graders.llm import LLMRubricGrader
from synthorg.engine.quality.verification import (
    AtomicProbe,
    GradeType,
    RubricCriterion,
    VerificationRubric,
    VerificationVerdict,
)
from synthorg.engine.workflow.handoff import HandoffArtifact
from synthorg.providers.capabilities import ModelCapabilities
from synthorg.providers.enums import FinishReason, StreamEventType
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
    CompletionResponse,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)

_CAPABILITIES = ModelCapabilities(
    model_id="test-medium-001",
    provider="test-provider",
    max_context_tokens=200_000,
    max_output_tokens=8_192,
    supports_tools=True,
    supports_vision=False,
    supports_streaming=True,
    supports_streaming_tool_calls=True,
    supports_system_messages=True,
    cost_per_1k_input=0.001,
    cost_per_1k_output=0.002,
)


def _rubric(*, min_confidence: float = 0.6) -> VerificationRubric:
    return VerificationRubric(
        name="test-rubric",
        criteria=(
            RubricCriterion(
                name="correctness",
                description="Output is correct",
                weight=0.6,
                grade_type=GradeType.SCORE,
            ),
            RubricCriterion(
                name="completeness",
                description="Output covers all asked outputs",
                weight=0.4,
                grade_type=GradeType.SCORE,
            ),
        ),
        min_confidence=min_confidence,
    )


def _artifact() -> HandoffArtifact:
    return HandoffArtifact(
        created_at=datetime.now(UTC),
        from_agent_id="agent-generator",
        to_agent_id="agent-evaluator",
        from_stage="generator",
        to_stage="evaluator",
        payload={"summary": "Implementation complete"},
        artifact_refs=("artifact-001",),
    )


def _probes() -> tuple[AtomicProbe, ...]:
    return (
        AtomicProbe(
            id="p-0",
            probe_text="Is the output correct?",
            source_criterion="correctness",
        ),
        AtomicProbe(
            id="p-1",
            probe_text="Is every required output present?",
            source_criterion="completeness",
        ),
    )


def _response(tool_arguments: dict[str, Any]) -> CompletionResponse:
    return CompletionResponse(
        tool_calls=(
            ToolCall(
                id="call-grade-001",
                name="emit_rubric_verdict",
                arguments=tool_arguments,
            ),
        ),
        finish_reason=FinishReason.TOOL_USE,
        usage=TokenUsage(input_tokens=200, output_tokens=60, cost_usd=0.0003),
        model="test-medium-001",
    )


class ScriptedProvider:
    """Structural ``CompletionProvider`` returning scripted responses."""

    def __init__(self, *, response: CompletionResponse) -> None:
        self._response = response
        self.complete_calls: list[
            tuple[
                list[ChatMessage],
                str,
                list[ToolDefinition] | None,
                CompletionConfig | None,
            ]
        ] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> CompletionResponse:
        self.complete_calls.append((messages, model, tools, config))
        return self._response

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[ToolDefinition] | None = None,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        async def _empty() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(event_type=StreamEventType.DONE)

        return _empty()

    async def get_model_capabilities(self, model: str) -> ModelCapabilities:
        return _CAPABILITIES


@pytest.mark.unit
class TestLLMRubricGraderConstructor:
    def test_invalid_override_rejected(self) -> None:
        with pytest.raises(ValueError, match="min_confidence_override"):
            LLMRubricGrader(
                provider=ScriptedProvider(
                    response=_response(
                        {
                            "per_criterion_grades": {},
                            "verdict": "pass",
                            "confidence": 1.0,
                            "findings": [],
                        }
                    ),
                ),
                model_id="test-medium-001",
                min_confidence_override=1.5,
            )

    def test_name_is_llm(self) -> None:
        grader = LLMRubricGrader(
            provider=ScriptedProvider(
                response=_response(
                    {
                        "per_criterion_grades": {
                            "correctness": 1.0,
                            "completeness": 1.0,
                        },
                        "verdict": "pass",
                        "confidence": 1.0,
                        "findings": [],
                    }
                ),
            ),
            model_id="test-medium-001",
        )
        assert grader.name == "llm"


@pytest.mark.unit
class TestLLMRubricGraderBehavior:
    async def test_happy_path_pass(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 0.9,
                    "completeness": 0.85,
                },
                "verdict": "pass",
                "confidence": 0.82,
                "findings": ["all criteria satisfied"],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.PASS
        assert result.confidence == pytest.approx(0.82)
        assert result.per_criterion_grades["correctness"] == pytest.approx(0.9)
        assert result.findings == ("all criteria satisfied",)

    async def test_happy_path_fail(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 0.2,
                    "completeness": 0.1,
                },
                "verdict": "fail",
                "confidence": 0.85,
                "findings": ["output incorrect"],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.FAIL

    async def test_low_confidence_downgrades_to_refer(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 0.9,
                    "completeness": 0.9,
                },
                "verdict": "pass",
                "confidence": 0.3,
                "findings": ["uncertain"],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(min_confidence=0.6),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.REFER
        assert any("below minimum" in f for f in result.findings)

    async def test_min_confidence_override_takes_precedence(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 0.9,
                    "completeness": 0.9,
                },
                "verdict": "pass",
                "confidence": 0.7,
                "findings": [],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
            min_confidence_override=0.9,
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(min_confidence=0.5),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.REFER

    async def test_missing_tool_call_returns_refer(self) -> None:
        response = CompletionResponse(
            content="I refuse to grade this",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(input_tokens=10, output_tokens=10, cost_usd=0.0),
            model="test-medium-001",
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.REFER
        assert result.confidence == 0.0
        assert "no emit_rubric_verdict" in result.findings[0]

    async def test_missing_criterion_returns_refer(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {"correctness": 0.9},
                "verdict": "pass",
                "confidence": 0.9,
                "findings": [],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.REFER
        assert "missing grades" in result.findings[0]

    async def test_unknown_criterion_returns_refer(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 0.9,
                    "completeness": 0.9,
                    "extra": 0.5,
                },
                "verdict": "pass",
                "confidence": 0.9,
                "findings": [],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.REFER
        assert "unknown criterion" in result.findings[0]

    async def test_out_of_range_grade_returns_refer(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 1.5,
                    "completeness": 0.5,
                },
                "verdict": "pass",
                "confidence": 0.9,
                "findings": [],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.REFER

    async def test_unknown_verdict_returns_refer(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 0.9,
                    "completeness": 0.9,
                },
                "verdict": "maybe",
                "confidence": 0.9,
                "findings": [],
            }
        )
        grader = LLMRubricGrader(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        result = await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        assert result.verdict == VerificationVerdict.REFER
        assert "unknown verdict" in result.findings[0]

    async def test_prompt_includes_rubric_and_probes(self) -> None:
        response = _response(
            {
                "per_criterion_grades": {
                    "correctness": 0.9,
                    "completeness": 0.9,
                },
                "verdict": "pass",
                "confidence": 0.9,
                "findings": [],
            }
        )
        provider = ScriptedProvider(response=response)
        grader = LLMRubricGrader(
            provider=provider,
            model_id="test-medium-001",
        )
        await grader.grade(
            artifact=_artifact(),
            rubric=_rubric(),
            probes=_probes(),
            generator_agent_id="agent-generator",
            evaluator_agent_id="agent-evaluator",
        )
        messages, _, tools, config = provider.complete_calls[0]
        assert tools is not None
        assert tools[0].name == "emit_rubric_verdict"
        assert config is not None
        assert config.temperature == 0.0
        content = messages[-1].content or ""
        assert "correctness" in content
        assert "completeness" in content
        assert "Is the output correct?" in content
