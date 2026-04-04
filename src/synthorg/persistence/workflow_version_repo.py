"""Repository protocol for workflow definition version persistence."""

from typing import Protocol, runtime_checkable

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.version import WorkflowDefinitionVersion  # noqa: TC001


@runtime_checkable
class WorkflowVersionRepository(Protocol):
    """CRUD interface for workflow definition version snapshots.

    Version records are immutable once created -- they capture the
    exact state of a definition at a point in time.
    """

    async def save_version(self, version: WorkflowDefinitionVersion) -> None:
        """Persist a version snapshot (insert only, idempotent).

        Args:
            version: The version snapshot to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_version(
        self,
        definition_id: NotBlankStr,
        version: int,
    ) -> WorkflowDefinitionVersion | None:
        """Retrieve a specific version snapshot.

        Args:
            definition_id: The parent definition ID.
            version: The version number.

        Returns:
            The version snapshot, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def list_versions(
        self,
        definition_id: NotBlankStr,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[WorkflowDefinitionVersion, ...]:
        """List version snapshots for a definition.

        Results are ordered by version descending (newest first).

        Args:
            definition_id: The parent definition ID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            Matching versions as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def count_versions(self, definition_id: NotBlankStr) -> int:
        """Count version snapshots for a definition.

        Args:
            definition_id: The parent definition ID.

        Returns:
            Number of version records.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete_versions_for_definition(self, definition_id: NotBlankStr) -> int:
        """Delete all version snapshots for a definition.

        Args:
            definition_id: The parent definition ID.

        Returns:
            Number of deleted records.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...
