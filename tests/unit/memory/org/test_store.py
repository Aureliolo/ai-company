"""Tests for SQLiteOrgFactStore."""

from datetime import UTC, datetime

import pytest

from ai_company.core.enums import OrgFactCategory, SeniorityLevel
from ai_company.memory.org.errors import OrgMemoryConnectionError
from ai_company.memory.org.models import OrgFact, OrgFactAuthor
from ai_company.memory.org.store import SQLiteOrgFactStore

pytestmark = pytest.mark.timeout(30)

_NOW = datetime.now(UTC)
_HUMAN_AUTHOR = OrgFactAuthor(is_human=True)
_AGENT_AUTHOR = OrgFactAuthor(
    agent_id="agent-1",
    seniority=SeniorityLevel.SENIOR,
    is_human=False,
)


def _make_fact(
    fact_id: str = "fact-1",
    content: str = "Test fact",
    category: OrgFactCategory = OrgFactCategory.ADR,
    version: int = 1,
) -> OrgFact:
    return OrgFact(
        id=fact_id,
        content=content,
        category=category,
        author=_HUMAN_AUTHOR,
        created_at=_NOW,
        version=version,
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

    async def test_save_and_get(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            fact = _make_fact()
            await store.save(fact)
            retrieved = await store.get("fact-1")
            assert retrieved is not None
            assert retrieved.id == "fact-1"
            assert retrieved.content == "Test fact"
            assert retrieved.category == OrgFactCategory.ADR
            assert retrieved.version == 1
        finally:
            await store.disconnect()

    async def test_get_nonexistent(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            result = await store.get("nonexistent")
            assert result is None
        finally:
            await store.disconnect()

    async def test_query_by_category(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "Fact A", OrgFactCategory.ADR))
            await store.save(_make_fact("f2", "Fact B", OrgFactCategory.PROCEDURE))
            await store.save(_make_fact("f3", "Fact C", OrgFactCategory.ADR))

            results = await store.query(
                categories=frozenset({OrgFactCategory.ADR}),
            )
            assert len(results) == 2
            assert all(r.category == OrgFactCategory.ADR for r in results)
        finally:
            await store.disconnect()

    async def test_query_by_text(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", "Code review required"))
            await store.save(_make_fact("f2", "Deploy always on Friday"))

            results = await store.query(text="review")
            assert len(results) == 1
            assert results[0].id == "f1"
        finally:
            await store.disconnect()

    async def test_query_with_limit(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            for i in range(10):
                await store.save(_make_fact(f"f{i}", f"Fact {i}"))
            results = await store.query(limit=3)
            assert len(results) == 3
        finally:
            await store.disconnect()

    async def test_list_by_category(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1", category=OrgFactCategory.CONVENTION))
            await store.save(_make_fact("f2", category=OrgFactCategory.CONVENTION))
            await store.save(_make_fact("f3", category=OrgFactCategory.ADR))

            results = await store.list_by_category(OrgFactCategory.CONVENTION)
            assert len(results) == 2
        finally:
            await store.disconnect()

    async def test_delete(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            await store.save(_make_fact("f1"))
            assert await store.delete("f1") is True
            assert await store.get("f1") is None
        finally:
            await store.disconnect()

    async def test_delete_nonexistent(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            assert await store.delete("nonexistent") is False
        finally:
            await store.disconnect()

    async def test_save_with_agent_author(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        await store.connect()
        try:
            fact = OrgFact(
                id="f1",
                content="Agent fact",
                category=OrgFactCategory.ADR,
                author=_AGENT_AUTHOR,
                created_at=_NOW,
                version=1,
            )
            await store.save(fact)
            retrieved = await store.get("f1")
            assert retrieved is not None
            assert retrieved.author.agent_id == "agent-1"
            assert retrieved.author.seniority == SeniorityLevel.SENIOR
            assert retrieved.author.is_human is False
        finally:
            await store.disconnect()

    async def test_operations_when_not_connected_raise(self) -> None:
        store = SQLiteOrgFactStore(":memory:")
        with pytest.raises(OrgMemoryConnectionError):
            await store.save(_make_fact())
        with pytest.raises(OrgMemoryConnectionError):
            await store.get("f1")
        with pytest.raises(OrgMemoryConnectionError):
            await store.query()
        with pytest.raises(OrgMemoryConnectionError):
            await store.delete("f1")
