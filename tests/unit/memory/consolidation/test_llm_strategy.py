"""Tests for LLM consolidation strategy."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from synthorg.core.enums import MemoryCategory
from synthorg.memory.consolidation.llm_strategy import LLMConsolidationStrategy
from synthorg.memory.consolidation.strategy import ConsolidationStrategy
from synthorg.memory.models import MemoryEntry, MemoryMetadata
from synthorg.providers.enums import FinishReason
from synthorg.providers.errors import (
    AuthenticationError,
    RateLimitError,
)
from synthorg.providers.models import CompletionResponse, TokenUsage


def _make_entry(  # noqa: PLR0913
    *,
    entry_id: str = "mem-1",
    agent_id: str = "agent-1",
    content: str = "test memory",
    category: MemoryCategory = MemoryCategory.EPISODIC,
    created_at: datetime | None = None,
    relevance_score: float | None = None,
) -> MemoryEntry:
    """Helper to build a MemoryEntry with sensible defaults."""
    return MemoryEntry(
        id=entry_id,
        agent_id=agent_id,
        category=category,
        content=content,
        metadata=MemoryMetadata(),
        created_at=created_at or datetime.now(UTC),
        relevance_score=relevance_score,
    )


def _make_response(content: str = "synthesized summary") -> CompletionResponse:
    """Build a mock CompletionResponse."""
    return CompletionResponse(
        content=content,
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(input_tokens=10, output_tokens=5, cost_usd=0.001),
        model="test-model",
    )


def _make_strategy(
    *,
    provider: AsyncMock | None = None,
    backend: AsyncMock | None = None,
    group_threshold: int = 3,
) -> LLMConsolidationStrategy:
    """Build an LLMConsolidationStrategy with mock dependencies."""
    if backend is None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="summary-id-1")
        backend.delete = AsyncMock(return_value=True)
    if provider is None:
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=_make_response())
    return LLMConsolidationStrategy(
        backend=backend,
        provider=provider,
        model="test-model",
        group_threshold=group_threshold,
    )


@pytest.mark.unit
class TestLLMConsolidationStrategyProtocol:
    def test_is_consolidation_strategy(self) -> None:
        strategy = _make_strategy()
        assert isinstance(strategy, ConsolidationStrategy)


@pytest.mark.unit
class TestLLMConsolidationStrategyInit:
    def test_group_threshold_below_min_raises(self) -> None:
        with pytest.raises(ValueError, match=r"group_threshold must be >= 2"):
            _make_strategy(group_threshold=1)

    def test_group_threshold_two_accepted(self) -> None:
        strategy = _make_strategy(group_threshold=2)
        assert strategy._group_threshold == 2


@pytest.mark.unit
class TestLLMConsolidationStrategyConsolidate:
    async def test_empty_input_returns_empty_result(self) -> None:
        strategy = _make_strategy()
        result = await strategy.consolidate((), agent_id="agent-1")
        assert result.consolidated_count == 0
        assert result.summary_id is None

    async def test_below_threshold_skipped(self) -> None:
        strategy = _make_strategy(group_threshold=3)
        entries = tuple(_make_entry(entry_id=f"e{i}") for i in range(2))
        result = await strategy.consolidate(entries, agent_id="agent-1")
        assert result.consolidated_count == 0

    async def test_above_threshold_consolidates(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="summary-1")
        backend.delete = AsyncMock(return_value=True)
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=_make_response())

        strategy = LLMConsolidationStrategy(
            backend=backend,
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        now = datetime.now(UTC)
        entries = tuple(
            _make_entry(
                entry_id=f"e{i}",
                relevance_score=0.5 + i * 0.1,
                created_at=now,
            )
            for i in range(4)
        )

        result = await strategy.consolidate(entries, agent_id="agent-1")

        # Keeps best (e3 with 0.8 relevance), removes e0, e1, e2
        assert result.consolidated_count == 3
        assert result.summary_id == "summary-1"
        assert "e3" not in result.removed_ids

        # LLM was called
        provider.complete.assert_called_once()
        # Summary was stored
        backend.store.assert_called_once()
        # Removed entries were deleted
        assert backend.delete.call_count == 3

    async def test_multi_category_groups_independent(self) -> None:
        backend = AsyncMock()
        store_ids = iter(["sum-ep", "sum-sem"])
        backend.store = AsyncMock(side_effect=lambda *_a, **_kw: next(store_ids))
        backend.delete = AsyncMock(return_value=True)
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=_make_response())

        strategy = LLMConsolidationStrategy(
            backend=backend,
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        now = datetime.now(UTC)
        episodic = tuple(
            _make_entry(
                entry_id=f"ep{i}",
                category=MemoryCategory.EPISODIC,
                relevance_score=0.5,
                created_at=now,
            )
            for i in range(3)
        )
        semantic = tuple(
            _make_entry(
                entry_id=f"sem{i}",
                category=MemoryCategory.SEMANTIC,
                relevance_score=0.5,
                created_at=now,
            )
            for i in range(3)
        )

        result = await strategy.consolidate(
            (*episodic, *semantic),
            agent_id="agent-1",
        )

        # 2 entries removed per group (keep 1), 2 groups
        assert result.consolidated_count == 4
        assert provider.complete.call_count == 2
        assert backend.store.call_count == 2

    async def test_keeps_highest_relevance_entry(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="sum-1")
        backend.delete = AsyncMock(return_value=True)
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=_make_response())

        strategy = LLMConsolidationStrategy(
            backend=backend,
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        now = datetime.now(UTC)
        entries = (
            _make_entry(entry_id="low", relevance_score=0.3, created_at=now),
            _make_entry(entry_id="high", relevance_score=0.9, created_at=now),
            _make_entry(entry_id="mid", relevance_score=0.6, created_at=now),
        )

        result = await strategy.consolidate(entries, agent_id="agent-1")

        # "high" is kept, "low" and "mid" are removed
        assert "high" not in result.removed_ids
        assert "low" in result.removed_ids
        assert "mid" in result.removed_ids


@pytest.mark.unit
class TestLLMConsolidationStrategyErrorHandling:
    async def test_retryable_error_falls_back(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="sum-1")
        backend.delete = AsyncMock(return_value=True)
        provider = AsyncMock()
        provider.complete = AsyncMock(
            side_effect=RateLimitError("rate limited"),
        )

        strategy = LLMConsolidationStrategy(
            backend=backend,
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        entries = tuple(
            _make_entry(entry_id=f"e{i}", relevance_score=0.5) for i in range(3)
        )

        # Should not raise -- falls back to concatenation
        result = await strategy.consolidate(entries, agent_id="agent-1")
        assert result.consolidated_count == 2

        # Verify fallback content was stored (starts with "Consolidated")
        stored_request = backend.store.call_args[0][1]
        assert stored_request.content.startswith("Consolidated")

    async def test_non_retryable_error_propagates(self) -> None:
        provider = AsyncMock()
        provider.complete = AsyncMock(
            side_effect=AuthenticationError("bad key"),
        )

        strategy = LLMConsolidationStrategy(
            backend=AsyncMock(),
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        entries = tuple(
            _make_entry(entry_id=f"e{i}", relevance_score=0.5) for i in range(3)
        )

        with pytest.raises(AuthenticationError):
            await strategy.consolidate(entries, agent_id="agent-1")

    async def test_memory_error_propagates(self) -> None:
        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=MemoryError("oom"))

        strategy = LLMConsolidationStrategy(
            backend=AsyncMock(),
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        entries = tuple(
            _make_entry(entry_id=f"e{i}", relevance_score=0.5) for i in range(3)
        )

        with pytest.raises(MemoryError):
            await strategy.consolidate(entries, agent_id="agent-1")

    async def test_empty_llm_response_falls_back(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="sum-1")
        backend.delete = AsyncMock(return_value=True)
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=_make_response(content=""))

        strategy = LLMConsolidationStrategy(
            backend=backend,
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        entries = tuple(
            _make_entry(entry_id=f"e{i}", relevance_score=0.5) for i in range(3)
        )

        result = await strategy.consolidate(entries, agent_id="agent-1")
        assert result.consolidated_count == 2

        # Verify fallback content was stored
        stored_request = backend.store.call_args[0][1]
        assert stored_request.content.startswith("Consolidated")

    async def test_whitespace_llm_response_falls_back(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="sum-1")
        backend.delete = AsyncMock(return_value=True)
        provider = AsyncMock()
        provider.complete = AsyncMock(
            return_value=_make_response(content="   \n  "),
        )

        strategy = LLMConsolidationStrategy(
            backend=backend,
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        entries = tuple(
            _make_entry(entry_id=f"e{i}", relevance_score=0.5) for i in range(3)
        )

        result = await strategy.consolidate(entries, agent_id="agent-1")
        assert result.consolidated_count == 2

        stored_request = backend.store.call_args[0][1]
        assert stored_request.content.startswith("Consolidated")

    async def test_unexpected_error_falls_back(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="sum-1")
        backend.delete = AsyncMock(return_value=True)
        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("oops"))

        strategy = LLMConsolidationStrategy(
            backend=backend,
            provider=provider,
            model="test-model",
            group_threshold=3,
        )

        entries = tuple(
            _make_entry(entry_id=f"e{i}", relevance_score=0.5) for i in range(3)
        )

        result = await strategy.consolidate(entries, agent_id="agent-1")
        assert result.consolidated_count == 2
