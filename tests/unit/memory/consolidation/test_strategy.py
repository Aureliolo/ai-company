"""Tests for SimpleConsolidationStrategy."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from ai_company.core.enums import MemoryCategory
from ai_company.memory.consolidation.simple_strategy import (
    SimpleConsolidationStrategy,
)
from ai_company.memory.models import MemoryEntry, MemoryMetadata

pytestmark = pytest.mark.timeout(30)

_NOW = datetime.now(UTC)
_AGENT_ID = "test-agent"


def _make_entry(
    entry_id: str,
    category: MemoryCategory = MemoryCategory.EPISODIC,
    relevance: float | None = 0.5,
    age_hours: int = 0,
) -> MemoryEntry:
    return MemoryEntry(
        id=entry_id,
        agent_id=_AGENT_ID,
        category=category,
        content=f"Content for {entry_id}",
        metadata=MemoryMetadata(),
        created_at=_NOW - timedelta(hours=age_hours),
        relevance_score=relevance,
    )


@pytest.mark.unit
class TestSimpleConsolidationStrategy:
    """SimpleConsolidationStrategy behaviour."""

    async def test_empty_input(self) -> None:
        backend = AsyncMock()
        strategy = SimpleConsolidationStrategy(backend=backend)
        result = await strategy.consolidate((), agent_id=_AGENT_ID)
        assert result.consolidated_count == 0
        assert result.removed_ids == ()
        assert result.summary_id is None

    async def test_single_category_below_threshold(self) -> None:
        backend = AsyncMock()
        strategy = SimpleConsolidationStrategy(
            backend=backend,
            group_threshold=5,
        )
        entries = tuple(_make_entry(f"m{i}") for i in range(2))
        result = await strategy.consolidate(entries, agent_id=_AGENT_ID)
        assert result.consolidated_count == 0
        backend.delete.assert_not_called()

    async def test_single_category_above_threshold(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="summary-1")
        backend.delete = AsyncMock(return_value=True)

        strategy = SimpleConsolidationStrategy(
            backend=backend,
            group_threshold=3,
        )
        entries = tuple(_make_entry(f"m{i}", relevance=0.1 * i) for i in range(5))
        result = await strategy.consolidate(entries, agent_id=_AGENT_ID)
        assert result.consolidated_count == 4
        assert result.summary_id == "summary-1"
        assert len(result.removed_ids) == 4

    async def test_multi_category(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="summary-1")
        backend.delete = AsyncMock(return_value=True)

        strategy = SimpleConsolidationStrategy(
            backend=backend,
            group_threshold=3,
        )
        entries = (
            _make_entry("e1", MemoryCategory.EPISODIC),
            _make_entry("e2", MemoryCategory.EPISODIC),
            _make_entry("e3", MemoryCategory.EPISODIC),
            _make_entry("s1", MemoryCategory.SEMANTIC),
            _make_entry("s2", MemoryCategory.SEMANTIC),
        )
        result = await strategy.consolidate(entries, agent_id=_AGENT_ID)
        assert result.consolidated_count == 2
        assert all(
            rid in ("e1", "e2") or rid in ("e1", "e3") or rid in ("e2", "e3")
            for rid in result.removed_ids
        )

    async def test_keeps_highest_relevance(self) -> None:
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="summary-1")
        backend.delete = AsyncMock(return_value=True)

        strategy = SimpleConsolidationStrategy(
            backend=backend,
            group_threshold=3,
        )
        entries = (
            _make_entry("low", relevance=0.1),
            _make_entry("mid", relevance=0.5),
            _make_entry("high", relevance=0.9),
        )
        result = await strategy.consolidate(entries, agent_id=_AGENT_ID)
        assert "high" not in result.removed_ids
        assert "low" in result.removed_ids
        assert "mid" in result.removed_ids
