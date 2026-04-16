"""Tests for the LLM-based criteria decomposer."""

from typing import Any

import pytest

from synthorg.core.task import AcceptanceCriterion
from synthorg.engine.quality.decomposers.llm import (
    LLMCriteriaDecomposer,
    LLMDecompositionError,
)
from synthorg.providers.enums import FinishReason
from synthorg.providers.models import CompletionResponse, TokenUsage
from tests.unit.engine.quality.conftest import (
    ScriptedProvider,
    build_tool_call_response,
)


def _build_response(tool_arguments: dict[str, Any]) -> CompletionResponse:
    return build_tool_call_response(
        "emit_atomic_probes",
        tool_arguments,
        call_id="call-decompose-001",
    )


@pytest.mark.unit
class TestLLMCriteriaDecomposerConstructor:
    def test_invalid_max_probes_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_probes_per_criterion"):
            LLMCriteriaDecomposer(
                provider=ScriptedProvider(),
                model_id="test-medium-001",
                max_probes_per_criterion=0,
            )

    def test_name_is_llm(self) -> None:
        decomposer = LLMCriteriaDecomposer(
            provider=ScriptedProvider(),
            model_id="test-medium-001",
        )
        assert decomposer.name == "llm"


@pytest.mark.unit
class TestLLMCriteriaDecomposerBehavior:
    async def test_empty_criteria_returns_empty(self) -> None:
        provider = ScriptedProvider()
        decomposer = LLMCriteriaDecomposer(
            provider=provider,
            model_id="test-medium-001",
        )
        probes = await decomposer.decompose(
            (),
            task_id="task-001",
            agent_id="agent-001",
        )
        assert probes == ()
        assert provider.complete_calls == []

    async def test_happy_path_materializes_probes(self) -> None:
        criteria = (
            AcceptanceCriterion(description="API responds in <200ms"),
            AcceptanceCriterion(description="API returns JSON body"),
        )
        response = _build_response(
            {
                "probes": [
                    {
                        "source_criterion_index": 0,
                        "probe_text": "Does p50 latency stay under 200ms?",
                    },
                    {
                        "source_criterion_index": 1,
                        "probe_text": "Is the Content-Type application/json?",
                    },
                    {
                        "source_criterion_index": 1,
                        "probe_text": "Does the body parse as valid JSON?",
                    },
                ]
            }
        )
        decomposer = LLMCriteriaDecomposer(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        probes = await decomposer.decompose(
            criteria,
            task_id="task-001",
            agent_id="agent-001",
        )
        assert len(probes) == 3
        assert [p.source_criterion for p in probes] == [
            "API responds in <200ms",
            "API returns JSON body",
            "API returns JSON body",
        ]
        assert all(p.id.startswith("task-001-probe-") for p in probes)
        assert probes[0].id != probes[1].id  # Deterministic unique IDs

    async def test_missing_tool_call_raises(self) -> None:
        response = CompletionResponse(
            content="sorry, I can't do that",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(input_tokens=10, output_tokens=10, cost_usd=0.0),
            model="test-medium-001",
        )
        decomposer = LLMCriteriaDecomposer(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        with pytest.raises(LLMDecompositionError, match="emit_atomic_probes"):
            await decomposer.decompose(
                (AcceptanceCriterion(description="foo"),),
                task_id="task-001",
                agent_id="agent-001",
            )

    async def test_non_list_probes_raises(self) -> None:
        response = _build_response({"probes": "not a list"})
        decomposer = LLMCriteriaDecomposer(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        with pytest.raises(LLMDecompositionError, match="probes"):
            await decomposer.decompose(
                (AcceptanceCriterion(description="foo"),),
                task_id="task-001",
                agent_id="agent-001",
            )

    async def test_per_criterion_cap_enforced(self) -> None:
        criteria = (AcceptanceCriterion(description="only criterion"),)
        response = _build_response(
            {
                "probes": [
                    {
                        "source_criterion_index": 0,
                        "probe_text": f"probe {i}",
                    }
                    for i in range(10)
                ]
            }
        )
        decomposer = LLMCriteriaDecomposer(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
            max_probes_per_criterion=3,
        )
        probes = await decomposer.decompose(
            criteria,
            task_id="task-001",
            agent_id="agent-001",
        )
        assert len(probes) == 3

    async def test_invalid_probes_rejected_but_others_kept(self) -> None:
        criteria = (AcceptanceCriterion(description="only criterion"),)
        response = _build_response(
            {
                "probes": [
                    "not a dict",
                    {"source_criterion_index": 99, "probe_text": "bad index"},
                    {"source_criterion_index": 0, "probe_text": "   "},
                    {"source_criterion_index": 0, "probe_text": "valid probe"},
                ]
            }
        )
        decomposer = LLMCriteriaDecomposer(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        probes = await decomposer.decompose(
            criteria,
            task_id="task-001",
            agent_id="agent-001",
        )
        assert len(probes) == 1
        assert probes[0].probe_text == "valid probe"

    async def test_all_probes_invalid_raises(self) -> None:
        criteria = (AcceptanceCriterion(description="only criterion"),)
        response = _build_response(
            {
                "probes": [
                    {"source_criterion_index": 99, "probe_text": "bad index"},
                    {"source_criterion_index": 0, "probe_text": ""},
                ]
            }
        )
        decomposer = LLMCriteriaDecomposer(
            provider=ScriptedProvider(response=response),
            model_id="test-medium-001",
        )
        with pytest.raises(LLMDecompositionError, match="no valid probes"):
            await decomposer.decompose(
                criteria,
                task_id="task-001",
                agent_id="agent-001",
            )

    async def test_prompt_includes_all_criteria(self) -> None:
        criteria = (
            AcceptanceCriterion(description="criterion one"),
            AcceptanceCriterion(description="criterion two"),
        )
        response = _build_response(
            {
                "probes": [
                    {"source_criterion_index": 0, "probe_text": "a?"},
                    {"source_criterion_index": 1, "probe_text": "b?"},
                ]
            }
        )
        provider = ScriptedProvider(response=response)
        decomposer = LLMCriteriaDecomposer(
            provider=provider,
            model_id="test-medium-001",
        )
        await decomposer.decompose(
            criteria,
            task_id="task-001",
            agent_id="agent-001",
        )
        assert len(provider.complete_calls) == 1
        messages, model, tools, config = provider.complete_calls[0]
        assert model == "test-medium-001"
        assert tools is not None
        assert tools[0].name == "emit_atomic_probes"
        assert config is not None
        assert config.temperature == 0.0
        user_content = messages[-1].content or ""
        assert "criterion one" in user_content
        assert "criterion two" in user_content
