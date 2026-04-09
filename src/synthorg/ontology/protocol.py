"""OntologyBackend protocol -- lifecycle + CRUD + versioning.

Application code depends on this protocol for ontology data access.
Concrete backends (SQLite, etc.) implement this interface.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.ontology.models import EntityDefinition, EntityTier


@runtime_checkable
class OntologyBackend(Protocol):
    """Lifecycle management and CRUD for entity definitions.

    Concrete backends implement this protocol to provide connection
    management, entity persistence, search, and version manifests.

    Attributes:
        is_connected: Whether the backend has an active connection.
        backend_name: Human-readable backend identifier.
    """

    async def connect(self) -> None:
        """Establish connection and apply schema.

        Raises:
            OntologyConnectionError: If the connection cannot be
                established.
        """
        ...

    async def disconnect(self) -> None:
        """Close the backend connection.

        Safe to call even if not connected.
        """
        ...

    async def health_check(self) -> bool:
        """Check whether the backend is healthy and responsive.

        Returns:
            ``True`` if the backend is reachable and operational.
        """
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the backend has an active connection."""
        ...

    @property
    def backend_name(self) -> NotBlankStr:
        """Human-readable backend identifier (e.g. ``"sqlite"``)."""
        ...

    async def register(self, entity: EntityDefinition) -> None:
        """Register a new entity definition.

        Args:
            entity: The entity definition to register.

        Raises:
            OntologyDuplicateError: If an entity with the same name
                already exists.
        """
        ...

    async def get(self, name: str) -> EntityDefinition:
        """Retrieve an entity definition by name.

        Args:
            name: Entity name.

        Returns:
            The matching entity definition.

        Raises:
            OntologyNotFoundError: If no entity with the given name
                exists.
        """
        ...

    async def update(self, entity: EntityDefinition) -> None:
        """Update an existing entity definition.

        Args:
            entity: The updated entity definition (matched by name).

        Raises:
            OntologyNotFoundError: If no entity with the given name
                exists.
        """
        ...

    async def delete(self, name: str) -> None:
        """Delete an entity definition by name.

        Args:
            name: Entity name.

        Raises:
            OntologyNotFoundError: If no entity with the given name
                exists.
        """
        ...

    async def list_entities(
        self,
        *,
        tier: EntityTier | None = None,
    ) -> tuple[EntityDefinition, ...]:
        """List all entity definitions, optionally filtered by tier.

        Args:
            tier: If provided, only return entities of this tier.

        Returns:
            Tuple of matching entity definitions.
        """
        ...

    async def search(self, query: str) -> tuple[EntityDefinition, ...]:
        """Search entity definitions by name or definition text.

        Matching is implementation-defined (e.g. substring via SQL LIKE
        for the SQLite backend).

        Args:
            query: Search string (matched against name and definition).

        Returns:
            Tuple of matching entity definitions.
        """
        ...

    async def get_version_manifest(self) -> dict[str, int]:
        """Return the latest version number for each entity.

        Returns:
            Mapping from entity name to its latest version number.
        """
        ...
