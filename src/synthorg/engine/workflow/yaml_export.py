"""Export a validated WorkflowDefinition as YAML.

Performs a topological sort of the graph and emits a flat list of
steps with dependency references that the engine's coordination/
decomposition subsystem can consume.
"""

from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any

import yaml

from synthorg.core.enums import WorkflowEdgeType, WorkflowNodeType
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_definition import (
    WORKFLOW_DEF_EXPORT_FAILED,
    WORKFLOW_DEF_EXPORTED,
)

if TYPE_CHECKING:
    from synthorg.engine.workflow.definition import WorkflowDefinition

logger = get_logger(__name__)


def _topological_sort(
    node_ids: list[str],
    adjacency: dict[str, list[str]],
) -> list[str]:
    """Kahn's algorithm for topological ordering.

    Args:
        node_ids: All node IDs in the graph.
        adjacency: Forward adjacency list (source -> targets).

    Returns:
        Topologically sorted node IDs.

    Raises:
        ValueError: If the graph contains a cycle.
    """
    in_degree: dict[str, int] = dict.fromkeys(node_ids, 0)
    for targets in adjacency.values():
        for target in targets:
            if target in in_degree:
                in_degree[target] += 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while queue:
        current = queue.popleft()
        result.append(current)
        for neighbor in adjacency.get(current, []):
            if neighbor in in_degree:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

    if len(result) != len(node_ids):
        msg = "Cannot topologically sort: graph contains a cycle"
        raise ValueError(msg)

    return result


_TASK_CONFIG_KEYS = (
    "title",
    "task_type",
    "priority",
    "complexity",
    "coordination_topology",
)
_ASSIGNMENT_KEYS = (
    "routing_strategy",
    "role_filter",
    "agent_name",
)
_ASSIGNMENT_STEP_MAP = {
    "routing_strategy": "strategy",
    "role_filter": "role",
    "agent_name": "agent_name",
}


def _add_task_fields(
    step: dict[str, Any],
    config: dict[str, Any],
) -> None:
    """Copy task-specific config fields into the step dict."""
    for key in _TASK_CONFIG_KEYS:
        if key in config:
            step[key] = config[key]
    if "routing_strategy" in config or "role_filter" in config:
        assignment = {
            _ASSIGNMENT_STEP_MAP[k]: str(config[k])
            for k in _ASSIGNMENT_KEYS
            if k in config
        }
        step["agent_assignment"] = assignment


def _add_assignment_fields(
    step: dict[str, Any],
    config: dict[str, Any],
) -> None:
    """Copy agent assignment fields into the step dict."""
    for key in _ASSIGNMENT_KEYS:
        if key in config:
            step[_ASSIGNMENT_STEP_MAP[key]] = config[key]


def _build_step(
    node_id: str,
    node_type: WorkflowNodeType,
    config: dict[str, Any],
    incoming_node_ids: list[str],
    outgoing_edges: list[tuple[str, WorkflowEdgeType]],
) -> dict[str, Any]:
    """Build a single step dict for the YAML output."""
    step: dict[str, Any] = {"id": node_id, "type": node_type.value}

    if node_type == WorkflowNodeType.TASK:
        _add_task_fields(step, config)
    elif node_type == WorkflowNodeType.AGENT_ASSIGNMENT:
        _add_assignment_fields(step, config)
    elif node_type == WorkflowNodeType.CONDITIONAL:
        if "condition_expression" in config:
            step["condition"] = config["condition_expression"]
    elif node_type == WorkflowNodeType.PARALLEL_SPLIT:
        step["branches"] = [
            t for t, et in outgoing_edges if et == WorkflowEdgeType.PARALLEL_BRANCH
        ]
        if "max_concurrency" in config:
            step["max_concurrency"] = config["max_concurrency"]
    elif node_type == WorkflowNodeType.PARALLEL_JOIN:
        step["join_strategy"] = config.get("join_strategy", "all")

    depends_on = [nid for nid in incoming_node_ids if nid != node_id]
    if depends_on:
        step["depends_on"] = depends_on

    return step


def _build_adjacency_maps(
    definition: WorkflowDefinition,
) -> tuple[
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[tuple[str, WorkflowEdgeType]]],
]:
    """Build forward, reverse, and typed-outgoing adjacency maps."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    reverse_adj: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[tuple[str, WorkflowEdgeType]]] = defaultdict(list)
    for edge in definition.edges:
        adjacency[edge.source_node_id].append(edge.target_node_id)
        reverse_adj[edge.target_node_id].append(edge.source_node_id)
        outgoing[edge.source_node_id].append(
            (edge.target_node_id, edge.type),
        )
    return adjacency, reverse_adj, outgoing


def _assemble_document(
    definition: WorkflowDefinition,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the top-level YAML document structure."""
    doc: dict[str, Any] = {
        "workflow_definition": {
            "name": definition.name,
            "workflow_type": definition.workflow_type.value,
            "steps": steps,
        },
    }
    if definition.description:
        doc["workflow_definition"]["description"] = definition.description
    return doc


def _generate_steps(
    sorted_ids: list[str],
    node_map: dict[str, Any],
    reverse_adj: dict[str, list[str]],
    outgoing_edges: dict[str, list[tuple[str, WorkflowEdgeType]]],
) -> list[dict[str, Any]]:
    """Build step dicts from topologically sorted node IDs."""
    skip = {WorkflowNodeType.START, WorkflowNodeType.END}
    steps: list[dict[str, Any]] = []
    for node_id in sorted_ids:
        node = node_map[node_id]
        if node.type in skip:
            continue
        incoming = [
            src
            for src in reverse_adj.get(node_id, [])
            if node_map[src].type not in skip
        ]
        steps.append(
            _build_step(
                node_id=node_id,
                node_type=node.type,
                config=dict(node.config),
                incoming_node_ids=incoming,
                outgoing_edges=outgoing_edges.get(node_id, []),
            )
        )
    return steps


def _serialize_yaml(
    document: dict[str, Any],
    workflow_id: str,
) -> str:
    """Serialize document to YAML, wrapping errors as ValueError."""
    try:
        return yaml.dump(
            document,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    except yaml.YAMLError as exc:
        msg = f"YAML serialization failed: {exc}"
        logger.exception(
            WORKFLOW_DEF_EXPORT_FAILED,
            workflow_id=workflow_id,
            reason="yaml_error",
        )
        raise ValueError(msg) from exc


def export_workflow_yaml(definition: WorkflowDefinition) -> str:
    """Export a workflow definition as a YAML string.

    Args:
        definition: A validated workflow definition.

    Returns:
        YAML string representation of the workflow.

    Raises:
        ValueError: If the graph contains a cycle or YAML
            serialization fails.
    """
    node_map = {n.id: n for n in definition.nodes}
    adjacency, reverse_adj, outgoing_edges = _build_adjacency_maps(definition)

    try:
        sorted_ids = _topological_sort(
            [n.id for n in definition.nodes],
            adjacency,
        )
    except ValueError:
        logger.exception(
            WORKFLOW_DEF_EXPORT_FAILED,
            workflow_id=definition.id,
            reason="cycle_detected",
        )
        raise

    steps = _generate_steps(sorted_ids, node_map, reverse_adj, outgoing_edges)
    document = _assemble_document(definition, steps)
    result = _serialize_yaml(document, definition.id)

    logger.info(
        WORKFLOW_DEF_EXPORTED,
        workflow_id=definition.id,
        step_count=len(steps),
    )

    return result
