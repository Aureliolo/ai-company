"""Tests for Pareto frontier-based memory pruning strategy."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from synthorg.memory.procedural.pruning.pareto_strategy import (
    ParetoPruningStrategy,
)


class TestParetoPruningStrategy:
    """Pareto pruning strategy tests."""

    @pytest.mark.unit
    async def test_name_property(self) -> None:
        """Test that strategy has correct name."""
        strategy = ParetoPruningStrategy(max_entries=100)
        assert strategy.name == "pareto"

    @pytest.mark.unit
    async def test_empty_entries(self) -> None:
        """Test pruning with empty entries."""
        strategy = ParetoPruningStrategy(max_entries=100)
        result = await strategy.prune(agent_id="test-agent-1", entries=())
        assert result == ()

    @pytest.mark.unit
    async def test_entries_under_limit_no_pruning(self) -> None:
        """Test that no pruning occurs when under max_entries."""
        entries = []
        for i in range(50):
            entry = MagicMock()
            entry.id = f"mem-{i}"
            entry.relevance_score = 0.5
            entries.append(entry)

        strategy = ParetoPruningStrategy(max_entries=100)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        assert result == ()

    @pytest.mark.unit
    async def test_pareto_frontier_basic(self) -> None:
        """Test basic Pareto frontier calculation.

        Entry A: relevance=1.0, created 2 days ago (oldest)
        Entry B: relevance=0.5, created 0 days ago (newest)
        Entry C: relevance=0.0, created 1 day ago (middle)

        Only B and A are on the Pareto frontier.
        C is dominated by B (lower relevance and lower recency).
        """
        now = datetime.now(UTC)
        entries = []

        entry_a = MagicMock()
        entry_a.id = "mem-a"
        entry_a.relevance_score = 1.0
        entry_a.created_at = now - timedelta(days=2)  # oldest
        entries.append(entry_a)

        entry_b = MagicMock()
        entry_b.id = "mem-b"
        entry_b.relevance_score = 0.5
        entry_b.created_at = now  # newest
        entries.append(entry_b)

        entry_c = MagicMock()
        entry_c.id = "mem-c"
        entry_c.relevance_score = 0.0
        entry_c.created_at = now - timedelta(days=1)  # middle
        entries.append(entry_c)

        strategy = ParetoPruningStrategy(max_entries=2)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        # C is dominated and should be pruned
        assert set(result) == {"mem-c"}

    @pytest.mark.unit
    async def test_high_relevance_kept(self) -> None:
        """Test that high-relevance entries are kept."""
        now = datetime.now(UTC)
        entries = []
        for i in range(5):
            entry = MagicMock()
            entry.id = f"mem-{i}"
            entry.relevance_score = 1.0 - (i * 0.1)
            entry.created_at = now - timedelta(days=i)
            entries.append(entry)

        strategy = ParetoPruningStrategy(max_entries=3)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        # mem-0 dominates all others (highest relevance + most recent)
        assert "mem-0" not in result
        assert set(result) == {"mem-1", "mem-2", "mem-3", "mem-4"}

    @pytest.mark.unit
    async def test_none_relevance_score(self) -> None:
        """Test entries with None relevance_score."""
        now = datetime.now(UTC)
        entry_with_score = MagicMock()
        entry_with_score.id = "mem-1"
        entry_with_score.relevance_score = 0.8
        entry_with_score.created_at = now

        entry_no_score = MagicMock()
        entry_no_score.id = "mem-2"
        entry_no_score.relevance_score = None
        entry_no_score.created_at = now - timedelta(days=1)

        strategy = ParetoPruningStrategy(max_entries=1)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(entry_with_score, entry_no_score),
        )
        # Entries with None score are treated as 0.0
        assert set(result) == {"mem-2"}

    @pytest.mark.unit
    async def test_equals_max_entries_no_pruning(self) -> None:
        """Test when entry count equals max_entries."""
        entries = []
        for i in range(5):
            entry = MagicMock()
            entry.id = f"mem-{i}"
            entry.relevance_score = 0.5
            entries.append(entry)

        strategy = ParetoPruningStrategy(max_entries=5)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        assert result == ()

    @pytest.mark.unit
    async def test_single_entry_below_limit(self) -> None:
        """Test with single entry below limit."""
        entry = MagicMock()
        entry.id = "mem-1"
        entry.relevance_score = 0.5

        strategy = ParetoPruningStrategy(max_entries=100)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(entry,),
        )
        assert result == ()

    @pytest.mark.unit
    async def test_default_max_entries_is_100(self) -> None:
        """Test that default max_entries is 100."""
        strategy = ParetoPruningStrategy()
        entries = []
        for i in range(50):
            entry = MagicMock()
            entry.id = f"mem-{i}"
            entry.relevance_score = 0.5
            entries.append(entry)

        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        assert result == ()

    @pytest.mark.unit
    async def test_all_same_relevance(self) -> None:
        """Test entries with identical relevance scores.

        When all have same relevance, recency becomes the differentiator.
        """
        now = datetime.now(UTC)
        entries = []
        for i in range(3):
            entry = MagicMock()
            entry.id = f"mem-{i}"
            entry.relevance_score = 0.5
            entry.created_at = now - timedelta(days=i)
            entries.append(entry)

        strategy = ParetoPruningStrategy(max_entries=2)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        # 3 entries with same relevance: mem-0 dominates on recency,
        # frontier = [mem-0], so mem-1 and mem-2 are pruned
        assert len(result) == 2
        assert set(result) == {"mem-1", "mem-2"}

    @pytest.mark.unit
    async def test_dominated_entries_pruned(self) -> None:
        """Test that strictly dominated entries are identified for pruning."""
        now = datetime.now(UTC)
        entries = []

        entry_dominant = MagicMock()
        entry_dominant.id = "mem-dominant"
        entry_dominant.relevance_score = 1.0
        entry_dominant.created_at = now  # newest
        entries.append(entry_dominant)

        entry_dominated = MagicMock()
        entry_dominated.id = "mem-dominated"
        entry_dominated.relevance_score = 0.5
        entry_dominated.created_at = now - timedelta(days=1)  # older
        entries.append(entry_dominated)

        strategy = ParetoPruningStrategy(max_entries=1)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        assert set(result) == {"mem-dominated"}

    @pytest.mark.unit
    async def test_frontier_over_cap_truncates_by_recency(self) -> None:
        """Test frontier trimming when frontier exceeds max_entries.

        Create entries that are all non-dominated (different relevance-recency
        tradeoffs), so the entire frontier exceeds max_entries. The strategy
        should keep only the most recent entries up to max_entries.
        """
        now = datetime.now(UTC)

        # 4 entries with inverse relevance-recency correlation
        # (no entry dominates another)
        e1 = MagicMock()
        e1.id = "e1"
        e1.relevance_score = 1.0
        e1.created_at = now - timedelta(days=3)  # highest rel, oldest

        e2 = MagicMock()
        e2.id = "e2"
        e2.relevance_score = 0.7
        e2.created_at = now - timedelta(days=2)

        e3 = MagicMock()
        e3.id = "e3"
        e3.relevance_score = 0.4
        e3.created_at = now - timedelta(days=1)

        e4 = MagicMock()
        e4.id = "e4"
        e4.relevance_score = 0.1
        e4.created_at = now  # lowest rel, newest

        strategy = ParetoPruningStrategy(max_entries=2)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(e1, e2, e3, e4),
        )
        # All 4 are on the frontier (non-dominated). Trimmed to 2 most
        # recent: e4, e3 kept. e1, e2 pruned.
        assert set(result) == {"e1", "e2"}
