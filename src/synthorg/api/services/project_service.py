"""Project admin service layer.

Thin wrapper over :class:`ProjectRepository` so the ``/projects``
controller does not reach into ``app_state.persistence.projects``
directly.  CRUD mechanics live here with uniform ``API_PROJECT_*``
audit logging, mirroring the structure of :class:`UserService` and
:class:`ArtifactService`.
"""

from typing import TYPE_CHECKING

from synthorg.core.enums import ProjectStatus  # noqa: TC001
from synthorg.core.project import Project  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_PROJECT_CREATED,
    API_PROJECT_DELETED,
    API_PROJECT_LISTED,
    API_PROJECT_UPDATED,
)

if TYPE_CHECKING:
    from synthorg.persistence.artifact_project_repos import ProjectRepository

logger = get_logger(__name__)


class ProjectService:
    """Wraps :class:`ProjectRepository` with uniform audit logging.

    Errors from the underlying repository (``ConstraintViolationError``,
    ``QueryError``) propagate unchanged so the controller can map them
    to the appropriate HTTP response.

    Args:
        repo: Project repository implementation.
    """

    __slots__ = ("_repo",)

    def __init__(self, *, repo: ProjectRepository) -> None:
        self._repo = repo

    async def get(self, project_id: NotBlankStr) -> Project | None:
        """Fetch a project by id, or ``None`` when no row matches."""
        return await self._repo.get(project_id)

    async def list_projects(
        self,
        *,
        status: ProjectStatus | None = None,
        lead: NotBlankStr | None = None,
    ) -> tuple[Project, ...]:
        """List projects with optional status / lead filters."""
        projects = await self._repo.list_projects(
            status=status,
            lead=lead,
        )
        logger.debug(API_PROJECT_LISTED, count=len(projects))
        return projects

    async def create(self, project: Project) -> Project:
        """Persist a freshly-constructed project."""
        await self._repo.save(project)
        logger.info(
            API_PROJECT_CREATED,
            project_id=project.id,
            status=project.status.value,
            lead=project.lead,
        )
        return project

    async def update(self, project: Project) -> Project:
        """Upsert an existing project."""
        await self._repo.save(project)
        logger.info(
            API_PROJECT_UPDATED,
            project_id=project.id,
            status=project.status.value,
        )
        return project

    async def delete(self, project_id: NotBlankStr) -> bool:
        """Delete a project; returns ``True`` when a row was removed."""
        deleted = await self._repo.delete(project_id)
        if deleted:
            logger.info(
                API_PROJECT_DELETED,
                project_id=project_id,
            )
        return deleted
