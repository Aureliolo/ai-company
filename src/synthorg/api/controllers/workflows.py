"""Workflow definition controller -- CRUD, validation, and YAML export."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from litestar import Controller, Request, Response, delete, get, patch, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter
from litestar.status_codes import HTTP_204_NO_CONTENT
from pydantic import ValidationError

from synthorg.api.controllers._workflow_helpers import get_auth_user_id
from synthorg.api.dto import (
    ApiResponse,
    BlueprintInfoResponse,
    CreateFromBlueprintRequest,
    CreateWorkflowDefinitionRequest,
    PaginatedResponse,
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
from synthorg.engine.workflow.blueprint_models import BlueprintData  # noqa: TC001
from synthorg.engine.workflow.definition import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowIODeclaration,
    WorkflowNode,
)
from synthorg.engine.workflow.subworkflow_registry import SubworkflowRegistry
from synthorg.engine.workflow.validation import (
    WorkflowValidationError,
    WorkflowValidationResult,
    validate_subworkflow_graph,
    validate_subworkflow_io,
)
from synthorg.engine.workflow.validation import (
    validate_workflow as run_workflow_validation,
)
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
    WORKFLOW_DEF_INVALID_REQUEST,
    WORKFLOW_DEF_NOT_FOUND,
    WORKFLOW_DEF_UPDATED,
    WORKFLOW_DEF_VERSION_CONFLICT,
)
from synthorg.observability.events.workflow_version import (
    WORKFLOW_VERSION_SNAPSHOT_FAILED,
)
from synthorg.persistence.errors import (
    PersistenceError,
    VersionConflictError,
)
from synthorg.persistence.workflow_definition_repo import (
    WorkflowDefinitionRepository,  # noqa: TC001
)
from synthorg.versioning import VersioningService


def _wf_versioning(state: State) -> VersioningService[WorkflowDefinition]:
    """Build a VersioningService for workflow definitions.

    ``VersioningService.__init__`` only stores a repo reference, so
    constructing per-request is trivially cheap.
    """
    return VersioningService(state.app_state.persistence.workflow_versions)


logger = get_logger(__name__)


async def _run_subworkflow_validation(
    definition: WorkflowDefinition,
    state: State,
) -> tuple[WorkflowValidationError, ...]:
    """Run save-time subworkflow I/O + cycle validation.

    Returns the combined tuple of validation errors; empty when
    the definition is subworkflow-clean.  Never raises for individual
    validation errors -- those are returned as structured errors so
    callers can map to 400 responses.
    """
    registry = SubworkflowRegistry(state.app_state.persistence.subworkflows)
    io_result = await validate_subworkflow_io(definition, registry)
    graph_result = await validate_subworkflow_graph(definition, registry)
    return tuple(io_result.errors) + tuple(graph_result.errors)


def _build_update_fields(  # noqa: C901, PLR0912
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
    if data.version is not None:
        updates["version"] = data.version
    if data.is_subworkflow is not None:
        updates["is_subworkflow"] = data.is_subworkflow
    if data.inputs is not None:
        try:
            updates["inputs"] = tuple(
                WorkflowIODeclaration.model_validate(i) for i in data.inputs
            )
        except (ValueError, ValidationError) as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                field="inputs",
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Invalid inputs: {exc}",
                ),
                status_code=422,
            )
    if data.outputs is not None:
        try:
            updates["outputs"] = tuple(
                WorkflowIODeclaration.model_validate(o) for o in data.outputs
            )
        except (ValueError, ValidationError) as exc:
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                field="outputs",
                error=str(exc),
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Invalid outputs: {exc}",
                ),
                status_code=422,
            )
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


def _nodes_from_blueprint(
    bp: BlueprintData,
) -> tuple[WorkflowNode, ...]:
    """Convert blueprint nodes to workflow nodes."""
    return tuple(
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


def _edges_from_blueprint(
    bp: BlueprintData,
) -> tuple[WorkflowEdge, ...]:
    """Convert blueprint edges to workflow edges."""
    return tuple(
        WorkflowEdge(
            id=e.id,
            source_node_id=e.source_node_id,
            target_node_id=e.target_node_id,
            type=e.type,
            label=e.label,
        )
        for e in bp.edges
    )


def _build_definition_from_blueprint(
    bp: BlueprintData,
    data: CreateFromBlueprintRequest,
    creator: str,
    now: datetime,
) -> WorkflowDefinition:
    """Build a ``WorkflowDefinition`` from a loaded blueprint.

    Args:
        bp: The loaded blueprint data.
        data: The creation request (may override name/description).
        creator: Authenticated user ID.
        now: Current UTC timestamp.

    Returns:
        A new ``WorkflowDefinition`` ready to persist.
    """
    return WorkflowDefinition(
        id=f"wfdef-{uuid.uuid4().hex[:12]}",
        name=data.name or bp.display_name,
        description=(
            data.description if data.description is not None else bp.description
        ),
        workflow_type=bp.workflow_type,
        nodes=_nodes_from_blueprint(bp),
        edges=_edges_from_blueprint(bp),
        created_by=creator,
        created_at=now,
        updated_at=now,
    )


def _apply_update(
    existing: WorkflowDefinition,
    data: UpdateWorkflowDefinitionRequest,
) -> WorkflowDefinition | Response[ApiResponse[WorkflowDefinition]]:
    """Merge update fields into an existing definition and validate.

    Builds the update dict, bumps the revision, and validates the merged
    model. Returns the updated definition on success or an error
    ``Response`` on validation failure or field-level errors.

    Args:
        existing: The current persisted definition.
        data: The partial-update request payload.

    Returns:
        The validated ``WorkflowDefinition``, or an error ``Response``.
    """
    result = _build_update_fields(data)
    if isinstance(result, Response):
        return result
    updates = result
    updates["revision"] = existing.revision + 1

    try:
        merged = existing.model_dump() | updates
        return WorkflowDefinition.model_validate(merged)
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


async def _fetch_existing_for_update(
    repo: WorkflowDefinitionRepository,
    workflow_id: str,
    expected_revision: int | None,
) -> WorkflowDefinition | Response[ApiResponse[WorkflowDefinition]]:
    """Fetch a definition and check for revision conflicts before update.

    Args:
        repo: The workflow definition repository.
        workflow_id: The workflow definition ID.
        expected_revision: Client-supplied expected revision (``None``
            to skip the optimistic concurrency check).

    Returns:
        The existing ``WorkflowDefinition``, or a ``Response`` error.
    """
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

    if expected_revision is not None and expected_revision != existing.revision:
        logger.warning(
            WORKFLOW_DEF_VERSION_CONFLICT,
            definition_id=workflow_id,
            expected=expected_revision,
            actual=existing.revision,
        )
        return Response(
            content=ApiResponse[WorkflowDefinition](
                error="Version conflict: the workflow was modified. Reload and retry.",
            ),
            status_code=409,
        )

    return existing


async def _load_blueprint_or_error(
    blueprint_name: str,
) -> BlueprintData | Response[ApiResponse[WorkflowDefinition]]:
    """Load a blueprint by name, returning an error response on failure.

    Args:
        blueprint_name: The blueprint identifier.

    Returns:
        The loaded ``BlueprintData``, or a ``Response`` error if the
        blueprint is not found or fails validation.
    """
    try:
        return await asyncio.to_thread(load_blueprint, blueprint_name)
    except BlueprintNotFoundError as exc:
        logger.warning(
            BLUEPRINT_INSTANTIATE_FAILED,
            blueprint_name=blueprint_name,
            error=str(exc),
        )
        return Response(
            content=ApiResponse[WorkflowDefinition](
                error=f"Blueprint not found: {blueprint_name}",
            ),
            status_code=404,
        )
    except BlueprintValidationError as exc:
        logger.warning(
            BLUEPRINT_INSTANTIATE_FAILED,
            blueprint_name=blueprint_name,
            error=str(exc),
        )
        return Response(
            content=ApiResponse[WorkflowDefinition](
                error="Blueprint validation failed",
            ),
            status_code=422,
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
        infos = await asyncio.to_thread(list_blueprints)
        responses = tuple(
            BlueprintInfoResponse(
                name=i.name,
                display_name=i.display_name,
                description=i.description,
                source=i.source,
                tags=i.tags,
                workflow_type=WorkflowType(i.workflow_type),
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
        creator = get_auth_user_id(request)
        logger.info(
            BLUEPRINT_INSTANTIATE_START,
            blueprint_name=data.blueprint_name,
        )

        result = await _load_blueprint_or_error(data.blueprint_name)
        if isinstance(result, Response):
            return result
        bp = result

        now = datetime.now(UTC)
        definition = _build_definition_from_blueprint(
            bp,
            data,
            creator,
            now,
        )

        repo = state.app_state.persistence.workflow_definitions
        await repo.save(definition)

        svc = _wf_versioning(state)
        try:
            await svc.snapshot_if_changed(
                entity_id=definition.id,
                snapshot=definition,
                saved_by=creator,
            )
        except PersistenceError:
            logger.exception(
                WORKFLOW_VERSION_SNAPSHOT_FAILED,
                definition_id=definition.id,
                revision=definition.revision,
            )

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
        creator = get_auth_user_id(request)
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

        subworkflow_errors = await _run_subworkflow_validation(definition, state)
        if subworkflow_errors:
            messages = "; ".join(e.message for e in subworkflow_errors)
            logger.warning(
                WORKFLOW_DEF_INVALID_REQUEST,
                error=messages,
            )
            return Response(
                content=ApiResponse[WorkflowDefinition](
                    error=f"Subworkflow validation failed: {messages}",
                ),
                status_code=422,
            )

        repo = state.app_state.persistence.workflow_definitions
        await repo.save(definition)

        svc = _wf_versioning(state)
        try:
            await svc.snapshot_if_changed(
                entity_id=definition.id,
                snapshot=definition,
                saved_by=creator,
            )
        except PersistenceError:
            logger.exception(
                WORKFLOW_VERSION_SNAPSHOT_FAILED,
                definition_id=definition.id,
                revision=definition.revision,
            )

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
        fetch_result = await _fetch_existing_for_update(
            repo,
            workflow_id,
            data.expected_revision,
        )
        if isinstance(fetch_result, Response):
            return fetch_result
        existing = fetch_result

        update_result = _apply_update(existing, data)
        if isinstance(update_result, Response):
            return update_result
        updated = update_result

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

        updater = get_auth_user_id(request)
        svc = _wf_versioning(state)
        try:
            await svc.snapshot_if_changed(
                entity_id=updated.id,
                snapshot=updated,
                saved_by=updater,
            )
        except PersistenceError:
            logger.exception(
                WORKFLOW_VERSION_SNAPSHOT_FAILED,
                definition_id=updated.id,
                revision=updated.revision,
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
        """Delete a workflow definition and its version history."""
        repo = state.app_state.persistence.workflow_definitions
        deleted = await repo.delete(workflow_id)
        if not deleted:
            logger.warning(
                WORKFLOW_DEF_NOT_FOUND,
                definition_id=workflow_id,
            )
            msg = "Workflow definition not found"
            raise NotFoundError(msg)
        # Defense-in-depth: explicit delete ensures cleanup even if
        # foreign keys are disabled.  Best-effort -- version cleanup
        # failure must not mask the successful primary delete.
        try:
            version_repo = state.app_state.persistence.workflow_versions
            await version_repo.delete_versions_for_entity(workflow_id)
        except PersistenceError:
            logger.warning(
                WORKFLOW_VERSION_SNAPSHOT_FAILED,
                definition_id=workflow_id,
                reason="version_cleanup_failed",
            )
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
