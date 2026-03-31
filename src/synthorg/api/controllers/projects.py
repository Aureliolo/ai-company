"""Project controller -- CRUD endpoints for project management."""

import uuid
from typing import Annotated

from litestar import Controller, Response, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import ApiResponse, CreateProjectRequest, PaginatedResponse
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.path_params import PathId  # noqa: TC001
from synthorg.core.enums import ProjectStatus
from synthorg.core.project import Project
from synthorg.observability import get_logger

logger = get_logger(__name__)

ProjectStatusFilter = Annotated[
    str | None,
    Parameter(
        required=False,
        description="Filter by project status",
    ),
]

LeadFilter = Annotated[
    str | None,
    Parameter(
        required=False,
        description="Filter by project lead agent ID",
    ),
]


class ProjectController(Controller):
    """CRUD controller for project management."""

    path = "/projects"
    tags = ("projects",)

    @get(guards=[require_read_access])
    async def list_projects(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
        status: ProjectStatusFilter = None,
        lead: LeadFilter = None,
    ) -> PaginatedResponse[Project]:
        """List projects with optional filters.

        Args:
            state: Application state.
            offset: Pagination offset.
            limit: Page size.
            status: Filter by project status.
            lead: Filter by project lead agent ID.

        Returns:
            Paginated list of projects.
        """
        parsed_status: ProjectStatus | None = None
        if status is not None:
            parsed_status = ProjectStatus(status)

        repo = state.app_state.persistence.projects
        projects = await repo.list_projects(
            status=parsed_status,
            lead=lead,
        )
        page, meta = paginate(projects, offset=offset, limit=limit)
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
            return Response(
                content=ApiResponse[Project](
                    error=f"Project {project_id!r} not found",
                ),
                status_code=404,
            )
        return Response(
            content=ApiResponse[Project](data=project),
            status_code=200,
        )

    @post(guards=[require_write_access])
    async def create_project(
        self,
        state: State,
        data: CreateProjectRequest,
    ) -> Response[ApiResponse[Project]]:
        """Create a new project.

        Args:
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
        return Response(
            content=ApiResponse[Project](data=project),
            status_code=201,
        )
