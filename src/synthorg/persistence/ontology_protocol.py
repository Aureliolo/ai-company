"""Ontology repository protocols -- entity definitions + drift reports.

Replaces the old parallel ``OntologyBackend`` abstraction.  Composite
methods (search orchestration, version-manifest assembly, drift
comparisons) belong to ``synthorg.ontology.service.OntologyService``,
not the data layer.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.ontology.models import (
        DriftReport,
        EntityDefinition,
        EntityTier,
    )


@runtime_checkable
class OntologyEntityRepository(Protocol):
    """CRUD interface for entity definitions."""

    async def register(self, entity: EntityDefinition) -> None:
        """Register a new entity definition.

        Raises:
            OntologyDuplicateError: If an entity with the same name
                already exists.
        """
        ...

    async def get(self, name: NotBlankStr) -> EntityDefinition:
        """Retrieve an entity definition by name.

        Raises:
            OntologyNotFoundError: If no entity with that name exists.
        """
        ...

    async def update(self, entity: EntityDefinition) -> None:
        """Update an existing entity definition (matched by name).

        Raises:
            OntologyNotFoundError: If no entity with that name exists.
        """
        ...

    async def delete(self, name: NotBlankStr) -> None:
        """Delete an entity definition by name.

        Raises:
            OntologyNotFoundError: If no entity with that name exists.
        """
        ...

    async def list_entities(
        self,
        *,
        tier: EntityTier | None = None,
    ) -> tuple[EntityDefinition, ...]:
        """List all entity definitions, optionally filtered by tier."""
        ...

    async def search(
        self,
        query: NotBlankStr,
    ) -> tuple[EntityDefinition, ...]:
        """Substring search against entity name and definition text."""
        ...


@runtime_checkable
class OntologyDriftReportRepository(Protocol):
    """Storage protocol for drift detection reports."""

    async def store_report(self, report: DriftReport) -> None:
        """Persist a drift report."""
        ...

    async def get_latest(
        self,
        entity_name: NotBlankStr,
        *,
        limit: int = 10,
    ) -> tuple[DriftReport, ...]:
        """Return most recent drift reports for an entity."""
        ...

    async def get_all_latest(
        self,
        *,
        limit: int = 100,
    ) -> tuple[DriftReport, ...]:
        """Return the most recent drift report for each entity."""
        ...
