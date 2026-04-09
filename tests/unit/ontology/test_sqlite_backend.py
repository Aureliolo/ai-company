"""Tests for SQLiteOntologyBackend."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest

from synthorg.ontology.backends.sqlite.backend import SQLiteOntologyBackend
from synthorg.ontology.errors import (
    OntologyConnectionError,
    OntologyDuplicateError,
    OntologyNotFoundError,
)
from synthorg.ontology.models import (
    EntityDefinition,
    EntityField,
    EntityRelation,
    EntitySource,
    EntityTier,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


def _make_entity(  # noqa: PLR0913
    name: str = "Task",
    *,
    tier: EntityTier = EntityTier.CORE,
    source: EntitySource = EntitySource.AUTO,
    definition: str = "A unit of work.",
    fields: tuple[EntityField, ...] = (),
    relationships: tuple[EntityRelation, ...] = (),
) -> EntityDefinition:
    return EntityDefinition(
        name=name,
        tier=tier,
        source=source,
        definition=definition,
        fields=fields,
        relationships=relationships,
        created_by="system",
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.fixture
async def backend() -> AsyncGenerator[SQLiteOntologyBackend]:
    """A connected in-memory SQLiteOntologyBackend."""
    b = SQLiteOntologyBackend(db_path=":memory:")
    await b.connect()
    yield b
    await b.disconnect()


# ── Lifecycle ───────────────────────────────────────────────────


class TestLifecycle:
    async def test_connect_sets_connected(self) -> None:
        b = SQLiteOntologyBackend(db_path=":memory:")
        await b.connect()
        assert b.is_connected
        await b.disconnect()

    async def test_disconnect_clears_connected(self) -> None:
        b = SQLiteOntologyBackend(db_path=":memory:")
        await b.connect()
        await b.disconnect()
        assert not b.is_connected

    async def test_disconnect_idempotent(self) -> None:
        b = SQLiteOntologyBackend(db_path=":memory:")
        await b.connect()
        await b.disconnect()
        await b.disconnect()  # Should not raise.

    async def test_health_check_when_connected(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        assert await backend.health_check() is True

    async def test_health_check_when_disconnected(self) -> None:
        b = SQLiteOntologyBackend(db_path=":memory:")
        assert await b.health_check() is False

    async def test_backend_name(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        assert backend.backend_name == "sqlite"

    async def test_connect_idempotent(self) -> None:
        b = SQLiteOntologyBackend(db_path=":memory:")
        await b.connect()
        await b.connect()  # Second connect should not raise.
        assert b.is_connected
        await b.disconnect()


# ── Register ────────────────────────────────────────────────────


class TestRegister:
    async def test_register_and_get(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        entity = _make_entity()
        await backend.register(entity)
        result = await backend.get("Task")
        assert result.name == "Task"
        assert result.tier == EntityTier.CORE
        assert result.definition == "A unit of work."

    async def test_register_duplicate_raises(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        entity = _make_entity()
        await backend.register(entity)
        with pytest.raises(OntologyDuplicateError, match="Task"):
            await backend.register(entity)

    async def test_register_with_fields(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        fields = (
            EntityField(name="title", type_hint="str", description="Title"),
            EntityField(name="status", type_hint="str", description="Status"),
        )
        entity = _make_entity(fields=fields)
        await backend.register(entity)
        result = await backend.get("Task")
        assert len(result.fields) == 2
        assert result.fields[0].name == "title"

    async def test_register_with_relationships(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        rels = (
            EntityRelation(
                target="Agent",
                relation="assigned_to",
                description="Assignee",
            ),
        )
        entity = _make_entity(relationships=rels)
        await backend.register(entity)
        result = await backend.get("Task")
        assert len(result.relationships) == 1
        assert result.relationships[0].target == "Agent"


# ── Get ─────────────────────────────────────────────────────────


class TestGet:
    async def test_get_not_found_raises(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        with pytest.raises(OntologyNotFoundError, match="NoSuch"):
            await backend.get("NoSuch")


# ── Update ──────────────────────────────────────────────────────


class TestUpdate:
    async def test_update_replaces_definition(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        entity = _make_entity()
        await backend.register(entity)
        updated = entity.model_copy(
            update={
                "definition": "Updated definition.",
                "updated_at": datetime(2026, 4, 2, 12, 0, 0, tzinfo=UTC),
            },
        )
        await backend.update(updated)
        result = await backend.get("Task")
        assert result.definition == "Updated definition."

    async def test_update_not_found_raises(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        entity = _make_entity(name="Ghost")
        with pytest.raises(OntologyNotFoundError, match="Ghost"):
            await backend.update(entity)


# ── Delete ──────────────────────────────────────────────────────


class TestDelete:
    async def test_delete_removes_entity(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        entity = _make_entity()
        await backend.register(entity)
        await backend.delete("Task")
        with pytest.raises(OntologyNotFoundError):
            await backend.get("Task")

    async def test_delete_not_found_raises(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        with pytest.raises(OntologyNotFoundError, match="NoSuch"):
            await backend.delete("NoSuch")


# ── List ────────────────────────────────────────────────────────


class TestList:
    async def test_list_empty(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        result = await backend.list_entities()
        assert result == ()

    async def test_list_all(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        await backend.register(_make_entity("A"))
        await backend.register(_make_entity("B"))
        result = await backend.list_entities()
        names = {e.name for e in result}
        assert names == {"A", "B"}

    async def test_list_filter_by_tier(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        await backend.register(_make_entity("Core1", tier=EntityTier.CORE))
        await backend.register(_make_entity("User1", tier=EntityTier.USER))
        core_only = await backend.list_entities(tier=EntityTier.CORE)
        assert len(core_only) == 1
        assert core_only[0].name == "Core1"


# ── Search ──────────────────────────────────────────────────────


class TestSearch:
    async def test_search_by_name(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        await backend.register(_make_entity("TaskDef", definition="About tasks."))
        await backend.register(_make_entity("Agent", definition="About agents."))
        results = await backend.search("Task")
        assert len(results) == 1
        assert results[0].name == "TaskDef"

    async def test_search_by_definition(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        await backend.register(_make_entity("X", definition="A unit of work."))
        await backend.register(_make_entity("Y", definition="An agent identity."))
        results = await backend.search("unit of work")
        assert len(results) == 1
        assert results[0].name == "X"

    async def test_search_no_results(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        await backend.register(_make_entity())
        results = await backend.search("nonexistent")
        assert results == ()


# ── Version manifest ────────────────────────────────────────────


class TestVersionManifest:
    async def test_empty_manifest(
        self,
        backend: SQLiteOntologyBackend,
    ) -> None:
        manifest = await backend.get_version_manifest()
        assert manifest == {}


# ── Operations when disconnected ────────────────────────────────


class TestDisconnectedGuard:
    async def test_register_when_disconnected_raises(self) -> None:
        b = SQLiteOntologyBackend(db_path=":memory:")
        with pytest.raises(OntologyConnectionError):
            await b.register(_make_entity())

    async def test_get_when_disconnected_raises(self) -> None:
        b = SQLiteOntologyBackend(db_path=":memory:")
        with pytest.raises(OntologyConnectionError):
            await b.get("Task")
