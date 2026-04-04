"""Activation-time helper functions for workflow execution.

Graph-walking, conditional node processing, and task config
parsing used by ``WorkflowExecutionService.activate()``.
"""

from collections import deque
from typing import TYPE_CHECKING

from synthorg.core.enums import (
    Complexity,
    Priority,
    TaskType,
    WorkflowEdgeType,
    WorkflowNodeExecutionStatus,
    WorkflowNodeType,
)
from synthorg.engine.errors import WorkflowConditionEvalError
from synthorg.engine.task_engine_models import CreateTaskData
from synthorg.engine.workflow.condition_eval import evaluate_condition
from synthorg.engine.workflow.execution_models import WorkflowNodeExecution
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_execution import (
    WORKFLOW_EXEC_CONDITION_EVAL_FAILED,
    WORKFLOW_EXEC_CONDITION_EVALUATED,
    WORKFLOW_EXEC_TASK_CREATED,
)

if TYPE_CHECKING:
    from synthorg.engine.task_engine import TaskEngine
    from synthorg.engine.workflow.definition import WorkflowNode

logger = get_logger(__name__)

_TASK_TYPE_MAP: dict[str, TaskType] = {t.value: t for t in TaskType}
_PRIORITY_MAP: dict[str, Priority] = {p.value: p for p in Priority}
_COMPLEXITY_MAP: dict[str, Complexity] = {c.value: c for c in Complexity}

# Node types that produce no concrete task (control flow and metadata)
CONTROL_NODE_TYPES = frozenset(
    {
        WorkflowNodeType.START,
        WorkflowNodeType.END,
        WorkflowNodeType.AGENT_ASSIGNMENT,
        WorkflowNodeType.CONDITIONAL,
        WorkflowNodeType.PARALLEL_SPLIT,
        WorkflowNodeType.PARALLEL_JOIN,
    }
)


def find_downstream_task_ids(
    nid: str,
    adjacency: dict[str, list[str]],
    node_map: dict[str, WorkflowNode],
) -> list[str]:
    """Walk forward through control nodes to find downstream TASK nodes.

    Used by AGENT_ASSIGNMENT to propagate assignments through
    intervening control nodes (CONDITIONAL, SPLIT, JOIN, etc.)
    to reach the actual TASK nodes.  Stops at other
    AGENT_ASSIGNMENT nodes (which override).
    """
    result: list[str] = []
    visited: set[str] = set()
    queue: deque[str] = deque(adjacency.get(nid, []))
    while queue:
        tid = queue.popleft()
        if tid in visited:
            continue
        visited.add(tid)
        target_node = node_map[tid]
        if target_node.type is WorkflowNodeType.TASK:
            result.append(tid)
        elif target_node.type is WorkflowNodeType.AGENT_ASSIGNMENT:
            pass  # Another assignment overrides -- stop propagation
        elif target_node.type in CONTROL_NODE_TYPES:
            queue.extend(adjacency.get(tid, []))
    return result


def find_upstream_task_ids(
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
        elif pred_node.type in CONTROL_NODE_TYPES:
            # Keep walking backwards through control nodes
            queue.extend(reverse_adj.get(pred_id, []))

    return tuple(sorted(set(result)))


def find_skipped_nodes(
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


def process_conditional_node(  # noqa: PLR0913
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

    safe_expr = expr.replace("\n", " ").replace("\r", " ")
    logger.info(
        WORKFLOW_EXEC_CONDITION_EVALUATED,
        execution_id=execution_id,
        node_id=nid,
        expression=safe_expr,
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
            find_skipped_nodes(untaken, taken, adjacency),
        )

    return WorkflowNodeExecution(
        node_id=nid,
        node_type=node.type,
        status=WorkflowNodeExecutionStatus.COMPLETED,
    )


def parse_task_config(
    config: dict[str, object],
    node: WorkflowNode,
    nid: str,
) -> tuple[str, str, TaskType, Priority, Complexity]:
    """Parse TASK node config into validated task parameters.

    Returns:
        A 5-tuple of (title, description, task_type, priority, complexity).
    """
    title = str(config.get("title", node.label))
    description = str(config.get("description", f"Task from workflow node {nid}"))

    raw_type = str(config.get("task_type", "development"))
    if raw_type not in _TASK_TYPE_MAP:
        msg = (
            f"Node {nid!r} has unrecognized task_type {raw_type!r}"
            f" (valid: {sorted(_TASK_TYPE_MAP)})"
        )
        logger.warning(
            WORKFLOW_EXEC_TASK_CREATED,
            node_id=nid,
            error=msg,
        )
        raise ValueError(msg)
    task_type = _TASK_TYPE_MAP[raw_type]

    raw_priority = str(config.get("priority", "medium"))
    if raw_priority not in _PRIORITY_MAP:
        msg = (
            f"Node {nid!r} has unrecognized priority {raw_priority!r}"
            f" (valid: {sorted(_PRIORITY_MAP)})"
        )
        logger.warning(
            WORKFLOW_EXEC_TASK_CREATED,
            node_id=nid,
            error=msg,
        )
        raise ValueError(msg)
    priority = _PRIORITY_MAP[raw_priority]

    raw_complexity = str(config.get("complexity", "medium"))
    if raw_complexity not in _COMPLEXITY_MAP:
        msg = (
            f"Node {nid!r} has unrecognized complexity {raw_complexity!r}"
            f" (valid: {sorted(_COMPLEXITY_MAP)})"
        )
        logger.warning(
            WORKFLOW_EXEC_TASK_CREATED,
            node_id=nid,
            error=msg,
        )
        raise ValueError(msg)
    complexity = _COMPLEXITY_MAP[raw_complexity]

    return title, description, task_type, priority, complexity


async def process_task_node(  # noqa: PLR0913
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
    title, description, task_type, priority, complexity = parse_task_config(
        config,
        node,
        nid,
    )
    assigned_to = pending_assignments.pop(nid, None)
    upstream_ids = find_upstream_task_ids(
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
