"""Project repository protocol."""

from typing import Protocol, runtime_checkable

from synthorg.core.enums import ProjectStatus  # noqa: TC001
from synthorg.core.project import Project  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001


@runtime_checkable
class ProjectRepository(Protocol):
    """CRUD + query interface for Project persistence."""

    async def save(self, project: Project) -> None:
        """Persist a project (insert or update).

        Args:
            project: The project to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, project_id: NotBlankStr) -> Project | None:
        """Retrieve a project by its ID.

        Args:
            project_id: The project identifier.

        Returns:
            The project, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def list_projects(
        self,
        *,
        status: ProjectStatus | None = None,
        lead: NotBlankStr | None = None,
    ) -> tuple[Project, ...]:
        """List projects with optional filters.

        Results are ordered by project ID ascending to ensure
        deterministic pagination across backends.

        Args:
            status: Filter by project status.
            lead: Filter by project lead agent ID.

        Returns:
            Matching projects ordered by ID, as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, project_id: NotBlankStr) -> bool:
        """Delete a project by ID.

        Args:
            project_id: The project identifier.

        Returns:
            ``True`` if the project was deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...
