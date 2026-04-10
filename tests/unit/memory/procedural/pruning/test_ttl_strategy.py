"""Tests for TTL-based memory pruning strategy."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from synthorg.memory.procedural.pruning.ttl_strategy import TtlPruningStrategy


class TestTtlPruningStrategy:
    """TTL pruning strategy tests."""

    @pytest.mark.unit
    async def test_name_property(self) -> None:
        """Test that strategy has correct name."""
        strategy = TtlPruningStrategy(max_age_days=90)
        assert strategy.name == "ttl"

    @pytest.mark.unit
    async def test_empty_entries(self) -> None:
        """Test pruning with empty entries."""
        strategy = TtlPruningStrategy(max_age_days=90)
        result = await strategy.prune(agent_id="test-agent-1", entries=())
        assert result == ()

    @pytest.mark.unit
    async def test_no_expired_entries(self) -> None:
        """Test when all entries are recent."""
        now = datetime.now(UTC)
        recent = MagicMock()
        recent.id = "mem-1"
        recent.created_at = now - timedelta(days=10)

        strategy = TtlPruningStrategy(max_age_days=90)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(recent,),
        )
        assert result == ()

    @pytest.mark.unit
    async def test_all_expired_entries(self) -> None:
        """Test when all entries exceed max age."""
        now = datetime.now(UTC)
        old = MagicMock()
        old.id = "mem-1"
        old.created_at = now - timedelta(days=120)

        strategy = TtlPruningStrategy(max_age_days=90)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(old,),
        )
        assert result == ("mem-1",)

    @pytest.mark.unit
    async def test_mixed_expired_and_recent(self) -> None:
        """Test with mix of expired and recent entries."""
        now = datetime.now(UTC)
        recent = MagicMock()
        recent.id = "mem-1"
        recent.created_at = now - timedelta(days=10)

        old = MagicMock()
        old.id = "mem-2"
        old.created_at = now - timedelta(days=120)

        very_old = MagicMock()
        very_old.id = "mem-3"
        very_old.created_at = now - timedelta(days=200)

        strategy = TtlPruningStrategy(max_age_days=90)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(recent, old, very_old),
        )
        assert set(result) == {"mem-2", "mem-3"}

    @pytest.mark.unit
    async def test_boundary_age(self) -> None:
        """Test entry at exactly max_age_days boundary (not pruned)."""
        now = datetime.now(UTC)
        # Slightly under the boundary to avoid timing drift between
        # the two datetime.now() calls (test vs strategy).
        boundary = MagicMock()
        boundary.id = "mem-1"
        boundary.created_at = now - timedelta(days=89, hours=23, minutes=59)

        strategy = TtlPruningStrategy(max_age_days=90)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(boundary,),
        )
        # Entry is under max_age, should not be pruned
        assert result == ()

    @pytest.mark.unit
    async def test_custom_max_age(self) -> None:
        """Test with custom max_age_days value."""
        now = datetime.now(UTC)
        entry = MagicMock()
        entry.id = "mem-1"
        entry.created_at = now - timedelta(days=35)

        strategy = TtlPruningStrategy(max_age_days=30)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(entry,),
        )
        assert result == ("mem-1",)

    @pytest.mark.unit
    async def test_multiple_expired_preserve_ids(self) -> None:
        """Test that all expired entry IDs are returned."""
        now = datetime.now(UTC)
        expired_ids = []
        entries = []
        for i in range(5):
            entry = MagicMock()
            entry.id = f"mem-expired-{i}"
            entry.created_at = now - timedelta(days=100 + i)
            entries.append(entry)
            expired_ids.append(f"mem-expired-{i}")

        strategy = TtlPruningStrategy(max_age_days=90)
        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=tuple(entries),
        )
        assert set(result) == set(expired_ids)

    @pytest.mark.unit
    async def test_default_max_age_is_90_days(self) -> None:
        """Test that default max_age_days is 90."""
        strategy = TtlPruningStrategy()
        now = datetime.now(UTC)
        entry = MagicMock()
        entry.id = "mem-1"
        entry.created_at = now - timedelta(days=91)

        result = await strategy.prune(
            agent_id="test-agent-1",
            entries=(entry,),
        )
        assert result == ("mem-1",)
