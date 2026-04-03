"""Workflow execution controller -- activate, list, get, cancel."""

from typing import Any

from litestar import Controller, Request, Response, get, post
from litestar.datastructures import State  # noqa: TC002

from synthorg.api.dto import (
    ActivateWorkflowRequest,
    ApiResponse,
)
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.path_params import PathId  # noqa: TC001
from synthorg.engine.errors import (
    WorkflowConditionEvalError,
    WorkflowDefinitionInvalidError,
    WorkflowExecutionNotFoundError,
)
from synthorg.engine.workflow.execution_models import WorkflowExecution
from synthorg.engine.workflow.execution_service import WorkflowExecutionService
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_execution import (
    WORKFLOW_EXEC_NOT_FOUND,
)

logger = get_logger(__name__)


def _build_service(state: State) -> WorkflowExecutionService:
    """Construct a WorkflowExecutionService from app state."""
    app_state = state.app_state
    return WorkflowExecutionService(
        definition_repo=app_state.persistence.workflow_definitions,
        execution_repo=app_state.persistence.workflow_executions,
        task_engine=app_state.task_engine,
    )


class WorkflowExecutionController(Controller):
    """Activate, list, get, and cancel workflow executions."""

    path = "/workflow-executions"
    tags = ("workflow-executions",)

    @post(
        "/activate/{workflow_id:str}",
        guards=[require_write_access],
        status_code=201,
    )
    async def activate_workflow(
        self,
        request: Request[Any, Any, Any],
        state: State,
        workflow_id: PathId,
        data: ActivateWorkflowRequest,
    ) -> Response[ApiResponse[WorkflowExecution]]:
        """Activate a workflow definition, creating task instances."""
        user = getattr(request, "user", None)
        activated_by = user.username if user and hasattr(user, "username") else "api"

        service = _build_service(state)
        try:
            execution = await service.activate(
                workflow_id,
                project=data.project,
                activated_by=activated_by,
                context=data.context,
            )
        except WorkflowExecutionNotFoundError:
            msg = f"Workflow definition {workflow_id!r} not found"
            raise NotFoundError(msg) from None
        except WorkflowDefinitionInvalidError as exc:
            return Response(
                content=ApiResponse[WorkflowExecution](error=str(exc)),
                status_code=422,
            )
        except WorkflowConditionEvalError as exc:
            return Response(
                content=ApiResponse[WorkflowExecution](error=str(exc)),
                status_code=422,
            )

        return Response(
            content=ApiResponse[WorkflowExecution](data=execution),
            status_code=201,
        )

    @get(
        "/by-definition/{workflow_id:str}",
        guards=[require_read_access],
    )
    async def list_executions(
        self,
        state: State,
        workflow_id: PathId,
    ) -> Response[ApiResponse[list[WorkflowExecution]]]:
        """List executions for a workflow definition."""
        service = _build_service(state)
        executions = await service.list_executions(workflow_id)
        return Response(
            content=ApiResponse[list[WorkflowExecution]](
                data=list(executions),
            ),
        )

    @get(
        "/{execution_id:str}",
        guards=[require_read_access],
    )
    async def get_execution(
        self,
        state: State,
        execution_id: PathId,
    ) -> Response[ApiResponse[WorkflowExecution]]:
        """Get a specific workflow execution."""
        service = _build_service(state)
        execution = await service.get_execution(execution_id)
        if execution is None:
            logger.warning(
                WORKFLOW_EXEC_NOT_FOUND,
                execution_id=execution_id,
            )
            msg = f"Workflow execution {execution_id!r} not found"
            raise NotFoundError(msg)

        return Response(
            content=ApiResponse[WorkflowExecution](data=execution),
        )

    @post(
        "/{execution_id:str}/cancel",
        guards=[require_write_access],
    )
    async def cancel_execution(
        self,
        state: State,
        execution_id: PathId,
    ) -> Response[ApiResponse[WorkflowExecution]]:
        """Cancel a workflow execution."""
        service = _build_service(state)
        try:
            execution = await service.cancel_execution(
                execution_id,
                cancelled_by="api",
            )
        except WorkflowExecutionNotFoundError:
            msg = f"Workflow execution {execution_id!r} not found"
            raise NotFoundError(msg) from None

        return Response(
            content=ApiResponse[WorkflowExecution](data=execution),
        )
