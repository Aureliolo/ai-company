"""Workflow execution service -- activate definitions into tasks.

Bridges design-time ``WorkflowDefinition`` blueprints and
runtime ``Task`` instances by walking the graph in topological
order, creating concrete tasks for TASK nodes, and wiring
upstream task dependencies from the graph edges.
"""

from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from synthorg.core.enums import (
    Complexity,
    Priority,
    TaskType,
    WorkflowEdgeType,
    WorkflowExecutionStatus,
    WorkflowNodeExecutionStatus,
    WorkflowNodeType,
)
from synthorg.engine.errors import (
    WorkflowConditionEvalError,
    WorkflowDefinitionInvalidError,
    WorkflowExecutionError,
    WorkflowExecutionNotFoundError,
)
from synthorg.engine.task_engine_models import CreateTaskData
from synthorg.engine.workflow.condition_eval import evaluate_condition
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
    WORKFLOW_EXEC_CONDITION_EVAL_FAILED,
    WORKFLOW_EXEC_CONDITION_EVALUATED,
    WORKFLOW_EXEC_INVALID_DEFINITION,
    WORKFLOW_EXEC_NODE_COMPLETED,
    WORKFLOW_EXEC_NODE_SKIPPED,
    WORKFLOW_EXEC_NOT_FOUND,
    WORKFLOW_EXEC_TASK_CREATED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.engine.task_engine import TaskEngine
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

_TASK_TYPE_MAP: dict[str, TaskType] = {t.value: t for t in TaskType}
_PRIORITY_MAP: dict[str, Priority] = {p.value: p for p in Priority}
_COMPLEXITY_MAP: dict[str, Complexity] = {c.value: c for c in Complexity}

# Node types that produce no concrete task (control flow and metadata)
_CONTROL_NODE_TYPES = frozenset(
    {
        WorkflowNodeType.START,
        WorkflowNodeType.END,
        WorkflowNodeType.AGENT_ASSIGNMENT,
        WorkflowNodeType.CONDITIONAL,
        WorkflowNodeType.PARALLEL_SPLIT,
        WorkflowNodeType.PARALLEL_JOIN,
    }
)


def _find_upstream_task_ids(
    node_id: str,
    reverse_adj: dict[str, list[str]],
    node_map: dict[str, WorkflowNode],
    node_task_ids: dict[str, str],
    skipped: set[str],
) -> tuple[str, ...]:
    """Walk backwards to find the nearest upstream TASK node task IDs.

    Skips through control nodes (START, END, AGENT_ASSIGNMENT,
    CONDITIONAL, PARALLEL_SPLIT, PARALLEL_JOIN) to find the actual
    TASK predecessors.  Skipped nodes are excluded entirely.
    TASK nodes that have not yet produced a task ID (not in
    ``node_task_ids``) are also excluded.
    """
    result: list[str] = []
    visited: set[str] = set()
    queue: deque[str] = deque(reverse_adj.get(node_id, []))

    while queue:
        pred_id = queue.popleft()
        if pred_id in visited or pred_id in skipped:
            continue
        visited.add(pred_id)
        pred_node = node_map[pred_id]
        if pred_node.type is WorkflowNodeType.TASK and pred_id in node_task_ids:
            result.append(node_task_ids[pred_id])
        elif pred_node.type in _CONTROL_NODE_TYPES:
            # Keep walking backwards through control nodes
            queue.extend(reverse_adj.get(pred_id, []))

    return tuple(sorted(set(result)))


def _find_skipped_nodes(
    untaken_target: str,
    taken_target: str,
    adjacency: dict[str, list[str]],
) -> set[str]:
    """Find nodes reachable only through the untaken branch.

    BFS from the untaken target, collecting all downstream nodes
    that are NOT reachable from the taken target.
    """
    # Find all nodes reachable from the taken branch
    taken_reachable: set[str] = set()
    queue: deque[str] = deque([taken_target])
    while queue:
        nid = queue.popleft()
        if nid in taken_reachable:
            continue
        taken_reachable.add(nid)
        queue.extend(adjacency.get(nid, []))

    # BFS from untaken target, skip nodes in taken_reachable
    skipped: set[str] = set()
    queue = deque([untaken_target])
    while queue:
        nid = queue.popleft()
        if nid in skipped or nid in taken_reachable:
            continue
        skipped.add(nid)
        queue.extend(adjacency.get(nid, []))

    return skipped


def _process_conditional_node(  # noqa: PLR0913
    nid: str,
    node: WorkflowNode,
    ctx: dict[str, object],
    outgoing: dict[str, list[tuple[str, WorkflowEdgeType]]],
    adjacency: dict[str, list[str]],
    skipped_nodes: set[str],
    execution_id: str,
) -> WorkflowNodeExecution:
    """Evaluate condition and mark untaken branch as skipped.

    Args:
        nid: The node ID being processed.
        node: The CONDITIONAL workflow node.
        ctx: Runtime context for condition evaluation.
        outgoing: Typed outgoing edge map.
        adjacency: Forward adjacency map.
        skipped_nodes: Accumulator of skipped node IDs (mutated).
        execution_id: Execution ID for logging.

    Returns:
        A completed ``WorkflowNodeExecution``.

    Raises:
        WorkflowConditionEvalError: On evaluation failure.
    """
    expr = str(node.config.get("condition_expression", "false"))
    if not node.config.get("condition_expression"):
        logger.warning(
            WORKFLOW_EXEC_CONDITION_EVALUATED,
            execution_id=execution_id,
            node_id=nid,
            expression=expr,
            result=False,
            note="missing condition_expression, defaulting to false",
        )
    try:
        result = evaluate_condition(expr, ctx)
    except (ValueError, TypeError, KeyError) as exc:
        logger.exception(
            WORKFLOW_EXEC_CONDITION_EVAL_FAILED,
            execution_id=execution_id,
            node_id=nid,
            expression=expr,
            error=str(exc),
        )
        msg = f"Failed to evaluate condition on node {nid!r}: {exc}"
        raise WorkflowConditionEvalError(msg) from exc

    logger.info(
        WORKFLOW_EXEC_CONDITION_EVALUATED,
        execution_id=execution_id,
        node_id=nid,
        expression=expr,
        result=result,
    )

    # Determine taken/untaken edges
    true_target: str | None = None
    false_target: str | None = None
    for target_id, edge_type in outgoing.get(nid, []):
        if edge_type is WorkflowEdgeType.CONDITIONAL_TRUE:
            true_target = target_id
        elif edge_type is WorkflowEdgeType.CONDITIONAL_FALSE:
            false_target = target_id

    if result:
        taken, untaken = true_target, false_target
    else:
        taken, untaken = false_target, true_target

    if true_target is None or false_target is None:
        logger.warning(
            WORKFLOW_EXEC_CONDITION_EVALUATED,
            execution_id=execution_id,
            node_id=nid,
            note="conditional node missing true or false edge",
            true_target=true_target,
            false_target=false_target,
        )

    if untaken is not None and taken is not None:
        skipped_nodes.update(
            _find_skipped_nodes(untaken, taken, adjacency),
        )

    return WorkflowNodeExecution(
        node_id=nid,
        node_type=node.type,
        status=WorkflowNodeExecutionStatus.COMPLETED,
    )


def _parse_task_config(
    config: dict[str, object],
    node: WorkflowNode,
    execution_id: str,
    nid: str,
) -> tuple[str, str, TaskType, Priority, Complexity]:
    """Parse TASK node config into validated task parameters.

    Returns:
        A 5-tuple of (title, description, task_type, priority, complexity).
    """
    title = str(config.get("title", node.label))
    description = str(config.get("description", f"Task from workflow node {nid}"))

    raw_type = str(config.get("task_type", "development"))
    task_type = _TASK_TYPE_MAP.get(raw_type, TaskType.DEVELOPMENT)
    if raw_type not in _TASK_TYPE_MAP:
        logger.warning(
            WORKFLOW_EXEC_TASK_CREATED,
            execution_id=execution_id,
            node_id=nid,
            note=f"unrecognized task_type {raw_type!r}, using development",
        )

    raw_priority = str(config.get("priority", "medium"))
    priority = _PRIORITY_MAP.get(raw_priority, Priority.MEDIUM)
    if raw_priority not in _PRIORITY_MAP:
        logger.warning(
            WORKFLOW_EXEC_TASK_CREATED,
            execution_id=execution_id,
            node_id=nid,
            note=f"unrecognized priority {raw_priority!r}, using medium",
        )

    raw_complexity = str(config.get("complexity", "medium"))
    complexity = _COMPLEXITY_MAP.get(raw_complexity, Complexity.MEDIUM)
    if raw_complexity not in _COMPLEXITY_MAP:
        logger.warning(
            WORKFLOW_EXEC_TASK_CREATED,
            execution_id=execution_id,
            node_id=nid,
            note=f"unrecognized complexity {raw_complexity!r}, using medium",
        )

    return title, description, task_type, priority, complexity


async def _process_task_node(  # noqa: PLR0913
    nid: str,
    node: WorkflowNode,
    *,
    reverse_adj: dict[str, list[str]],
    node_map: dict[str, WorkflowNode],
    node_task_ids: dict[str, str],
    skipped_nodes: set[str],
    pending_assignments: dict[str, str],
    project: str,
    activated_by: str,
    task_engine: TaskEngine,
    execution_id: str,
) -> WorkflowNodeExecution:
    """Create a concrete task for a TASK node.

    Args:
        nid: The node ID being processed.
        node: The TASK workflow node.
        reverse_adj: Reverse adjacency map.
        node_map: All nodes keyed by ID.
        node_task_ids: Accumulator of node-to-task mappings (mutated).
        skipped_nodes: Set of skipped node IDs.
        pending_assignments: Agent assignments (mutated via pop).
        project: Project ID for the created task.
        activated_by: Identity of the activating user.
        task_engine: Engine for creating tasks.
        execution_id: Execution ID for logging.

    Returns:
        A ``WorkflowNodeExecution`` in TASK_CREATED status.
    """
    config = dict(node.config)
    title, description, task_type, priority, complexity = _parse_task_config(
        config,
        node,
        execution_id,
        nid,
    )
    assigned_to = pending_assignments.pop(nid, None)
    upstream_ids = _find_upstream_task_ids(
        nid,
        reverse_adj,
        node_map,
        node_task_ids,
        skipped_nodes,
    )

    task_data = CreateTaskData(
        title=title,
        description=description,
        type=task_type,
        priority=priority,
        project=project,
        created_by=activated_by,
        assigned_to=assigned_to,
        dependencies=upstream_ids,
        estimated_complexity=complexity,
    )

    task = await task_engine.create_task(
        task_data,
        requested_by="workflow-engine",
    )

    node_task_ids[nid] = task.id
    logger.info(
        WORKFLOW_EXEC_TASK_CREATED,
        execution_id=execution_id,
        node_id=nid,
        task_id=task.id,
        title=title,
    )

    return WorkflowNodeExecution(
        node_id=nid,
        node_type=node.type,
        status=WorkflowNodeExecutionStatus.TASK_CREATED,
        task_id=task.id,
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
        execution = WorkflowExecution(
            id=execution_id,
            definition_id=definition.id,
            definition_version=definition.version,
            status=WorkflowExecutionStatus.RUNNING,
            node_executions=tuple(node_exec_map[n.id] for n in definition.nodes),
            activated_by=activated_by,
            project=project,
            created_at=now,
            updated_at=now,
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
                for target_id in adjacency.get(nid, []):
                    if node_map[target_id].type is WorkflowNodeType.TASK:
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
            return _process_conditional_node(
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

        return await _process_task_node(
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
