"""Workflow controller builders -- blueprint loaders, update appliers.

Extracted from ``workflows.py`` to keep that controller focused on
the Litestar route handlers.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from litestar import Response
from pydantic import ValidationError

from synthorg.api.dto import ApiResponse
from synthorg.engine.workflow.blueprint_errors import (
    BlueprintNotFoundError,
    BlueprintValidationError,
)
from synthorg.engine.workflow.blueprint_loader import load_blueprint
from synthorg.engine.workflow.definition import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowIODeclaration,
    WorkflowNode,
)
from synthorg.engine.workflow.subworkflow_registry import SubworkflowRegistry
from synthorg.engine.workflow.validation import (
    validate_subworkflow_graph,
    validate_subworkflow_io,
)
from synthorg.observability import get_logger
from synthorg.observability.events.blueprint import BLUEPRINT_INSTANTIATE_FAILED
from synthorg.observability.events.workflow_definition import (
    WORKFLOW_DEF_INVALID_REQUEST,
    WORKFLOW_DEF_NOT_FOUND,
    WORKFLOW_DEF_VERSION_CONFLICT,
)
from synthorg.versioning import VersioningService

if TYPE_CHECKING:
    from litestar.datastructures import State

    from synthorg.api.dto import (
        CreateFromBlueprintRequest,
        UpdateWorkflowDefinitionRequest,
    )
    from synthorg.engine.workflow.blueprint_models import BlueprintData
    from synthorg.engine.workflow.validation import WorkflowValidationError
    from synthorg.persistence.workflow_definition_repo import (
        WorkflowDefinitionRepository,
    )

logger = get_logger(__name__)


def wf_versioning(state: State) -> VersioningService[WorkflowDefinition]:
    """Build a VersioningService for workflow definitions."""
    return VersioningService(state.app_state.persistence.workflow_versions)


async def run_subworkflow_validation(
    definition: WorkflowDefinition,
    state: State,
) -> tuple[WorkflowValidationError, ...]:
    """Run save-time subworkflow I/O + cycle validation."""
    registry = SubworkflowRegistry(state.app_state.persistence.subworkflows)
    io_result = await validate_subworkflow_io(definition, registry)
    graph_result = await validate_subworkflow_graph(definition, registry)
    return tuple(io_result.errors) + tuple(graph_result.errors)


def build_update_fields(  # noqa: C901, PLR0912
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
                    error="Invalid 'inputs' field in request.",
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
                    error="Invalid 'outputs' field in request.",
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


def build_definition_from_blueprint(
    bp: BlueprintData,
    data: CreateFromBlueprintRequest,
    creator: str,
    now: datetime,
) -> WorkflowDefinition:
    """Build a ``WorkflowDefinition`` from a loaded blueprint."""
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


def apply_update(
    existing: WorkflowDefinition,
    data: UpdateWorkflowDefinitionRequest,
) -> WorkflowDefinition | Response[ApiResponse[WorkflowDefinition]]:
    """Merge update fields into an existing definition and validate."""
    result = build_update_fields(data)
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


async def fetch_existing_for_update(
    repo: WorkflowDefinitionRepository,
    workflow_id: str,
    expected_revision: int | None,
) -> WorkflowDefinition | Response[ApiResponse[WorkflowDefinition]]:
    """Fetch a definition and check for revision conflicts before update."""
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


async def load_blueprint_or_error(
    blueprint_name: str,
) -> BlueprintData | Response[ApiResponse[WorkflowDefinition]]:
    """Load a blueprint by name, returning an error response on failure."""
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
