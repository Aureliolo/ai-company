"""Integration tests for the ontology subsystem.

Full lifecycle: backend + versioning + service + bootstrap.
"""

from datetime import UTC, datetime

import pytest

from synthorg.ontology.backends.sqlite.backend import SQLiteOntologyBackend
from synthorg.ontology.config import (
    EntitiesConfig,
    EntityEntry,
    OntologyConfig,
)
from synthorg.ontology.decorator import clear_entity_registry, ontology_entity
from synthorg.ontology.models import (
    EntityDefinition,
    EntitySource,
    EntityTier,
)
from synthorg.ontology.service import OntologyService
from synthorg.ontology.versioning import create_ontology_versioning

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Clear the decorator registry before each test."""
    clear_entity_registry()


class TestFullBootstrapLifecycle:
    """End-to-end: backend + versioning + service + bootstrap."""

    async def test_bootstrap_from_decorated_models(
        self,
        on_disk_backend: SQLiteOntologyBackend,
    ) -> None:
        from pydantic import BaseModel, Field

        @ontology_entity
        class IntegTask(BaseModel):
            """A task for integration testing."""

            title: str = Field(description="Task title")
            status: str = Field(description="Current status")

        @ontology_entity
        class IntegAgent(BaseModel):
            """An agent for integration testing."""

            name: str = Field(description="Agent name")

        versioning = create_ontology_versioning(on_disk_backend.get_db())
        service = OntologyService(
            backend=on_disk_backend,
            versioning=versioning,
            config=OntologyConfig(),
        )

        registered = await service.bootstrap()
        assert registered == 2

        # Verify entities in backend.
        entities = await service.list_entities()
        names = {e.name for e in entities}
        assert names == {"IntegTask", "IntegAgent"}

        # Verify fields derived correctly.
        task_entity = await service.get("IntegTask")
        assert task_entity.tier == EntityTier.CORE
        assert task_entity.source == EntitySource.AUTO
        field_names = {f.name for f in task_entity.fields}
        assert "title" in field_names
        assert "status" in field_names

    async def test_bootstrap_from_config(
        self,
        on_disk_backend: SQLiteOntologyBackend,
    ) -> None:
        versioning = create_ontology_versioning(on_disk_backend.get_db())
        service = OntologyService(
            backend=on_disk_backend,
            versioning=versioning,
            config=OntologyConfig(),
        )

        entries = EntitiesConfig(
            entries=(
                EntityEntry(
                    name="Invoice",
                    definition="A financial document for billing.",
                    fields={"amount": "Total amount", "currency": "Currency code"},
                ),
                EntityEntry(
                    name="Contract",
                    definition="A legal agreement between parties.",
                ),
            ),
        )
        registered = await service.bootstrap_from_config(entries)
        assert registered == 2

        invoice = await service.get("Invoice")
        assert invoice.tier == EntityTier.USER
        assert invoice.source == EntitySource.CONFIG
        assert len(invoice.fields) == 2

    async def test_bootstrap_idempotent(
        self,
        on_disk_backend: SQLiteOntologyBackend,
    ) -> None:
        from pydantic import BaseModel

        @ontology_entity
        class Idempotent(BaseModel):
            """Idempotent entity."""

        versioning = create_ontology_versioning(on_disk_backend.get_db())
        service = OntologyService(
            backend=on_disk_backend,
            versioning=versioning,
            config=OntologyConfig(),
        )

        first = await service.bootstrap()
        assert first == 1

        # Second bootstrap should skip.
        second = await service.bootstrap()
        assert second == 0

    async def test_version_snapshots_created(
        self,
        on_disk_backend: SQLiteOntologyBackend,
    ) -> None:
        from pydantic import BaseModel, Field

        @ontology_entity
        class Versioned(BaseModel):
            """A versioned entity."""

            value: str = Field(description="Some value")

        versioning = create_ontology_versioning(on_disk_backend.get_db())
        service = OntologyService(
            backend=on_disk_backend,
            versioning=versioning,
            config=OntologyConfig(),
        )

        await service.bootstrap()

        manifest = await on_disk_backend.get_version_manifest()
        assert "Versioned" in manifest
        assert manifest["Versioned"] == 1

    async def test_update_creates_new_version(
        self,
        on_disk_backend: SQLiteOntologyBackend,
    ) -> None:
        from pydantic import BaseModel

        @ontology_entity
        class Evolving(BaseModel):
            """An evolving entity."""

        versioning = create_ontology_versioning(on_disk_backend.get_db())
        service = OntologyService(
            backend=on_disk_backend,
            versioning=versioning,
            config=OntologyConfig(),
        )

        await service.bootstrap()

        # Update the entity.
        entity = await service.get("Evolving")
        updated = entity.model_copy(
            update={
                "definition": "An evolved entity with new meaning.",
                "updated_at": datetime(2026, 4, 2, 12, 0, 0, tzinfo=UTC),
            },
        )
        await service.update(updated)

        manifest = await on_disk_backend.get_version_manifest()
        assert manifest["Evolving"] == 2

    async def test_search(
        self,
        on_disk_backend: SQLiteOntologyBackend,
    ) -> None:
        versioning = create_ontology_versioning(on_disk_backend.get_db())
        service = OntologyService(
            backend=on_disk_backend,
            versioning=versioning,
            config=OntologyConfig(),
        )

        entity = EntityDefinition(
            name="SearchTarget",
            tier=EntityTier.USER,
            source=EntitySource.API,
            definition="A unique searchable definition about invoicing.",
            created_by="test",
            created_at=_NOW,
            updated_at=_NOW,
        )
        await service.register(entity)

        results = await service.search("invoicing")
        assert len(results) == 1
        assert results[0].name == "SearchTarget"

    async def test_data_persists_across_reconnect(
        self,
        db_path: str,
    ) -> None:
        # Write with first connection.
        backend1 = SQLiteOntologyBackend(db_path=db_path)
        await backend1.connect()
        try:
            entity = EntityDefinition(
                name="Persistent",
                tier=EntityTier.CORE,
                source=EntitySource.AUTO,
                definition="Should survive reconnect.",
                created_by="system",
                created_at=_NOW,
                updated_at=_NOW,
            )
            await backend1.register(entity)
        finally:
            await backend1.disconnect()

        # Read with second connection.
        backend2 = SQLiteOntologyBackend(db_path=db_path)
        await backend2.connect()
        try:
            result = await backend2.get("Persistent")
            assert result.name == "Persistent"
            assert result.definition == "Should survive reconnect."
        finally:
            await backend2.disconnect()
