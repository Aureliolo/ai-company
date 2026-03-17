"""Tests for context budget indicators and fill estimation."""

import pytest
from pydantic import ValidationError

from synthorg.engine.context import AgentContext
from synthorg.engine.context_budget import (
    ContextBudgetIndicator,
    estimate_context_fill,
    make_context_indicator,
    update_context_fill,
)
from synthorg.engine.prompt import DefaultTokenEstimator
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage

# ── ContextBudgetIndicator ────────────────────────────────────────


@pytest.mark.unit
class TestContextBudgetIndicator:
    """ContextBudgetIndicator model and formatting."""

    def test_format_known_capacity(self) -> None:
        ind = ContextBudgetIndicator(
            fill_tokens=12_450,
            capacity_tokens=16_000,
            archived_blocks=0,
        )
        result = ind.format()
        assert "12,450" in result
        assert "16,000" in result
        assert "78%" in result
        assert "0 archived blocks" in result

    def test_format_unknown_capacity(self) -> None:
        ind = ContextBudgetIndicator(
            fill_tokens=5_000,
            archived_blocks=2,
        )
        result = ind.format()
        assert "5,000" in result
        assert "capacity unknown" in result
        assert "2 archived blocks" in result

    def test_fill_percent_known(self) -> None:
        ind = ContextBudgetIndicator(
            fill_tokens=8_000,
            capacity_tokens=10_000,
        )
        assert ind.fill_percent == pytest.approx(80.0)

    def test_fill_percent_unknown(self) -> None:
        ind = ContextBudgetIndicator(fill_tokens=8_000)
        assert ind.fill_percent is None

    def test_fill_percent_zero_fill(self) -> None:
        ind = ContextBudgetIndicator(
            fill_tokens=0,
            capacity_tokens=10_000,
        )
        assert ind.fill_percent == pytest.approx(0.0)

    def test_frozen(self) -> None:
        ind = ContextBudgetIndicator(fill_tokens=100)
        with pytest.raises(ValidationError):
            ind.fill_tokens = 200  # type: ignore[misc]


# ── estimate_context_fill ─────────────────────────────────────────


@pytest.mark.unit
class TestEstimateContextFill:
    """Context fill estimation."""

    def test_empty_conversation(self) -> None:
        result = estimate_context_fill(
            system_prompt_tokens=100,
            conversation=(),
            tool_definitions_count=0,
        )
        assert result == 100

    def test_with_messages(self) -> None:
        msgs = (
            ChatMessage(
                role=MessageRole.USER,
                content="a" * 40,
            ),
            ChatMessage(
                role=MessageRole.ASSISTANT,
                content="b" * 80,
            ),
        )
        est = DefaultTokenEstimator()
        conv_tokens = est.estimate_conversation_tokens(msgs)
        result = estimate_context_fill(
            system_prompt_tokens=50,
            conversation=msgs,
            tool_definitions_count=0,
        )
        assert result == 50 + conv_tokens

    def test_with_tools(self) -> None:
        result = estimate_context_fill(
            system_prompt_tokens=100,
            conversation=(),
            tool_definitions_count=3,
        )
        # 3 tools * 50 overhead = 150
        assert result == 100 + 150


# ── make_context_indicator ────────────────────────────────────────


@pytest.mark.unit
class TestMakeContextIndicator:
    """make_context_indicator factory."""

    def test_from_context_with_capacity(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        ctx = sample_agent_context.model_copy(
            update={
                "context_fill_tokens": 5_000,
                "context_capacity_tokens": 10_000,
            },
        )
        ind = make_context_indicator(ctx, archived_blocks=1)
        assert ind.fill_tokens == 5_000
        assert ind.capacity_tokens == 10_000
        assert ind.archived_blocks == 1

    def test_from_context_without_capacity(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        ind = make_context_indicator(sample_agent_context)
        assert ind.fill_tokens == 0
        assert ind.capacity_tokens is None
        assert ind.archived_blocks == 0


# ── update_context_fill ───────────────────────────────────────────


@pytest.mark.unit
class TestUpdateContextFill:
    """update_context_fill helper."""

    def test_updates_fill_tokens(
        self,
        sample_agent_context: AgentContext,
    ) -> None:
        ctx = sample_agent_context.model_copy(
            update={"context_capacity_tokens": 10_000},
        )
        msgs = (ChatMessage(role=MessageRole.SYSTEM, content="x" * 400),)
        ctx = ctx.model_copy(update={"conversation": msgs})
        updated = update_context_fill(
            ctx,
            system_prompt_tokens=200,
            tool_defs_count=2,
        )
        assert updated.context_fill_tokens > 0
        assert updated.context_fill_tokens != ctx.context_fill_tokens


# ── DefaultTokenEstimator.estimate_conversation_tokens ────────────


@pytest.mark.unit
class TestEstimateConversationTokens:
    """DefaultTokenEstimator.estimate_conversation_tokens."""

    def test_empty(self) -> None:
        est = DefaultTokenEstimator()
        assert est.estimate_conversation_tokens(()) == 0

    def test_single_message(self) -> None:
        est = DefaultTokenEstimator()
        msgs = (ChatMessage(role=MessageRole.USER, content="a" * 100),)
        result = est.estimate_conversation_tokens(msgs)
        # 100 chars / 4 = 25, + 4 overhead = 29
        assert result == 29

    def test_none_content(self) -> None:
        est = DefaultTokenEstimator()
        msgs = (
            ChatMessage(
                role=MessageRole.ASSISTANT,
                content="",
            ),
        )
        result = est.estimate_conversation_tokens(msgs)
        # empty content => 0 + 4 overhead = 4
        assert result == 4
