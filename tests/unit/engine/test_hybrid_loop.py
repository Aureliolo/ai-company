"""Tests for the Hybrid Plan + ReAct execution loop."""

import json
from typing import TYPE_CHECKING, Any

import pytest

from synthorg.budget.call_category import LLMCallCategory
from synthorg.core.enums import ToolCategory
from synthorg.engine.context import AgentContext
from synthorg.engine.hybrid_loop import HybridLoop
from synthorg.engine.hybrid_models import HybridLoopConfig
from synthorg.engine.loop_protocol import TerminationReason, TurnRecord
from synthorg.engine.stagnation.models import (
    StagnationResult,
    StagnationVerdict,
)
from synthorg.providers.enums import FinishReason, MessageRole
from synthorg.providers.models import (
    ChatMessage,
    CompletionResponse,
    TokenUsage,
    ToolCall,
)
from synthorg.tools.base import BaseTool, ToolExecutionResult
from synthorg.tools.invoker import ToolInvoker
from synthorg.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from .conftest import MockCompletionProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _usage(
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> TokenUsage:
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=0.001,
    )


def _plan_response(steps: list[dict[str, Any]]) -> CompletionResponse:
    """Build a plan response with JSON-formatted steps."""
    plan = {"steps": steps}
    return CompletionResponse(
        content=json.dumps(plan),
        finish_reason=FinishReason.STOP,
        usage=_usage(),
        model="test-model-001",
    )


def _single_step_plan() -> CompletionResponse:
    return _plan_response(
        [
            {
                "step_number": 1,
                "description": "Analyze and solve the problem",
                "expected_outcome": "Problem solved",
            },
        ]
    )


def _multi_step_plan() -> CompletionResponse:
    return _plan_response(
        [
            {
                "step_number": 1,
                "description": "Research the topic",
                "expected_outcome": "Understanding gained",
            },
            {
                "step_number": 2,
                "description": "Implement solution",
                "expected_outcome": "Code written",
            },
            {
                "step_number": 3,
                "description": "Verify results",
                "expected_outcome": "Tests pass",
            },
        ]
    )


def _stop_response(content: str = "Done.") -> CompletionResponse:
    return CompletionResponse(
        content=content,
        finish_reason=FinishReason.STOP,
        usage=_usage(),
        model="test-model-001",
    )


def _summary_response(
    *,
    replan: bool = False,
    summary: str = "Step completed successfully.",
) -> CompletionResponse:
    """Build a progress-summary response."""
    return CompletionResponse(
        content=json.dumps({"summary": summary, "replan": replan}),
        finish_reason=FinishReason.STOP,
        usage=_usage(),
        model="test-model-001",
    )


def _tool_use_response(
    tool_name: str = "echo",
    tool_call_id: str = "tc-1",
) -> CompletionResponse:
    return CompletionResponse(
        content=None,
        tool_calls=(ToolCall(id=tool_call_id, name=tool_name, arguments={}),),
        finish_reason=FinishReason.TOOL_USE,
        usage=_usage(),
        model="test-model-001",
    )


def _content_filter_response() -> CompletionResponse:
    return CompletionResponse(
        content=None,
        finish_reason=FinishReason.CONTENT_FILTER,
        usage=_usage(),
        model="test-model-001",
    )


def _step_fail_response() -> CompletionResponse:
    """Response causing step failure (TOOL_USE with no tool calls)."""
    return CompletionResponse(
        content="I could not complete this step.",
        finish_reason=FinishReason.TOOL_USE,
        usage=_usage(),
        model="test-model-001",
    )


class _StubTool(BaseTool):
    def __init__(self, name: str = "echo") -> None:
        super().__init__(
            name=name,
            description="Test tool",
            category=ToolCategory.CODE_EXECUTION,
        )

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            content=f"echoed: {arguments}",
            is_error=False,
        )


def _make_invoker(*tool_names: str) -> ToolInvoker:
    tools = [_StubTool(name=n) for n in tool_names]
    return ToolInvoker(ToolRegistry(tools))


def _ctx_with_user_msg(ctx: AgentContext) -> AgentContext:
    msg = ChatMessage(role=MessageRole.USER, content="Do something")
    return ctx.with_message(msg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHybridLoopProtocol:
    """Protocol compliance and basic properties."""

    def test_loop_type(self) -> None:
        loop = HybridLoop()
        assert loop.get_loop_type() == "hybrid"

    def test_is_execution_loop(self) -> None:
        from synthorg.engine.loop_protocol import ExecutionLoop

        loop = HybridLoop()
        assert isinstance(loop, ExecutionLoop)

    def test_default_config(self) -> None:
        loop = HybridLoop()
        assert loop.config.max_plan_steps == 7
        assert loop.config.max_turns_per_step == 5

    def test_custom_config(self) -> None:
        cfg = HybridLoopConfig(max_plan_steps=3, max_turns_per_step=10)
        loop = HybridLoop(config=cfg)
        assert loop.config.max_plan_steps == 3
        assert loop.config.max_turns_per_step == 10


@pytest.mark.unit
class TestHybridLoopBasic:
    """Single-step and multi-step plan -> execute -> complete."""

    async def test_single_step_completion(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # planning
                _stop_response("Done."),  # step 1 execution
                _summary_response(),  # progress summary
            ]
        )
        loop = HybridLoop()

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        # 3 turns: plan + step execution + summary
        assert len(result.turns) == 3
        assert result.metadata["loop_type"] == "hybrid"
        assert result.metadata["replans_used"] == 0
        # Planning = SYSTEM, execution = PRODUCTIVE, summary = SYSTEM
        assert result.turns[0].call_category == LLMCallCategory.SYSTEM
        assert result.turns[1].call_category == LLMCallCategory.PRODUCTIVE
        assert result.turns[2].call_category == LLMCallCategory.SYSTEM

    async def test_multi_step_completion(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _multi_step_plan(),  # planning
                _stop_response("Research done."),  # step 1
                _summary_response(),  # summary 1
                _stop_response("Implementation done."),  # step 2
                _summary_response(),  # summary 2
                _stop_response("Verification done."),  # step 3
                _summary_response(),  # summary 3
            ]
        )
        loop = HybridLoop()

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        # 7 turns: plan + 3*(step + summary)
        assert len(result.turns) == 7

    async def test_no_summary_when_disabled(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """When checkpoint_after_each_step=False, skip progress summary."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # planning
                _stop_response("Done."),  # step 1 execution
            ]
        )
        cfg = HybridLoopConfig(checkpoint_after_each_step=False)
        loop = HybridLoop(config=cfg)

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        # 2 turns: plan + step execution (no summary)
        assert len(result.turns) == 2


@pytest.mark.unit
class TestHybridLoopWithTools:
    """Steps that invoke tools."""

    async def test_tool_calls_per_step(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # planning
                _tool_use_response("echo", "tc-1"),  # step 1 turn 1
                _stop_response("Tool used and done."),  # step 1 turn 2
                _summary_response(),  # summary
            ]
        )
        invoker = _make_invoker("echo")
        loop = HybridLoop()

        result = await loop.execute(
            context=ctx,
            provider=provider,
            tool_invoker=invoker,
        )

        assert result.termination_reason == TerminationReason.COMPLETED
        assert result.total_tool_calls == 1
        # 4 turns: plan + tool_use + stop + summary
        assert len(result.turns) == 4


@pytest.mark.unit
class TestHybridLoopPerStepTurnLimit:
    """Per-step turn limiting (unique to hybrid)."""

    async def test_step_fails_on_turn_limit(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Step uses all max_turns_per_step without completing -> FAILED."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(
            max_turns_per_step=2,
            max_replans=0,
        )
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # planning
                _tool_use_response("echo", "tc-1"),  # step turn 1
                _tool_use_response("echo", "tc-2"),  # step turn 2 (limit!)
                # step fails, replans exhausted -> ERROR
            ]
        )
        invoker = _make_invoker("echo")
        loop = HybridLoop(config=cfg)

        result = await loop.execute(
            context=ctx,
            provider=provider,
            tool_invoker=invoker,
        )

        assert result.termination_reason == TerminationReason.ERROR
        assert "Max replans" in (result.error_message or "")

    async def test_step_succeeds_within_limit(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Step completes before per-step limit."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(max_turns_per_step=3)
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # planning
                _tool_use_response("echo", "tc-1"),  # step turn 1
                _stop_response("Done after tool use."),  # step turn 2
                _summary_response(),  # summary
            ]
        )
        invoker = _make_invoker("echo")
        loop = HybridLoop(config=cfg)

        result = await loop.execute(
            context=ctx,
            provider=provider,
            tool_invoker=invoker,
        )

        assert result.termination_reason == TerminationReason.COMPLETED


@pytest.mark.unit
class TestHybridLoopProgressSummary:
    """Progress summary and LLM-decided replanning."""

    async def test_summary_triggers_replan(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """LLM says replan=true after step 1 -> creates a new plan."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(allow_replan_on_completion=True)
        provider = mock_provider_factory(
            [
                _multi_step_plan(),  # initial plan (3 steps)
                _stop_response("Research done."),  # step 1 execution
                _summary_response(replan=True),  # summary -> replan!
                _single_step_plan(),  # new plan (1 step)
                _stop_response("All done."),  # new step 1
                _summary_response(replan=False),  # summary -> no replan
            ]
        )
        loop = HybridLoop(config=cfg)

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        assert result.metadata["replans_used"] == 1
        plans = result.metadata["plans"]
        assert isinstance(plans, list)
        assert len(plans) == 2  # original + replanned

    async def test_no_replan_when_disabled(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """allow_replan_on_completion=False ignores replan signal."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(allow_replan_on_completion=False)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
                _stop_response("Done."),
                # Summary says replan, but config says no
                _summary_response(replan=True),
            ]
        )
        loop = HybridLoop(config=cfg)

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        assert result.metadata["replans_used"] == 0


@pytest.mark.unit
class TestHybridLoopReplanning:
    """Re-planning on step failure."""

    async def test_max_replans_exhausted(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Step fails, max_replans=0 -> ERROR."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(max_replans=0)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
                _step_fail_response(),
            ]
        )
        loop = HybridLoop(config=cfg)

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.ERROR
        assert "Max replans" in (result.error_message or "")

    async def test_successful_replan_on_failure(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Step fails, replan succeeds, new plan completes."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(max_replans=1)
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # original plan
                _step_fail_response(),  # step fails
                _single_step_plan(),  # replan
                _stop_response("Done now."),  # new step succeeds
                _summary_response(),  # summary
            ]
        )
        loop = HybridLoop(config=cfg)

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        assert result.metadata["replans_used"] == 1

    async def test_content_filter_during_step_returns_error(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
                _content_filter_response(),
            ]
        )
        loop = HybridLoop()

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.ERROR


@pytest.mark.unit
class TestHybridLoopBudget:
    """Budget exhaustion handling."""

    async def test_budget_exhausted_before_planning(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory([])
        loop = HybridLoop()

        result = await loop.execute(
            context=ctx,
            provider=provider,
            budget_checker=lambda _ctx: True,
        )

        assert result.termination_reason == TerminationReason.BUDGET_EXHAUSTED

    async def test_budget_exhausted_during_step(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        call_count = 0

        def budget_check(_ctx: AgentContext) -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 1  # allow planning, block step

        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
            ]
        )
        loop = HybridLoop()

        result = await loop.execute(
            context=ctx,
            provider=provider,
            budget_checker=budget_check,
        )

        assert result.termination_reason == TerminationReason.BUDGET_EXHAUSTED


@pytest.mark.unit
class TestHybridLoopShutdown:
    """Shutdown handling."""

    async def test_shutdown_before_planning(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory([])
        loop = HybridLoop()

        result = await loop.execute(
            context=ctx,
            provider=provider,
            shutdown_checker=lambda: True,
        )

        assert result.termination_reason == TerminationReason.SHUTDOWN

    async def test_shutdown_during_step(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        call_count = 0

        def shutdown_check() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 1

        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
            ]
        )
        loop = HybridLoop()

        result = await loop.execute(
            context=ctx,
            provider=provider,
            shutdown_checker=shutdown_check,
        )

        assert result.termination_reason == TerminationReason.SHUTDOWN


@pytest.mark.unit
class TestHybridLoopMaxTurns:
    """Global turn budget exhaustion."""

    async def test_max_turns_during_step(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Run out of global turns mid-step -> MAX_TURNS."""
        # Create context with very low max_turns
        ctx = _ctx_with_user_msg(sample_agent_context)
        ctx = ctx.model_copy(update={"max_turns": 2})
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # turn 1
                _tool_use_response("echo", "tc-1"),  # turn 2 (max!)
            ]
        )
        invoker = _make_invoker("echo")
        loop = HybridLoop()

        result = await loop.execute(
            context=ctx,
            provider=provider,
            tool_invoker=invoker,
        )

        assert result.termination_reason == TerminationReason.MAX_TURNS


@pytest.mark.unit
class TestHybridLoopModelTiering:
    """Different models for planning vs execution."""

    async def test_different_models_for_phases(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(
            planner_model="test-large-001",
            executor_model="test-small-001",
        )
        provider = mock_provider_factory(
            [
                _single_step_plan(),  # planning (large model)
                _stop_response("Done."),  # step (small model)
                _summary_response(),  # summary (large model)
            ]
        )
        loop = HybridLoop(config=cfg)

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        # Verify model usage
        assert provider.recorded_models[0] == "test-large-001"  # plan
        assert provider.recorded_models[1] == "test-small-001"  # step
        assert provider.recorded_models[2] == "test-large-001"  # summary


@pytest.mark.unit
class TestHybridLoopMetadata:
    """Verify metadata structure."""

    async def test_metadata_structure(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
                _stop_response("Done."),
                _summary_response(),
            ]
        )
        loop = HybridLoop()

        result = await loop.execute(context=ctx, provider=provider)

        assert result.metadata["loop_type"] == "hybrid"
        assert result.metadata["replans_used"] == 0
        assert result.metadata["final_plan"] is not None
        plans = result.metadata["plans"]
        assert isinstance(plans, list)
        assert len(plans) == 1


@pytest.mark.unit
class TestHybridLoopContextImmutability:
    """Original context must not be mutated."""

    async def test_original_context_unchanged(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        original_turn_count = ctx.turn_count
        original_conversation_len = len(ctx.conversation)

        provider = mock_provider_factory(
            [
                _single_step_plan(),
                _stop_response("Done."),
                _summary_response(),
            ]
        )
        loop = HybridLoop()

        await loop.execute(context=ctx, provider=provider)

        assert ctx.turn_count == original_turn_count
        assert len(ctx.conversation) == original_conversation_len


@pytest.mark.unit
class TestHybridLoopStagnation:
    """Stagnation detection integration."""

    async def test_stagnation_within_step_triggers_terminate(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        class TerminateDetector:
            async def check(
                self,
                turns: tuple[TurnRecord, ...],
                *,
                corrections_injected: int = 0,
            ) -> StagnationResult:
                if len(turns) >= 2:
                    return StagnationResult(
                        verdict=StagnationVerdict.TERMINATE,
                        repetition_ratio=1.0,
                    )
                return StagnationResult(
                    verdict=StagnationVerdict.NO_STAGNATION,
                    repetition_ratio=0.0,
                )

            def get_detector_type(self) -> str:
                return "test_terminate"

        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
                _tool_use_response("echo", "tc-1"),  # turn 1
                _tool_use_response("echo", "tc-2"),  # turn 2 -> stagnation
            ]
        )
        invoker = _make_invoker("echo")
        loop = HybridLoop(stagnation_detector=TerminateDetector())

        result = await loop.execute(
            context=ctx,
            provider=provider,
            tool_invoker=invoker,
        )

        assert result.termination_reason == TerminationReason.STAGNATION

    async def test_stagnation_correction_in_step(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        class CorrectDetector:
            def __init__(self) -> None:
                self._fired = False

            async def check(
                self,
                turns: tuple[TurnRecord, ...],
                *,
                corrections_injected: int = 0,
            ) -> StagnationResult:
                if len(turns) >= 1 and not self._fired:
                    self._fired = True
                    return StagnationResult(
                        verdict=StagnationVerdict.INJECT_PROMPT,
                        corrective_message="Try a different approach.",
                        repetition_ratio=0.6,
                    )
                return StagnationResult(
                    verdict=StagnationVerdict.NO_STAGNATION,
                    repetition_ratio=0.0,
                )

            def get_detector_type(self) -> str:
                return "test_correct"

        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                _single_step_plan(),
                _tool_use_response("echo", "tc-1"),  # triggers correction
                _stop_response("Done differently."),  # completes after fix
                _summary_response(),
            ]
        )
        invoker = _make_invoker("echo")
        loop = HybridLoop(stagnation_detector=CorrectDetector())

        result = await loop.execute(
            context=ctx,
            provider=provider,
            tool_invoker=invoker,
        )

        assert result.termination_reason == TerminationReason.COMPLETED


@pytest.mark.unit
class TestHybridLoopPlanParsing:
    """Plan parsing edge cases."""

    async def test_unparseable_plan_returns_error(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        ctx = _ctx_with_user_msg(sample_agent_context)
        provider = mock_provider_factory(
            [
                CompletionResponse(
                    content="This is not a plan.",
                    finish_reason=FinishReason.STOP,
                    usage=_usage(),
                    model="test-model-001",
                ),
            ]
        )
        loop = HybridLoop()

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.ERROR
        assert "parse" in (result.error_message or "").lower()

    async def test_plan_truncated_to_max_steps(
        self,
        sample_agent_context: AgentContext,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Plan with more steps than max_plan_steps gets truncated."""
        ctx = _ctx_with_user_msg(sample_agent_context)
        cfg = HybridLoopConfig(max_plan_steps=2)
        # LLM returns a 3-step plan, but config says max 2
        provider = mock_provider_factory(
            [
                _multi_step_plan(),  # 3 steps, truncated to 2
                _stop_response("Step 1 done."),  # step 1
                _summary_response(),  # summary 1
                _stop_response("Step 2 done."),  # step 2
                _summary_response(),  # summary 2
            ]
        )
        loop = HybridLoop(config=cfg)

        result = await loop.execute(context=ctx, provider=provider)

        assert result.termination_reason == TerminationReason.COMPLETED
        # Only 2 steps executed (not 3)
        final_plan = result.metadata["final_plan"]
        assert isinstance(final_plan, dict)
        assert len(final_plan["steps"]) == 2
