"""Tests for SQLiteOrgFactStore (MVCC implementation)."""

import sqlite3
from unittest.mock import AsyncMock

import pytest

from synthorg.core.enums import OrgFactCategory, SeniorityLevel
from synthorg.memory.org.errors import (
    OrgMemoryConnectionError,
    OrgMemoryQueryError,
    OrgMemoryWriteError,
)
from synthorg.memory.org.models import OrgFact
from synthorg.memory.org.sqlite_store import (
    SQLiteOrgFactStore,
    _snapshot_row_to_org_fact,
)

# Import conftest fixtures and helpers
from .conftest import (
    _NOW,
    AGENT_AUTHOR,
    HUMAN_AUTHOR,
    _make_fact,
)


@pytest.mark.unit
class TestSQLiteOrgFactStoreLifecycle:
    """Connection lifecycle tests."""

    async def test_connect_disconnect(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        assert store.is_connected is True
        await store.disconnect()
        assert store.is_connected is False

    async def test_disconnect_when_not_connected(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.disconnect()

    async def test_double_connect_is_safe(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        await store.connect()
        assert store.is_connected is True
        await store.disconnect()

    async def test_backend_name(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        assert store.backend_name == "sqlite_org_facts"


@pytest.mark.unit
class TestSQLiteOrgFactStoreOperations:
    """CRUD operation tests."""

    async def test_save_and_get(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        fact = _make_fact()
        await connected_store.save(fact)
        retrieved = await connected_store.get("fact-1")
        assert retrieved is not None
        assert retrieved.id == "fact-1"
        assert retrieved.content == "Test fact"
        assert retrieved.category == OrgFactCategory.ADR

    async def test_get_nonexistent(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        result = await connected_store.get("nonexistent")
        assert result is None

    async def test_query_by_category(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        await connected_store.save(_make_fact("f1", "Fact A", OrgFactCategory.ADR))
        await connected_store.save(
            _make_fact("f2", "Fact B", OrgFactCategory.PROCEDURE),
        )
        await connected_store.save(_make_fact("f3", "Fact C", OrgFactCategory.ADR))

        results = await connected_store.query(
            categories=frozenset({OrgFactCategory.ADR}),
        )
        assert len(results) == 2
        assert all(r.category == OrgFactCategory.ADR for r in results)

    async def test_query_by_text(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        await connected_store.save(_make_fact("f1", "Code review required"))
        await connected_store.save(_make_fact("f2", "Deploy always on Friday"))

        results = await connected_store.query(text="review")
        assert len(results) == 1
        assert results[0].id == "f1"

    async def test_query_with_limit(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        for i in range(10):
            await connected_store.save(_make_fact(f"f{i}", f"Fact {i}"))
        results = await connected_store.query(limit=3)
        assert len(results) == 3

    async def test_list_by_category(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        await connected_store.save(
            _make_fact("f1", category=OrgFactCategory.CONVENTION),
        )
        await connected_store.save(
            _make_fact("f2", category=OrgFactCategory.CONVENTION),
        )
        await connected_store.save(_make_fact("f3", category=OrgFactCategory.ADR))

        results = await connected_store.list_by_category(
            OrgFactCategory.CONVENTION,
        )
        assert len(results) == 2

    async def test_delete(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        await connected_store.save(_make_fact("f1"))
        assert await connected_store.delete("f1", author=HUMAN_AUTHOR) is True
        assert await connected_store.get("f1") is None

    async def test_delete_nonexistent(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        assert await connected_store.delete("nonexistent", author=HUMAN_AUTHOR) is False

    async def test_save_with_agent_author(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        fact = OrgFact(
            id="f1",
            content="Agent fact",
            category=OrgFactCategory.ADR,
            author=AGENT_AUTHOR,
            created_at=_NOW,
        )
        await connected_store.save(fact)
        retrieved = await connected_store.get("f1")
        assert retrieved is not None
        assert retrieved.author.agent_id == "agent-1"
        assert retrieved.author.seniority == SeniorityLevel.SENIOR
        assert retrieved.author.is_human is False

    async def test_operations_when_not_connected_raise(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConnectionError):
            await store.save(_make_fact())
        with pytest.raises(OrgMemoryConnectionError):
            await store.get("f1")
        with pytest.raises(OrgMemoryConnectionError):
            await store.query()
        with pytest.raises(OrgMemoryConnectionError):
            await store.delete("f1", author=HUMAN_AUTHOR)

    async def test_list_by_category_when_not_connected(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConnectionError):
            await store.list_by_category(OrgFactCategory.ADR)

    async def test_save_duplicate_id_republishes(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        """Re-publishing a fact creates a new version in the log."""
        await connected_store.save(_make_fact("f1", "Original content"))
        await connected_store.save(_make_fact("f1", "Updated content"))
        retrieved = await connected_store.get("f1")
        assert retrieved is not None
        assert retrieved.content == "Updated content"

    async def test_query_combined_category_and_text(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        await connected_store.save(
            _make_fact(
                "f1",
                "Code review required",
                OrgFactCategory.ADR,
            ),
        )
        await connected_store.save(
            _make_fact(
                "f2",
                "Code review optional",
                OrgFactCategory.PROCEDURE,
            ),
        )
        await connected_store.save(
            _make_fact(
                "f3",
                "Deploy on Friday",
                OrgFactCategory.ADR,
            ),
        )

        results = await connected_store.query(
            categories=frozenset({OrgFactCategory.ADR}),
            text="review",
        )
        assert len(results) == 1
        assert results[0].id == "f1"

    async def test_connect_with_invalid_path(self) -> None:
        store = SQLiteOrgFactStore("/nonexistent/dir/db.sqlite")
        with pytest.raises(OrgMemoryConnectionError) as exc_info:
            await store.connect()
        assert exc_info.value.__cause__ is not None

    async def test_save_sqlite_error_wraps(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        store._db = AsyncMock()
        store._db.execute = AsyncMock(
            side_effect=sqlite3.Error("disk I/O error"),
        )
        with pytest.raises(OrgMemoryWriteError, match="disk I/O error"):
            await store.save(_make_fact())
        store._db = None

    async def test_get_sqlite_error_wraps(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        store._db = AsyncMock()
        store._db.execute = AsyncMock(
            side_effect=sqlite3.Error("disk I/O error"),
        )
        with pytest.raises(OrgMemoryQueryError, match="disk I/O error"):
            await store.get("f1")
        store._db = None

    async def test_query_sqlite_error_wraps(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        store._db = AsyncMock()
        store._db.execute = AsyncMock(
            side_effect=sqlite3.Error("disk I/O error"),
        )
        with pytest.raises(OrgMemoryQueryError, match="disk I/O error"):
            await store.query()
        store._db = None

    async def test_delete_sqlite_error_wraps(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        store._db = AsyncMock()
        store._db.execute = AsyncMock(
            side_effect=sqlite3.Error("disk I/O error"),
        )
        with pytest.raises(OrgMemoryWriteError, match="disk I/O error"):
            await store.delete("f1", author=HUMAN_AUTHOR)
        store._db = None

    def test_path_traversal_rejected(self) -> None:
        with pytest.raises(
            OrgMemoryConnectionError,
            match="Path traversal",
        ):
            SQLiteOrgFactStore("../../../etc/db")

    async def test_like_special_chars_escaped(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        await connected_store.save(_make_fact("f1", "100% complete"))
        await connected_store.save(_make_fact("f2", "field_name here"))
        await connected_store.save(_make_fact("f3", "normal text"))

        results_percent = await connected_store.query(text="%")
        assert len(results_percent) == 1
        assert results_percent[0].id == "f1"

        results_underscore = await connected_store.query(text="_")
        assert len(results_underscore) == 1
        assert results_underscore[0].id == "f2"

    async def test_list_by_category_sqlite_error_wraps(self) -> None:
        """list_by_category wraps sqlite3.Error."""
        store = SQLiteOrgFactStore(":memory:")
        store._db = AsyncMock()
        store._db.execute = AsyncMock(
            side_effect=sqlite3.Error("disk I/O error"),
        )
        with pytest.raises(OrgMemoryQueryError, match="disk I/O error"):
            await store.list_by_category(OrgFactCategory.ADR)
        store._db = None

    async def test_row_parse_error_wraps_in_query_error(self) -> None:
        malformed_row = {
            "fact_id": "f1",
            "content": "test",
            "category": "INVALID_CATEGORY",
            "tags": "[]",
            "author_agent_id": None,
            "author_seniority": None,
            "author_is_human": 1,
            "author_autonomy_level": None,
            "created_at": _NOW.isoformat(),
            "retracted_at": None,
            "version": 1,
        }
        mock_row = AsyncMock()
        mock_row.__getitem__ = lambda self, key: malformed_row[key]
        with pytest.raises(
            OrgMemoryQueryError,
            match="Failed to deserialize",
        ):
            _snapshot_row_to_org_fact(mock_row)

    async def test_save_with_tags(
        self,
        connected_store: SQLiteOrgFactStore,
    ) -> None:
        """Tags are persisted and retrievable."""
        fact = OrgFact(
            id="f1",
            content="Tagged fact",
            category=OrgFactCategory.ADR,
            tags=("core-policy", "security"),
            author=HUMAN_AUTHOR,
            created_at=_NOW,
        )
        await connected_store.save(fact)
        retrieved = await connected_store.get("f1")
        assert retrieved is not None
        assert retrieved.tags == ("core-policy", "security")
