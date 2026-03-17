"""Property-based tests for context budget indicators."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthorg.engine.context_budget import ContextBudgetIndicator
from synthorg.engine.token_estimation import DefaultTokenEstimator
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage


@pytest.mark.unit
class TestContextBudgetIndicatorProperties:
    """Hypothesis property tests for ContextBudgetIndicator."""

    @given(
        fill=st.integers(min_value=0, max_value=1_000_000),
        capacity=st.one_of(
            st.none(),
            st.integers(min_value=1, max_value=1_000_000),
        ),
        archived=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=200)
    def test_format_never_crashes(
        self,
        fill: int,
        capacity: int | None,
        archived: int,
    ) -> None:
        ind = ContextBudgetIndicator(
            fill_tokens=fill,
            capacity_tokens=capacity,
            archived_blocks=archived,
        )
        text = ind.format()
        assert isinstance(text, str)
        assert len(text) > 0

    @given(
        fill=st.integers(min_value=0, max_value=1_000_000),
        capacity=st.integers(min_value=1, max_value=1_000_000),
    )
    @settings(max_examples=200)
    def test_fill_percent_non_negative(
        self,
        fill: int,
        capacity: int,
    ) -> None:
        ind = ContextBudgetIndicator(
            fill_tokens=fill,
            capacity_tokens=capacity,
        )
        pct = ind.fill_percent
        assert pct is not None
        assert pct >= 0.0

    @given(fill=st.integers(min_value=0, max_value=1_000_000))
    @settings(max_examples=200)
    def test_fill_percent_none_without_capacity(
        self,
        fill: int,
    ) -> None:
        ind = ContextBudgetIndicator(fill_tokens=fill)
        assert ind.fill_percent is None


@pytest.mark.unit
class TestEstimateConversationTokensProperties:
    """Hypothesis property tests for conversation token estimation."""

    @given(
        contents=st.lists(
            st.text(min_size=0, max_size=500),
            min_size=0,
            max_size=50,
        ),
    )
    @settings(max_examples=200)
    def test_estimate_non_negative(
        self,
        contents: list[str],
    ) -> None:
        msgs = tuple(ChatMessage(role=MessageRole.USER, content=c) for c in contents)
        estimator = DefaultTokenEstimator()
        tokens = estimator.estimate_conversation_tokens(msgs)
        assert tokens >= 0
