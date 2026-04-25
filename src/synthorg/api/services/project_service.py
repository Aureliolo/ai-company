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
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.api import (
    API_PROJECT_CREATED,
    API_PROJECT_DELETED,
    API_PROJECT_LISTED,
    API_PROJECT_UPDATED,
)

if TYPE_CHECKING:
    from synthorg.persistence.project_protocol import ProjectRepository

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

    _repo: ProjectRepository

    def __init__(self, *, repo: ProjectRepository) -> None:
        self._repo = repo

    async def get(self, project_id: NotBlankStr) -> Project | None:
        """Fetch a project by id.

        Args:
            project_id: Identifier of the project to fetch.

        Returns:
            The project, or ``None`` when no row matches.

        Raises:
            QueryError: Repository read failure (logged at WARNING
                before propagating).
        """
        try:
            return await self._repo.get(project_id)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                API_PROJECT_LISTED,
                project_id=project_id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise

    async def list_projects(
        self,
        *,
        status: ProjectStatus | None = None,
        lead: NotBlankStr | None = None,
    ) -> tuple[Project, ...]:
        """List projects with optional ``status`` / ``lead`` filters.

        Emits ``API_PROJECT_LISTED`` at DEBUG with the result count for
        traceability under high-volume listing.

        Args:
            status: Restrict to projects in this lifecycle status.
            lead: Restrict to projects led by this agent id.

        Returns:
            Tuple of matching projects in repository order.

        Raises:
            QueryError: Repository read failure (logged at WARNING
                before propagating).
        """
        try:
            projects = await self._repo.list_projects(
                status=status,
                lead=lead,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                API_PROJECT_LISTED,
                status=status.value if status is not None else None,
                lead=lead,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise
        logger.debug(API_PROJECT_LISTED, count=len(projects))
        return projects

    async def create(self, project: Project) -> Project:
        """Persist a freshly-constructed project and audit the create.

        Args:
            project: Fully-validated project to persist.

        Returns:
            The same project (identity preserved for caller chaining).

        Raises:
            ConstraintViolationError: Duplicate id or invalid foreign
                reference (logged at WARNING before propagating).
            QueryError: Repository write failure (logged at WARNING
                before propagating).
        """
        try:
            await self._repo.save(project)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                API_PROJECT_CREATED,
                project_id=project.id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise
        logger.info(
            API_PROJECT_CREATED,
            project_id=project.id,
            status=project.status.value,
            lead=project.lead,
        )
        return project

    async def update(self, project: Project) -> Project:
        """Upsert an existing project and audit the update.

        Args:
            project: Project to upsert (must have an existing id).

        Returns:
            The same project (identity preserved for caller chaining).

        Raises:
            ConstraintViolationError: Invalid foreign reference (logged
                at WARNING before propagating).
            QueryError: Repository write failure (logged at WARNING
                before propagating).
        """
        try:
            await self._repo.save(project)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                API_PROJECT_UPDATED,
                project_id=project.id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise
        logger.info(
            API_PROJECT_UPDATED,
            project_id=project.id,
            status=project.status.value,
        )
        return project

    async def delete(self, project_id: NotBlankStr) -> bool:
        """Delete a project and audit the deletion.

        The audit event is only emitted when a row was actually removed,
        so monitoring keyed on ``API_PROJECT_DELETED`` does not see
        spurious entries for missing ids.

        Args:
            project_id: Identifier of the project to delete.

        Returns:
            ``True`` when a row was removed, ``False`` when no row matched.

        Raises:
            QueryError: Repository write failure (logged at WARNING
                before propagating).
        """
        try:
            deleted = await self._repo.delete(project_id)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                API_PROJECT_DELETED,
                project_id=project_id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise
        if deleted:
            logger.info(
                API_PROJECT_DELETED,
                project_id=project_id,
            )
        return deleted
