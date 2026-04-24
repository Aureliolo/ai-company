"""Project controller -- endpoints for project listing, creation and deletion."""

import uuid
from typing import Annotated, Any

from litestar import Controller, Request, Response, delete, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter
from litestar.status_codes import HTTP_204_NO_CONTENT

from synthorg.api.channels import CHANNEL_PROJECTS, publish_ws_event
from synthorg.api.dto import (
    ApiResponse,
    CreateProjectRequest,
    PaginatedResponse,
)
from synthorg.api.errors import ApiValidationError, NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import CursorLimit, CursorParam, paginate_cursor
from synthorg.api.path_params import QUERY_MAX_LENGTH, PathId
from synthorg.api.ws_models import WsEventType
from synthorg.core.enums import ProjectStatus
from synthorg.core.project import Project
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_PROJECT_DELETED,
    PERSISTENCE_PROJECT_SAVED,
)

logger = get_logger(__name__)


ProjectStatusFilter = Annotated[
    NotBlankStr | None,
    Parameter(
        required=False,
        max_length=QUERY_MAX_LENGTH,
        description="Filter by project status",
    ),
]

LeadFilter = Annotated[
    NotBlankStr | None,
    Parameter(
        required=False,
        max_length=QUERY_MAX_LENGTH,
        description="Filter by project lead agent ID",
    ),
]


class ProjectController(Controller):
    """Controller for project listing, creation, and deletion."""

    path = "/projects"
    tags = ("projects",)

    @get(guards=[require_read_access])
    async def list_projects(
        self,
        state: State,
        cursor: CursorParam = None,
        limit: CursorLimit = 50,
        status: ProjectStatusFilter = None,
        lead: LeadFilter = None,
    ) -> PaginatedResponse[Project]:
        """List projects with optional filters.

        Args:
            state: Application state.
            cursor: Opaque pagination cursor from the previous page.
            limit: Page size.
            status: Filter by project status.
            lead: Filter by project lead agent ID.

        Returns:
            Paginated list of projects.

        Raises:
            ApiValidationError: ``status`` is not a valid
                :class:`ProjectStatus` value.
        """
        parsed_status: ProjectStatus | None = None
        if status is not None:
            try:
                parsed_status = ProjectStatus(status)
            except ValueError as exc:
                valid = ", ".join(e.value for e in ProjectStatus)
                msg = f"Invalid project status: {status!r}. Valid values: {valid}"
                raise ApiValidationError(msg) from exc

        repo = state.app_state.persistence.projects
        projects = await repo.list_projects(
            status=parsed_status,
            lead=lead,
        )
        page, meta = paginate_cursor(
            projects,
            limit=limit,
            cursor=cursor,
            secret=state.app_state.cursor_secret,
        )
        return PaginatedResponse[Project](data=page, pagination=meta)

    @get("/{project_id:str}", guards=[require_read_access])
    async def get_project(
        self,
        state: State,
        project_id: PathId,
    ) -> Response[ApiResponse[Project]]:
        """Get a project by ID.

        Args:
            state: Application state.
            project_id: Project identifier.

        Returns:
            The project, or 404 if not found.
        """
        repo = state.app_state.persistence.projects
        project = await repo.get(project_id)
        if project is None:
            msg = f"Project {project_id!r} not found"
            raise NotFoundError(msg)
        return Response(
            content=ApiResponse[Project](data=project),
            status_code=200,
        )

    @delete(
        "/{project_id:str}",
        guards=[require_write_access],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def delete_project(
        self,
        request: Request[Any, Any, Any],
        state: State,
        project_id: PathId,
    ) -> None:
        """Delete a project by ID.

        Args:
            request: The incoming request.
            state: Application state.
            project_id: Project identifier.

        Raises:
            NotFoundError: Project with ``project_id`` does not exist.
        """
        repo = state.app_state.persistence.projects
        project = await repo.get(project_id)
        if project is None:
            msg = f"Project {project_id!r} not found"
            raise NotFoundError(msg)
        deleted = await repo.delete(project_id)
        if not deleted:
            msg = f"Project {project_id!r} not found"
            raise NotFoundError(msg)
        logger.info(PERSISTENCE_PROJECT_DELETED, project_id=project_id)
        publish_ws_event(
            request,
            WsEventType.PROJECT_DELETED,
            CHANNEL_PROJECTS,
            {"project_id": project_id, "name": project.name},
        )

    @post(guards=[require_write_access])
    async def create_project(
        self,
        request: Request[Any, Any, Any],
        state: State,
        data: CreateProjectRequest,
    ) -> Response[ApiResponse[Project]]:
        """Create a new project.

        Args:
            request: The incoming request.
            state: Application state.
            data: Project creation payload.

        Returns:
            The created project with generated ID.
        """
        project = Project(
            id=f"proj-{uuid.uuid4().hex[:12]}",
            name=data.name,
            description=data.description,
            team=data.team,
            lead=data.lead,
            deadline=data.deadline,
            budget=data.budget,
        )
        repo = state.app_state.persistence.projects
        await repo.save(project)
        logger.info(PERSISTENCE_PROJECT_SAVED, project_id=project.id)
        publish_ws_event(
            request,
            WsEventType.PROJECT_CREATED,
            CHANNEL_PROJECTS,
            {
                "project_id": project.id,
                "name": project.name,
                "status": project.status.value,
                "lead": project.lead,
            },
        )
        return Response(
            content=ApiResponse[Project](data=project),
            status_code=201,
        )
