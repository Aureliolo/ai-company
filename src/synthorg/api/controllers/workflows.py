"""Workflow definition controller -- CRUD, validation, and YAML export."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from litestar import Controller, Request, Response, delete, get, patch, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter
from litestar.status_codes import HTTP_204_NO_CONTENT
from pydantic import ValidationError

from synthorg.api.auth.models import AuthenticatedUser
from synthorg.api.dto import (
    ApiResponse,
    BlueprintInfoResponse,
    CreateFromBlueprintRequest,
    CreateWorkflowDefinitionRequest,
    PaginatedResponse,
    RollbackWorkflowRequest,
    UpdateWorkflowDefinitionRequest,
)
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.path_params import QUERY_MAX_LENGTH, PathId
from synthorg.core.enums import WorkflowType
from synthorg.core.types import NotBlankStr
from synthorg.engine.workflow.blueprint_errors import (
    BlueprintNotFoundError,
    BlueprintValidationError,
)
from synthorg.engine.workflow.blueprint_loader import (
    list_blueprints,
    load_blueprint,
)
from synthorg.engine.workflow.definition import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from synthorg.engine.workflow.diff import WorkflowDiff, compute_diff
from synthorg.engine.workflow.validation import (
    WorkflowValidationResult,
)
from synthorg.engine.workflow.validation import (
    validate_workflow as run_workflow_validation,
)
from synthorg.engine.workflow.version import WorkflowDefinitionVersion
from synthorg.engine.workflow.yaml_export import export_workflow_yaml
from synthorg.observability import get_logger
from synthorg.observability.events.blueprint import (
    BLUEPRINT_INSTANTIATE_FAILED,
    BLUEPRINT_INSTANTIATE_START,
    BLUEPRINT_INSTANTIATE_SUCCESS,
)
from synthorg.observability.events.workflow_definition import (
    WORKFLOW_DEF_CREATED,
    WORKFLOW_DEF_DELETED,
    WORKFLOW_DEF_DIFF_COMPUTED,
    WORKFLOW_DEF_INVALID_REQUEST,
    WORKFLOW_DEF_NOT_FOUND,
    WORKFLOW_DEF_ROLLED_BACK,
    WORKFLOW_DEF_UPDATED,
    WORKFLOW_DEF_VERSION_CONFLICT,
    WORKFLOW_DEF_VERSION_LISTED,
)
from synthorg.persistence.errors import VersionConflictError

logger = get_logger(__name__)


def _build_update_fields(
    data: UpdateWorkflowDefinitionRequest,
) -> dict[str, object] | Response[ApiResponse[WorkflowDefinition]]:
    """Build the update dict from the request, or return error."""
    updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
    if data.name is not None:
        updates["name"] = data.name
    if data.description is not None:
        updates["description"] = data.description
    if data.workflow_type is not None:
        updates["workflow_type"] = data.workflow_type
    if data.nodes is not None:
        try:
            updates["nodes"] = tuple(WorkflowNode.model_validate(n) for n in data.nodes)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                field="nodes",
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Invalid nodes: {exc}",
                ),
                status_code=422,
            )
    if data.edges is not None:
        try:
            updates["edges"] = tuple(WorkflowEdge.model_validate(e) for e in data.edges)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                field="edges",
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Invalid edges: {exc}",
                ),
                status_code=422,
            )
    return updates


def _build_version_snapshot(
    definition: WorkflowDefinition,
    saved_by: str,
) -> WorkflowDefinitionVersion:
    """Build a version snapshot from a definition."""
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


WorkflowTypeFilter = Annotated[
    NotBlankStr | None,
    Parameter(
        required=False,
        max_length=QUERY_MAX_LENGTH,
        description="Filter by workflow type",
    ),
]


class WorkflowController(Controller):
    """CRUD, validation, and export for workflow definitions."""

    path = "/workflows"
    tags = ("workflows",)

    @get(guards=[require_read_access])
    async def list_workflows(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
        workflow_type: WorkflowTypeFilter = None,
    ) -> PaginatedResponse[WorkflowDefinition] | Response[ApiResponse[None]]:
        """List workflow definitions with optional filters."""
        parsed_type: WorkflowType | None = None
        if workflow_type is not None:
            try:
                parsed_type = WorkflowType(workflow_type)
            except ValueError:
                valid = ", ".join(e.value for e in WorkflowType)
                logger.warning(
                    WORKFLOW_DEF_INVALID_REQUEST,
                    field="workflow_type",
                    value=workflow_type,
                )
                return Response(
                    content=ApiResponse[None](
                        error=(
                            f"Invalid workflow type: {workflow_type!r}. Valid: {valid}"
                        ),
                    ),
                    status_code=400,
                )

        repo = state.app_state.persistence.workflow_definitions
        defs = await repo.list_definitions(workflow_type=parsed_type)
        page, meta = paginate(defs, offset=offset, limit=limit)
        return PaginatedResponse[WorkflowDefinition](
            data=page,
            pagination=meta,
        )

    @get("/blueprints", guards=[require_read_access])
    async def list_workflow_blueprints(
        self,
    ) -> Response[ApiResponse[tuple[BlueprintInfoResponse, ...]]]:
        """List available workflow blueprints."""
        import asyncio  # noqa: PLC0415

        infos = await asyncio.to_thread(list_blueprints)
        responses = tuple(
            BlueprintInfoResponse(
                name=i.name,
                display_name=i.display_name,
                description=i.description,
                source=i.source,
                tags=i.tags,
                workflow_type=i.workflow_type,
                node_count=i.node_count,
                edge_count=i.edge_count,
            )
            for i in infos
        )
        return Response(
            content=ApiResponse[tuple[BlueprintInfoResponse, ...]](
                data=responses,
            ),
        )

    @post("/from-blueprint", guards=[require_write_access])
    async def create_from_blueprint(
        self,
        request: Request[Any, Any, Any],
        state: State,
        data: CreateFromBlueprintRequest,
    ) -> Response[ApiResponse[WorkflowDefinition]]:
        """Create a new workflow definition from a blueprint."""
        import asyncio  # noqa: PLC0415

        auth_user = request.scope.get("user")
        creator = (
            auth_user.user_id if isinstance(auth_user, AuthenticatedUser) else "api"
        )
        logger.info(
            BLUEPRINT_INSTANTIATE_START,
            blueprint_name=data.blueprint_name,
        )

        try:
            bp = await asyncio.to_thread(load_blueprint, data.blueprint_name)
        except BlueprintNotFoundError as exc:
            logger.warning(
                BLUEPRINT_INSTANTIATE_FAILED,
                blueprint_name=data.blueprint_name,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Blueprint not found: {data.blueprint_name}",
                ),
                status_code=404,
            )
        except BlueprintValidationError as exc:
            logger.warning(
                BLUEPRINT_INSTANTIATE_FAILED,
                blueprint_name=data.blueprint_name,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Blueprint validation failed: {exc}",
                ),
                status_code=422,
            )

        now = datetime.now(UTC)
        nodes = tuple(
            WorkflowNode(
                id=n.id,
                type=n.type,
                label=n.label,
                position_x=n.position_x,
                position_y=n.position_y,
                config=dict(n.config),
            )
            for n in bp.nodes
        )
        edges = tuple(
            WorkflowEdge(
                id=e.id,
                source_node_id=e.source_node_id,
                target_node_id=e.target_node_id,
                type=e.type,
                label=e.label,
            )
            for e in bp.edges
        )

        definition = WorkflowDefinition(
            id=f"wfdef-{uuid.uuid4().hex[:12]}",
            name=data.name or bp.display_name,
            description=(
                data.description if data.description is not None else bp.description
            ),
            workflow_type=bp.workflow_type,
            nodes=nodes,
            edges=edges,
            created_by=creator,
            created_at=now,
            updated_at=now,
        )

        repo = state.app_state.persistence.workflow_definitions
        await repo.save(definition)
        logger.info(
            BLUEPRINT_INSTANTIATE_SUCCESS,
            definition_id=definition.id,
            blueprint_name=data.blueprint_name,
        )

        return Response(
            content=ApiResponse[WorkflowDefinition](data=definition),
            status_code=201,
        )

    @get("/{workflow_id:str}", guards=[require_read_access])
    async def get_workflow(
        self,
        state: State,
        workflow_id: PathId,
    ) -> Response[ApiResponse[WorkflowDefinition]]:
        """Get a workflow definition by ID."""
        repo = state.app_state.persistence.workflow_definitions
        definition = await repo.get(workflow_id)
        if definition is None:
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
        return Response(
            content=ApiResponse[WorkflowDefinition](data=definition),
        )

    @post(guards=[require_write_access])
    async def create_workflow(
        self,
        request: Request[Any, Any, Any],
        state: State,
        data: CreateWorkflowDefinitionRequest,
    ) -> Response[ApiResponse[WorkflowDefinition]]:
        """Create a new workflow definition."""
        auth_user = request.scope.get("user")
        creator = (
            auth_user.user_id if isinstance(auth_user, AuthenticatedUser) else "api"
        )
        now = datetime.now(UTC)
        try:
            nodes = tuple(WorkflowNode.model_validate(n) for n in data.nodes)
            edges = tuple(WorkflowEdge.model_validate(e) for e in data.edges)
            definition = WorkflowDefinition(
                id=f"wfdef-{uuid.uuid4().hex[:12]}",
                name=data.name,
                description=data.description,
                workflow_type=data.workflow_type,
                nodes=nodes,
                edges=edges,
                created_by=creator,
                created_at=now,
                updated_at=now,
            )
        except (ValueError, ValidationError) as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Invalid workflow definition: {exc}",
                ),
                status_code=422,
            )

        repo = state.app_state.persistence.workflow_definitions
        await repo.save(definition)

        # Auto-snapshot version.
        version_repo = state.app_state.persistence.workflow_versions
        snapshot = _build_version_snapshot(definition, creator)
        await version_repo.save_version(snapshot)

        logger.info(WORKFLOW_DEF_CREATED, definition_id=definition.id)

        return Response(
            content=ApiResponse[WorkflowDefinition](data=definition),
            status_code=201,
        )

    @patch("/{workflow_id:str}", guards=[require_write_access])
    async def update_workflow(
        self,
        request: Request[Any, Any, Any],
        state: State,
        workflow_id: PathId,
        data: UpdateWorkflowDefinitionRequest,
    ) -> Response[ApiResponse[WorkflowDefinition]]:
        """Update an existing workflow definition."""
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

        if (
            data.expected_version is not None
            and data.expected_version != existing.version
        ):
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

        result = _build_update_fields(data)
        if isinstance(result, Response):
            return result
        updates = result
        updates["version"] = existing.version + 1

        try:
            merged = existing.model_dump() | updates
            updated = WorkflowDefinition.model_validate(merged)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Invalid update: {exc}",
                ),
                status_code=422,
            )

        # Auto-snapshot version before saving.
        auth_user = request.scope.get("user")
        updater = (
            auth_user.user_id if isinstance(auth_user, AuthenticatedUser) else "api"
        )
        version_repo = state.app_state.persistence.workflow_versions
        snapshot = _build_version_snapshot(updated, updater)
        await version_repo.save_version(snapshot)

        try:
            await repo.save(updated)
        except VersionConflictError as exc:
            logger.warning(
                WORKFLOW_DEF_VERSION_CONFLICT,
                definition_id=updated.id,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Version conflict: {exc}",
                ),
                status_code=409,
            )
        logger.info(WORKFLOW_DEF_UPDATED, definition_id=updated.id)

        return Response(
            content=ApiResponse[WorkflowDefinition](data=updated),
        )

    @delete(
        "/{workflow_id:str}",
        guards=[require_write_access],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def delete_workflow(
        self,
        state: State,
        workflow_id: PathId,
    ) -> None:
        """Delete a workflow definition."""
        repo = state.app_state.persistence.workflow_definitions
        deleted = await repo.delete(workflow_id)
        if not deleted:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
            )
            msg = "Workflow definition not found"
            raise NotFoundError(msg)
        logger.info(
            WORKFLOW_DEF_DELETED,
            definition_id=workflow_id,
        )

    @post("/validate-draft", guards=[require_read_access], status_code=200)
    async def validate_draft(
        self,
        data: CreateWorkflowDefinitionRequest,
    ) -> Response[ApiResponse[WorkflowValidationResult]]:
        """Validate a draft workflow without persisting."""
        try:
            nodes = tuple(WorkflowNode.model_validate(n) for n in data.nodes)
            edges = tuple(WorkflowEdge.model_validate(e) for e in data.edges)
            definition = WorkflowDefinition(
                id="draft",
                name=data.name,
                description=data.description,
                workflow_type=data.workflow_type,
                nodes=nodes,
                edges=edges,
                created_by="draft",
            )
        except (ValueError, ValidationError) as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowValidationResult](
                    error=f"Invalid workflow: {exc}",
                ),
                status_code=422,
            )

        result = run_workflow_validation(definition)
        return Response(
            content=ApiResponse[WorkflowValidationResult](
                data=result,
            ),
        )

    @post("/{workflow_id:str}/validate", guards=[require_read_access], status_code=200)
    async def validate_workflow(
        self,
        state: State,
        workflow_id: PathId,
    ) -> Response[ApiResponse[WorkflowValidationResult]]:
        """Validate a workflow definition for execution readiness."""
        repo = state.app_state.persistence.workflow_definitions
        definition = await repo.get(workflow_id)
        if definition is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
            )
            return Response(
                content=ApiResponse[WorkflowValidationResult](
                    error="Workflow definition not found",
                ),
                status_code=404,
            )

        result = run_workflow_validation(definition)
        return Response(
            content=ApiResponse[WorkflowValidationResult](
                data=result,
            ),
        )

    @post("/{workflow_id:str}/export", guards=[require_read_access], status_code=200)
    async def export_workflow(
        self,
        state: State,
        workflow_id: PathId,
    ) -> Response[str] | Response[ApiResponse[None]]:
        """Export a workflow definition as YAML."""
        repo = state.app_state.persistence.workflow_definitions
        definition = await repo.get(workflow_id)
        if definition is None:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
            )
            return Response(
                content=ApiResponse[None](
                    error="Workflow definition not found",
                ),
                status_code=404,
            )

        try:
            yaml_str = export_workflow_yaml(definition)
        except ValueError as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                error=str(exc),
            )
            return Response(
                content=ApiResponse[None](
                    error=f"Export failed: {exc}",
                ),
                status_code=422,
            )

        return Response(
            content=yaml_str,
            media_type="text/yaml",
        )

    # ── Version history endpoints ──────────────────────────────

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
        # Versions are already paginated by the repo query, so pass
        # them through with pre-computed total for metadata.
        _, meta = paginate(versions, offset=offset, limit=limit, total=total)
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
        version_num: int,
    ) -> Response[ApiResponse[WorkflowDefinitionVersion]]:
        """Get a specific version snapshot."""
        version_repo = state.app_state.persistence.workflow_versions
        version = await version_repo.get_version(workflow_id, version_num)
        if version is None:
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
            return Response(
                content=ApiResponse[WorkflowDiff](
                    error="from_version and to_version must differ",
                ),
                status_code=400,
            )

        version_repo = state.app_state.persistence.workflow_versions
        old = await version_repo.get_version(workflow_id, from_version)
        if old is None:
            return Response(
                content=ApiResponse[WorkflowDiff](
                    error=f"Version {from_version} not found",
                ),
                status_code=404,
            )
        new = await version_repo.get_version(workflow_id, to_version)
        if new is None:
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

    @post("/{workflow_id:str}/rollback", guards=[require_write_access], status_code=200)
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
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Target version {data.target_version} not found",
                ),
                status_code=404,
            )

        auth_user = request.scope.get("user")
        updater = (
            auth_user.user_id if isinstance(auth_user, AuthenticatedUser) else "api"
        )
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

        snapshot = _build_version_snapshot(rolled_back, updater)
        await version_repo.save_version(snapshot)

        try:
            await repo.save(rolled_back)
        except VersionConflictError as exc:
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Version conflict during rollback: {exc}",
                ),
                status_code=409,
            )

        logger.info(
            WORKFLOW_DEF_ROLLED_BACK,
            definition_id=workflow_id,
            target_version=data.target_version,
            new_version=rolled_back.version,
        )
        return Response(
            content=ApiResponse[WorkflowDefinition](data=rolled_back),
        )
