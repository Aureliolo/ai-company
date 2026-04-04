"""Workflow execution service -- activate definitions into tasks.

Bridges design-time ``WorkflowDefinition`` blueprints and
runtime ``Task`` instances by walking the graph in topological
order, creating concrete tasks for TASK nodes, and wiring
upstream task dependencies from the graph edges.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from synthorg.core.enums import (
    TaskStatus,
    WorkflowEdgeType,
    WorkflowExecutionStatus,
    WorkflowNodeExecutionStatus,
    WorkflowNodeType,
)
from synthorg.engine.errors import (
    WorkflowDefinitionInvalidError,
    WorkflowExecutionError,
    WorkflowExecutionNotFoundError,
)
from synthorg.engine.workflow.execution_activation_helpers import (
    find_downstream_task_ids,
    process_conditional_node,
    process_task_node,
)
from synthorg.engine.workflow.execution_models import (
    WorkflowExecution,
    WorkflowNodeExecution,
)
from synthorg.engine.workflow.graph_utils import (
    build_adjacency_maps,
    topological_sort,
)
from synthorg.engine.workflow.validation import validate_workflow
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_execution import (
    WORKFLOW_EXEC_ACTIVATED,
    WORKFLOW_EXEC_CANCELLED,
    WORKFLOW_EXEC_COMPLETED,
    WORKFLOW_EXEC_FAILED,
    WORKFLOW_EXEC_INVALID_DEFINITION,
    WORKFLOW_EXEC_INVALID_STATUS,
    WORKFLOW_EXEC_NODE_COMPLETED,
    WORKFLOW_EXEC_NODE_SKIPPED,
    WORKFLOW_EXEC_NODE_TASK_COMPLETED,
    WORKFLOW_EXEC_NODE_TASK_FAILED,
    WORKFLOW_EXEC_NOT_FOUND,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.engine.task_engine import TaskEngine
    from synthorg.engine.task_engine_models import TaskStateChanged
    from synthorg.engine.workflow.definition import (
        WorkflowDefinition,
        WorkflowNode,
    )
    from synthorg.persistence.workflow_definition_repo import (
        WorkflowDefinitionRepository,
    )
    from synthorg.persistence.workflow_execution_repo import (
        WorkflowExecutionRepository,
    )

logger = get_logger(__name__)

_TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
)


class WorkflowExecutionService:
    """Activates workflow definitions into concrete task instances.

    Walks the definition graph in topological order, creates
    ``Task`` instances for TASK nodes via the ``TaskEngine``,
    and tracks per-node execution state.

    Args:
        definition_repo: Repository for reading workflow definitions.
        execution_repo: Repository for persisting execution state.
        task_engine: Engine for creating concrete tasks.
    """

    def __init__(
        self,
        *,
        definition_repo: WorkflowDefinitionRepository,
        execution_repo: WorkflowExecutionRepository,
        task_engine: TaskEngine,
    ) -> None:
        self._definition_repo = definition_repo
        self._execution_repo = execution_repo
        self._task_engine = task_engine

    async def activate(
        self,
        definition_id: str,
        *,
        project: str,
        activated_by: str,
        context: Mapping[str, object] | None = None,
    ) -> WorkflowExecution:
        """Activate a workflow definition, creating task instances.

        Args:
            definition_id: ID of the workflow definition to activate.
            project: Project ID for all created tasks.
            activated_by: Identity of the user triggering activation.
            context: Runtime context for condition evaluation.

        Returns:
            The created ``WorkflowExecution`` in RUNNING status.

        Raises:
            WorkflowExecutionNotFoundError: If the definition is
                not found.
            WorkflowDefinitionInvalidError: If the definition fails
                validation.
            WorkflowConditionEvalError: If a condition expression
                cannot be evaluated.
            PersistenceError: If the execution cannot be persisted.
            WorkflowExecutionError: If an unhandled node type is
                encountered.
        """
        ctx = dict(context) if context else {}

        # 1. Load and validate
        definition = await self._load_and_validate(definition_id)

        # 2. Build graph structures
        adjacency, reverse_adj, outgoing = build_adjacency_maps(
            definition,
        )
        node_map = {n.id: n for n in definition.nodes}
        sorted_ids = topological_sort(
            [n.id for n in definition.nodes],
            adjacency,
        )

        # 3. Walk nodes in topological order
        execution_id = f"wfexec-{uuid4().hex[:12]}"
        now = datetime.now(UTC)
        node_exec_map, node_task_ids = await self._walk_nodes(
            sorted_ids=sorted_ids,
            node_map=node_map,
            adjacency=adjacency,
            reverse_adj=reverse_adj,
            outgoing=outgoing,
            ctx=ctx,
            execution_id=execution_id,
            project=project,
            activated_by=activated_by,
        )

        # 4. Build and persist execution
        # If no tasks were created, the workflow is immediately complete
        if node_task_ids:
            status = WorkflowExecutionStatus.RUNNING
            completed_at = None
        else:
            status = WorkflowExecutionStatus.COMPLETED
            completed_at = now

        execution = WorkflowExecution(
            id=execution_id,
            definition_id=definition.id,
            definition_version=definition.version,
            status=status,
            node_executions=tuple(node_exec_map[n.id] for n in definition.nodes),
            activated_by=activated_by,
            project=project,
            created_at=now,
            updated_at=now,
            completed_at=completed_at,
        )
        await self._execution_repo.save(execution)

        logger.info(
            WORKFLOW_EXEC_ACTIVATED,
            execution_id=execution_id,
            definition_id=definition.id,
            task_count=len(node_task_ids),
        )

        return execution

    async def _load_and_validate(
        self,
        definition_id: str,
    ) -> WorkflowDefinition:
        """Load a workflow definition and validate it.

        Raises:
            WorkflowExecutionNotFoundError: If not found.
            WorkflowDefinitionInvalidError: If invalid.
        """
        definition = await self._definition_repo.get(definition_id)
        if definition is None:
            logger.warning(
                WORKFLOW_EXEC_NOT_FOUND,
                definition_id=definition_id,
            )
            msg = f"Workflow definition {definition_id!r} not found"
            raise WorkflowExecutionNotFoundError(msg)

        validation = validate_workflow(definition)
        if not validation.valid:
            error_msgs = "; ".join(e.message for e in validation.errors)
            logger.warning(
                WORKFLOW_EXEC_INVALID_DEFINITION,
                definition_id=definition_id,
                errors=error_msgs,
            )
            msg = f"Workflow definition {definition_id!r} is invalid: {error_msgs}"
            raise WorkflowDefinitionInvalidError(msg)

        return definition

    async def _walk_nodes(  # noqa: PLR0913
        self,
        *,
        sorted_ids: list[str],
        node_map: dict[str, WorkflowNode],
        adjacency: dict[str, list[str]],
        reverse_adj: dict[str, list[str]],
        outgoing: dict[str, list[tuple[str, WorkflowEdgeType]]],
        ctx: dict[str, object],
        execution_id: str,
        project: str,
        activated_by: str,
    ) -> tuple[dict[str, WorkflowNodeExecution], dict[str, str]]:
        """Walk the graph in topological order, processing each node.

        Returns:
            A 2-tuple of (node_exec_map, node_task_ids).
        """
        node_exec_map: dict[str, WorkflowNodeExecution] = {}
        node_task_ids: dict[str, str] = {}
        skipped_nodes: set[str] = set()
        pending_assignments: dict[str, str] = {}

        for nid in sorted_ids:
            if nid in skipped_nodes:
                node_exec_map[nid] = WorkflowNodeExecution(
                    node_id=nid,
                    node_type=node_map[nid].type,
                    status=WorkflowNodeExecutionStatus.SKIPPED,
                    skipped_reason="Conditional branch not taken",
                )
                logger.debug(
                    WORKFLOW_EXEC_NODE_SKIPPED,
                    execution_id=execution_id,
                    node_id=nid,
                )
                continue

            node = node_map[nid]
            node_exec_map[nid] = await self._process_node(
                nid=nid,
                node=node,
                adjacency=adjacency,
                reverse_adj=reverse_adj,
                outgoing=outgoing,
                ctx=ctx,
                execution_id=execution_id,
                project=project,
                activated_by=activated_by,
                node_map=node_map,
                node_task_ids=node_task_ids,
                skipped_nodes=skipped_nodes,
                pending_assignments=pending_assignments,
            )

        return node_exec_map, node_task_ids

    async def _process_node(  # noqa: PLR0913
        self,
        *,
        nid: str,
        node: WorkflowNode,
        adjacency: dict[str, list[str]],
        reverse_adj: dict[str, list[str]],
        outgoing: dict[str, list[tuple[str, WorkflowEdgeType]]],
        ctx: dict[str, object],
        execution_id: str,
        project: str,
        activated_by: str,
        node_map: dict[str, WorkflowNode],
        node_task_ids: dict[str, str],
        skipped_nodes: set[str],
        pending_assignments: dict[str, str],
    ) -> WorkflowNodeExecution:
        """Dispatch a single node to the appropriate handler."""
        if node.type in {
            WorkflowNodeType.START,
            WorkflowNodeType.END,
            WorkflowNodeType.PARALLEL_SPLIT,
            WorkflowNodeType.PARALLEL_JOIN,
        }:
            logger.debug(
                WORKFLOW_EXEC_NODE_COMPLETED,
                execution_id=execution_id,
                node_id=nid,
                node_type=node.type.value,
            )
            return WorkflowNodeExecution(
                node_id=nid,
                node_type=node.type,
                status=WorkflowNodeExecutionStatus.COMPLETED,
            )

        if node.type is WorkflowNodeType.AGENT_ASSIGNMENT:
            agent_name = node.config.get("agent_name")
            if agent_name:
                task_targets = find_downstream_task_ids(
                    nid,
                    adjacency,
                    node_map,
                )
                for target_id in task_targets:
                    pending_assignments[target_id] = str(agent_name)
            else:
                logger.warning(
                    WORKFLOW_EXEC_NODE_COMPLETED,
                    execution_id=execution_id,
                    node_id=nid,
                    note="AGENT_ASSIGNMENT node has no agent_name",
                )
            logger.debug(
                WORKFLOW_EXEC_NODE_COMPLETED,
                execution_id=execution_id,
                node_id=nid,
                node_type=node.type.value,
            )
            return WorkflowNodeExecution(
                node_id=nid,
                node_type=node.type,
                status=WorkflowNodeExecutionStatus.COMPLETED,
            )

        if node.type is WorkflowNodeType.CONDITIONAL:
            return process_conditional_node(
                nid,
                node,
                ctx,
                outgoing,
                adjacency,
                skipped_nodes,
                execution_id,
            )

        if node.type is not WorkflowNodeType.TASK:
            msg = f"Unhandled node type {node.type.value!r} for node {nid!r}"
            logger.error(
                WORKFLOW_EXEC_NODE_COMPLETED,
                execution_id=execution_id,
                node_id=nid,
                node_type=node.type.value,
                error=msg,
            )
            raise WorkflowExecutionError(msg)

        return await process_task_node(
            nid,
            node,
            reverse_adj=reverse_adj,
            node_map=node_map,
            node_task_ids=node_task_ids,
            skipped_nodes=skipped_nodes,
            pending_assignments=pending_assignments,
            project=project,
            activated_by=activated_by,
            task_engine=self._task_engine,
            execution_id=execution_id,
        )

    async def get_execution(
        self,
        execution_id: str,
    ) -> WorkflowExecution | None:
        """Retrieve a workflow execution by ID.

        Args:
            execution_id: The execution identifier.

        Returns:
            The execution, or ``None`` if not found.
        """
        return await self._execution_repo.get(execution_id)

    async def list_executions(
        self,
        definition_id: str,
    ) -> tuple[WorkflowExecution, ...]:
        """List executions for a workflow definition.

        Args:
            definition_id: The source definition identifier.

        Returns:
            Matching executions as a tuple.
        """
        return await self._execution_repo.list_by_definition(definition_id)

    async def cancel_execution(
        self,
        execution_id: str,
        *,
        cancelled_by: str,
    ) -> WorkflowExecution:
        """Cancel a workflow execution.

        Args:
            execution_id: The execution identifier.
            cancelled_by: Identity of the user cancelling.

        Returns:
            The updated execution in CANCELLED status.

        Raises:
            WorkflowExecutionNotFoundError: If not found.
            WorkflowExecutionError: If execution is already terminal.
        """
        execution = await self._execution_repo.get(execution_id)
        if execution is None:
            logger.warning(
                WORKFLOW_EXEC_NOT_FOUND,
                execution_id=execution_id,
            )
            msg = f"Workflow execution {execution_id!r} not found"
            raise WorkflowExecutionNotFoundError(msg)

        terminal_statuses = {
            WorkflowExecutionStatus.COMPLETED,
            WorkflowExecutionStatus.FAILED,
            WorkflowExecutionStatus.CANCELLED,
        }
        if execution.status in terminal_statuses:
            msg = (
                f"Cannot cancel execution {execution_id!r}"
                f" in terminal status {execution.status.value!r}"
            )
            logger.warning(
                WORKFLOW_EXEC_CANCELLED,
                execution_id=execution_id,
                error=msg,
            )
            raise WorkflowExecutionError(msg)

        now = datetime.now(UTC)
        cancelled = execution.model_copy(
            update={
                "status": WorkflowExecutionStatus.CANCELLED,
                "updated_at": now,
                "completed_at": now,
                "version": execution.version + 1,
            }
        )
        await self._execution_repo.save(cancelled)

        logger.info(
            WORKFLOW_EXEC_CANCELLED,
            execution_id=execution_id,
            cancelled_by=cancelled_by,
        )

        return cancelled

    # -- Lifecycle transitions ---------------------------------------------

    async def complete_execution(
        self,
        execution_id: str,
    ) -> WorkflowExecution:
        """Transition a running execution to COMPLETED.

        Args:
            execution_id: The execution identifier.

        Returns:
            The updated execution in COMPLETED status.

        Raises:
            WorkflowExecutionNotFoundError: If not found.
            WorkflowExecutionError: If execution is not RUNNING.
        """
        execution = await self._load_running(execution_id)
        now = datetime.now(UTC)
        completed = execution.model_copy(
            update={
                "status": WorkflowExecutionStatus.COMPLETED,
                "updated_at": now,
                "completed_at": now,
                "version": execution.version + 1,
            },
        )
        await self._execution_repo.save(completed)
        logger.info(
            WORKFLOW_EXEC_COMPLETED,
            execution_id=execution_id,
        )
        return completed

    async def fail_execution(
        self,
        execution_id: str,
        *,
        error: str,
    ) -> WorkflowExecution:
        """Transition a running execution to FAILED.

        Args:
            execution_id: The execution identifier.
            error: Error message describing the failure.

        Returns:
            The updated execution in FAILED status.

        Raises:
            WorkflowExecutionNotFoundError: If not found.
            WorkflowExecutionError: If execution is not RUNNING.
        """
        execution = await self._load_running(execution_id)
        now = datetime.now(UTC)
        failed = execution.model_copy(
            update={
                "status": WorkflowExecutionStatus.FAILED,
                "error": error,
                "updated_at": now,
                "completed_at": now,
                "version": execution.version + 1,
            },
        )
        await self._execution_repo.save(failed)
        logger.info(
            WORKFLOW_EXEC_FAILED,
            execution_id=execution_id,
            error=error,
        )
        return failed

    async def handle_task_state_changed(
        self,
        event: TaskStateChanged,
    ) -> None:
        """React to a task state change from the TaskEngine.

        Correlates the task to a running workflow execution and
        transitions the execution to COMPLETED or FAILED as
        appropriate.  Task cancellations are treated as failures
        at the workflow level.  Silently ignores events for tasks
        not belonging to any running execution.

        Node status update and execution-level transition are
        combined into a single save to avoid version conflicts.

        Args:
            event: The task state change event.
        """
        if event.mutation_type != "transition":
            return
        if event.new_status not in _TERMINAL_TASK_STATUSES:
            return

        execution = await self._find_execution_by_task(event.task_id)
        if execution is None:
            return

        if event.new_status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            await self._handle_task_failed(execution, event)
        else:
            await self._handle_task_completed(execution, event)

    async def _handle_task_failed(
        self,
        execution: WorkflowExecution,
        event: TaskStateChanged,
    ) -> None:
        """Handle a task failure or cancellation event.

        Updates the node to TASK_FAILED and transitions the
        execution to FAILED in a single repository save.
        """
        updated = _update_node_status(
            execution,
            event.task_id,
            WorkflowNodeExecutionStatus.TASK_FAILED,
        )
        now = datetime.now(UTC)
        verb = "cancelled" if event.new_status is TaskStatus.CANCELLED else "failed"
        error_msg = f"Task {event.task_id} {verb}"
        # Combine node update + execution terminal status in one save
        # (version already bumped by _update_node_status)
        failed = updated.model_copy(
            update={
                "status": WorkflowExecutionStatus.FAILED,
                "error": error_msg,
                "updated_at": now,
                "completed_at": now,
            },
        )
        await self._execution_repo.save(failed)
        logger.info(
            WORKFLOW_EXEC_NODE_TASK_FAILED,
            execution_id=execution.id,
            task_id=event.task_id,
        )
        logger.info(
            WORKFLOW_EXEC_FAILED,
            execution_id=execution.id,
            error=error_msg,
        )

    async def _handle_task_completed(
        self,
        execution: WorkflowExecution,
        event: TaskStateChanged,
    ) -> None:
        """Handle a task completion event.

        Updates the node to TASK_COMPLETED. If all task nodes are
        now complete, transitions the execution to COMPLETED in
        a single save.
        """
        updated = _update_node_status(
            execution,
            event.task_id,
            WorkflowNodeExecutionStatus.TASK_COMPLETED,
        )
        logger.info(
            WORKFLOW_EXEC_NODE_TASK_COMPLETED,
            execution_id=execution.id,
            task_id=event.task_id,
        )
        if _all_tasks_completed(updated):
            now = datetime.now(UTC)
            # Combine node update + execution terminal status in one save
            # (version already bumped by _update_node_status)
            completed = updated.model_copy(
                update={
                    "status": WorkflowExecutionStatus.COMPLETED,
                    "updated_at": now,
                    "completed_at": now,
                },
            )
            await self._execution_repo.save(completed)
            logger.info(
                WORKFLOW_EXEC_COMPLETED,
                execution_id=execution.id,
            )
        else:
            await self._execution_repo.save(updated)

    # -- Private helpers ---------------------------------------------------

    async def _load_running(
        self,
        execution_id: str,
    ) -> WorkflowExecution:
        """Load an execution and validate it is RUNNING.

        Raises:
            WorkflowExecutionNotFoundError: If not found.
            WorkflowExecutionError: If not in RUNNING status.
        """
        execution = await self._execution_repo.get(execution_id)
        if execution is None:
            logger.warning(
                WORKFLOW_EXEC_NOT_FOUND,
                execution_id=execution_id,
            )
            msg = f"Workflow execution {execution_id!r} not found"
            raise WorkflowExecutionNotFoundError(msg)

        if execution.status is not WorkflowExecutionStatus.RUNNING:
            msg = (
                f"Cannot transition execution {execution_id!r}"
                f" in status {execution.status.value!r}"
                " (expected 'running')"
            )
            logger.warning(
                WORKFLOW_EXEC_INVALID_STATUS,
                execution_id=execution_id,
                current_status=execution.status.value,
                error=msg,
            )
            raise WorkflowExecutionError(msg)

        return execution

    async def _find_execution_by_task(
        self,
        task_id: str,
    ) -> WorkflowExecution | None:
        """Find a RUNNING execution containing a node with the task ID."""
        return await self._execution_repo.find_by_task_id(task_id)


def _update_node_status(
    execution: WorkflowExecution,
    task_id: str,
    new_status: WorkflowNodeExecutionStatus,
) -> WorkflowExecution:
    """Return a copy with one node's status updated.

    Args:
        execution: The source execution (not mutated).
        task_id: Task ID of the node to update.
        new_status: New status for the matching node.

    Returns:
        A new ``WorkflowExecution`` with the updated node and
        bumped ``version`` / ``updated_at``.

    Raises:
        ValueError: If no node matches the given task_id.
    """
    found = False
    updated_nodes: list[WorkflowNodeExecution] = []
    for ne in execution.node_executions:
        if ne.task_id == task_id:
            updated_nodes.append(ne.model_copy(update={"status": new_status}))
            found = True
        else:
            updated_nodes.append(ne)

    if not found:
        msg = f"task_id {task_id!r} not found in execution {execution.id!r}"
        logger.warning(
            WORKFLOW_EXEC_NOT_FOUND,
            execution_id=execution.id,
            task_id=task_id,
            error=msg,
        )
        raise ValueError(msg)

    return execution.model_copy(
        update={
            "node_executions": tuple(updated_nodes),
            "updated_at": datetime.now(UTC),
            "version": execution.version + 1,
        },
    )


def _all_tasks_completed(execution: WorkflowExecution) -> bool:
    """Check if all non-skipped TASK nodes have completed."""
    for ne in execution.node_executions:
        if ne.node_type is not WorkflowNodeType.TASK:
            continue
        if ne.status is WorkflowNodeExecutionStatus.SKIPPED:
            continue
        if ne.status is not WorkflowNodeExecutionStatus.TASK_COMPLETED:
            return False
    return True
