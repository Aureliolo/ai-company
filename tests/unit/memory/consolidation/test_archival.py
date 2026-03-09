"""Tests for ArchivalStore protocol compliance."""

from datetime import UTC, datetime

import pytest

from ai_company.core.enums import MemoryCategory
from ai_company.memory.consolidation.archival import ArchivalStore
from ai_company.memory.consolidation.models import ArchivalEntry

pytestmark = pytest.mark.timeout(30)

_NOW = datetime.now(UTC)


class _MockArchivalStore:
    """Mock implementation of ArchivalStore for protocol tests."""

    def __init__(self) -> None:
        self._entries: dict[str, ArchivalEntry] = {}
        self._next_id = 0

    async def archive(self, entry: ArchivalEntry) -> str:
        self._next_id += 1
        archive_id = f"archive-{self._next_id}"
        self._entries[archive_id] = entry
        return archive_id

    async def search(self, query: object) -> tuple[ArchivalEntry, ...]:
        return tuple(self._entries.values())

    async def restore(self, entry_id: str) -> ArchivalEntry | None:
        return self._entries.get(entry_id)

    async def count(self, agent_id: str) -> int:
        return sum(1 for e in self._entries.values() if e.agent_id == agent_id)


@pytest.mark.unit
class TestArchivalStoreProtocol:
    """ArchivalStore is runtime_checkable."""

    def test_mock_is_instance(self) -> None:
        store = _MockArchivalStore()
        assert isinstance(store, ArchivalStore)


@pytest.mark.unit
class TestMockArchivalStoreRoundTrip:
    """Archive/search/restore round-trip."""

    async def test_archive_and_search(self) -> None:
        store = _MockArchivalStore()
        entry = ArchivalEntry(
            original_id="mem-1",
            agent_id="agent-1",
            content="Archived memory",
            category=MemoryCategory.EPISODIC,
            created_at=_NOW,
            archived_at=_NOW,
        )
        archive_id = await store.archive(entry)
        assert archive_id == "archive-1"

        results = await store.search(None)
        assert len(results) == 1
        assert results[0].original_id == "mem-1"

    async def test_restore(self) -> None:
        store = _MockArchivalStore()
        entry = ArchivalEntry(
            original_id="mem-1",
            agent_id="agent-1",
            content="Test",
            category=MemoryCategory.WORKING,
            created_at=_NOW,
            archived_at=_NOW,
        )
        archive_id = await store.archive(entry)
        restored = await store.restore(archive_id)
        assert restored is not None
        assert restored.original_id == "mem-1"

    async def test_restore_nonexistent(self) -> None:
        store = _MockArchivalStore()
        assert await store.restore("nonexistent") is None

    async def test_count(self) -> None:
        store = _MockArchivalStore()
        entry = ArchivalEntry(
            original_id="mem-1",
            agent_id="agent-1",
            content="Test",
            category=MemoryCategory.WORKING,
            created_at=_NOW,
            archived_at=_NOW,
        )
        await store.archive(entry)
        assert await store.count("agent-1") == 1
        assert await store.count("agent-2") == 0
