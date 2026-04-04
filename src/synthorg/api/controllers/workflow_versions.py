"""Workflow version history controller -- list, get, diff, rollback."""

from datetime import UTC, datetime
from typing import Annotated, Any

from litestar import Controller, Request, Response, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.auth.models import AuthenticatedUser
from synthorg.api.dto import (
    ApiResponse,
    PaginatedResponse,
    PaginationMeta,
    RollbackWorkflowRequest,
)
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset  # noqa: TC001
from synthorg.api.path_params import PathId  # noqa: TC001
from synthorg.engine.workflow.definition import (
    WorkflowDefinition,
)
from synthorg.engine.workflow.diff import WorkflowDiff, compute_diff
from synthorg.engine.workflow.version import WorkflowDefinitionVersion
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_definition import (
    WORKFLOW_DEF_DIFF_COMPUTED,
    WORKFLOW_DEF_INVALID_REQUEST,
    WORKFLOW_DEF_NOT_FOUND,
    WORKFLOW_DEF_ROLLED_BACK,
    WORKFLOW_DEF_VERSION_CONFLICT,
    WORKFLOW_DEF_VERSION_LISTED,
)
from synthorg.persistence.errors import VersionConflictError

logger = get_logger(__name__)


def _get_auth_user_id(request: Request[Any, Any, Any]) -> str:
    """Extract the authenticated user ID from a request."""
    auth_user = request.scope.get("user")
    if isinstance(auth_user, AuthenticatedUser):
        return auth_user.user_id
    return "api"


def _build_version_snapshot(
    definition: WorkflowDefinition,
    saved_by: str,
) -> WorkflowDefinitionVersion:
    """Build a version snapshot from a definition.

    The snapshot's ``saved_at`` is set to the definition's
    ``updated_at`` timestamp, not the current time.
    """
    return WorkflowDefinitionVersion(
        definition_id=definition.id,
        version=definition.version,
        name=definition.name,
        description=definition.description,
        workflow_type=definition.workflow_type,
        nodes=definition.nodes,
        edges=definition.edges,
        created_by=definition.created_by,
        saved_by=saved_by,
        saved_at=definition.updated_at,
    )


class WorkflowVersionController(Controller):
    """Version history, diff, and rollback for workflow definitions."""

    path = "/workflows"
    tags = ("workflows",)

    @get("/{workflow_id:str}/versions", guards=[require_read_access])
    async def list_versions(
        self,
        state: State,
        workflow_id: PathId,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 20,
    ) -> Response[PaginatedResponse[WorkflowDefinitionVersion]]:
        """List version history for a workflow definition."""
        version_repo = state.app_state.persistence.workflow_versions
        versions = await version_repo.list_versions(
            workflow_id,
            limit=limit,
            offset=offset,
        )
        total = await version_repo.count_versions(workflow_id)
        logger.debug(
            WORKFLOW_DEF_VERSION_LISTED,
            definition_id=workflow_id,
            count=len(versions),
        )
        meta = PaginationMeta(total=total, offset=offset, limit=limit)
        return Response(
            content=PaginatedResponse[WorkflowDefinitionVersion](
                data=versions,
                pagination=meta,
            ),
        )

    @get(
        "/{workflow_id:str}/versions/{version_num:int}",
        guards=[require_read_access],
    )
    async def get_version(
        self,
        state: State,
        workflow_id: PathId,
        version_num: Annotated[int, Parameter(ge=1)],
    ) -> Response[ApiResponse[WorkflowDefinitionVersion]]:
        """Get a specific version snapshot."""
        version_repo = state.app_state.persistence.workflow_versions
        version = await version_repo.get_version(workflow_id, version_num)
        if version is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
                version=version_num,
            )
            return Response(
                content=ApiResponse[WorkflowDefinitionVersion](
                    error=f"Version {version_num} not found",
                ),
                status_code=404,
            )
        return Response(
            content=ApiResponse[WorkflowDefinitionVersion](data=version),
        )

    @get("/{workflow_id:str}/diff", guards=[require_read_access])
    async def get_diff(
        self,
        state: State,
        workflow_id: PathId,
        from_version: Annotated[
            int,
            Parameter(required=True, ge=1, description="Source version"),
        ],
        to_version: Annotated[
            int,
            Parameter(required=True, ge=1, description="Target version"),
        ],
    ) -> Response[ApiResponse[WorkflowDiff]]:
        """Compute diff between two versions of a workflow definition."""
        if from_version == to_version:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                definition_id=workflow_id,
                error="from_version and to_version must differ",
            )
            return Response(
                content=ApiResponse[WorkflowDiff](
                    error="from_version and to_version must differ",
                ),
                status_code=400,
            )

        version_repo = state.app_state.persistence.workflow_versions
        old = await version_repo.get_version(workflow_id, from_version)
        if old is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
                version=from_version,
            )
            return Response(
                content=ApiResponse[WorkflowDiff](
                    error=f"Version {from_version} not found",
                ),
                status_code=404,
            )
        new = await version_repo.get_version(workflow_id, to_version)
        if new is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
                version=to_version,
            )
            return Response(
                content=ApiResponse[WorkflowDiff](
                    error=f"Version {to_version} not found",
                ),
                status_code=404,
            )

        diff = compute_diff(old, new)
        logger.debug(
            WORKFLOW_DEF_DIFF_COMPUTED,
            definition_id=workflow_id,
            from_version=from_version,
            to_version=to_version,
        )
        return Response(
            content=ApiResponse[WorkflowDiff](data=diff),
        )

    @post(
        "/{workflow_id:str}/rollback",
        guards=[require_write_access],
        status_code=200,
    )
    async def rollback_workflow(
        self,
        request: Request[Any, Any, Any],
        state: State,
        workflow_id: PathId,
        data: RollbackWorkflowRequest,
    ) -> Response[ApiResponse[WorkflowDefinition]]:
        """Rollback a workflow to a previous version."""
        repo = state.app_state.persistence.workflow_definitions
        existing = await repo.get(workflow_id)
        if existing is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error="Workflow definition not found",
                ),
                status_code=404,
            )

        if data.expected_version != existing.version:
            logger.warning(
                WORKFLOW_DEF_VERSION_CONFLICT,
                definition_id=workflow_id,
                expected=data.expected_version,
                actual=existing.version,
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=(
                        f"Version conflict: expected "
                        f"{data.expected_version}, "
                        f"actual {existing.version}"
                    ),
                ),
                status_code=409,
            )

        version_repo = state.app_state.persistence.workflow_versions
        target = await version_repo.get_version(
            workflow_id,
            data.target_version,
        )
        if target is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
                version=data.target_version,
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Target version {data.target_version} not found",
                ),
                status_code=404,
            )

        updater = _get_auth_user_id(request)
        now = datetime.now(UTC)

        rolled_back = WorkflowDefinition(
            id=existing.id,
            name=target.name,
            description=target.description,
            workflow_type=target.workflow_type,
            nodes=target.nodes,
            edges=target.edges,
            created_by=existing.created_by,
            created_at=existing.created_at,
            updated_at=now,
            version=existing.version + 1,
        )

        try:
            await repo.save(rolled_back)
        except VersionConflictError as exc:
            logger.warning(
                WORKFLOW_DEF_VERSION_CONFLICT,
                definition_id=workflow_id,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Version conflict during rollback: {exc}",
                ),
                status_code=409,
            )

        snapshot = _build_version_snapshot(rolled_back, updater)
        await version_repo.save_version(snapshot)
        logger.info(
            WORKFLOW_DEF_ROLLED_BACK,
            definition_id=workflow_id,
            target_version=data.target_version,
            new_version=rolled_back.version,
        )
        return Response(
            content=ApiResponse[WorkflowDefinition](data=rolled_back),
        )
