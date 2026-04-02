"""Graph-level validation for workflow definitions.

Model-level validators on ``WorkflowDefinition`` ensure structural
integrity (unique IDs, edge references, terminal nodes).  This module
adds *semantic* validation: connectivity, edge-type constraints,
conditional/parallel correctness, and config completeness.
"""

from collections import defaultdict, deque
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, computed_field

from synthorg.core.enums import WorkflowEdgeType, WorkflowNodeType
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_definition import (
    WORKFLOW_DEF_VALIDATED,
    WORKFLOW_DEF_VALIDATION_FAILED,
)

if TYPE_CHECKING:
    from synthorg.engine.workflow.definition import WorkflowDefinition

logger = get_logger(__name__)

_MIN_SPLIT_BRANCHES = 2

_CONDITIONAL_EDGE_TYPES = frozenset(
    {
        WorkflowEdgeType.CONDITIONAL_TRUE,
        WorkflowEdgeType.CONDITIONAL_FALSE,
    }
)


class ValidationErrorCode(StrEnum):
    """Codes for workflow validation errors."""

    UNREACHABLE_NODE = "unreachable_node"
    END_NOT_REACHABLE = "end_not_reachable"
    CONDITIONAL_MISSING_TRUE = "conditional_missing_true"
    CONDITIONAL_MISSING_FALSE = "conditional_missing_false"
    CONDITIONAL_EXTRA_OUTGOING = "conditional_extra_outgoing"
    SPLIT_TOO_FEW_BRANCHES = "split_too_few_branches"
    TASK_MISSING_TITLE = "task_missing_title"
    CYCLE_DETECTED = "cycle_detected"


class WorkflowValidationError(BaseModel):
    """A single validation error with optional location context.

    Attributes:
        code: Machine-readable error code.
        message: Human-readable description.
        node_id: ID of the node this error relates to (if any).
        edge_id: ID of the edge this error relates to (if any).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    code: ValidationErrorCode = Field(description="Error code")
    message: NotBlankStr = Field(description="Human-readable message")
    node_id: NotBlankStr | None = Field(
        default=None,
        description="Related node ID",
    )
    edge_id: NotBlankStr | None = Field(
        default=None,
        description="Related edge ID",
    )


class WorkflowValidationResult(BaseModel):
    """Result of validating a workflow definition.

    Attributes:
        valid: Whether the workflow passed all checks (derived).
        errors: Validation errors found (empty when valid).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    errors: tuple[WorkflowValidationError, ...] = Field(
        default=(),
        description="Validation errors",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def valid(self) -> bool:
        """Whether validation passed (no errors)."""
        return len(self.errors) == 0


def _reachable_from(
    start_id: str,
    adjacency: dict[str, list[str]],
) -> frozenset[str]:
    """BFS to find all nodes reachable from *start_id*."""
    visited: set[str] = set()
    queue: deque[str] = deque([start_id])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        queue.extend(n for n in adjacency.get(current, []) if n not in visited)
    return frozenset(visited)


def _has_cycle(
    node_ids: frozenset[str],
    adjacency: dict[str, list[str]],
) -> bool:
    """Detect cycles using iterative DFS coloring (white/gray/black)."""
    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(node_ids, white)

    for start in node_ids:
        if color[start] != white:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = gray
        while stack:
            nid, idx = stack[-1]
            neighbors = adjacency.get(nid, [])
            if idx < len(neighbors):
                stack[-1] = (nid, idx + 1)
                neighbor = neighbors[idx]
                if neighbor not in color:
                    continue
                if color[neighbor] == gray:
                    return True
                if color[neighbor] == white:
                    color[neighbor] = gray
                    stack.append((neighbor, 0))
            else:
                stack.pop()
                color[nid] = black

    return False


def _check_reachability(
    definition: WorkflowDefinition,
    adjacency: dict[str, list[str]],
) -> list[WorkflowValidationError]:
    """Check all nodes reachable from START and END reachable."""
    errors: list[WorkflowValidationError] = []
    start = next(n for n in definition.nodes if n.type == WorkflowNodeType.START)
    end = next(n for n in definition.nodes if n.type == WorkflowNodeType.END)
    reachable = _reachable_from(start.id, adjacency)

    # Flag unreachable nodes (exclude END -- handled separately)
    errors.extend(
        WorkflowValidationError(
            code=ValidationErrorCode.UNREACHABLE_NODE,
            message=f"Node {node.id!r} is not reachable from START",
            node_id=node.id,
        )
        for node in definition.nodes
        if node.id not in reachable and node.type != WorkflowNodeType.END
    )

    if end.id not in reachable:
        errors.append(
            WorkflowValidationError(
                code=ValidationErrorCode.END_NOT_REACHABLE,
                message="END node is not reachable from START",
                node_id=end.id,
            ),
        )
    return errors


def _check_conditional_edges(
    definition: WorkflowDefinition,
    outgoing: dict[str, list[WorkflowEdgeType]],
) -> list[WorkflowValidationError]:
    """Validate conditional node edge constraints."""
    errors: list[WorkflowValidationError] = []
    for node in definition.nodes:
        if node.type != WorkflowNodeType.CONDITIONAL:
            continue
        out_types = outgoing.get(node.id, [])
        if WorkflowEdgeType.CONDITIONAL_TRUE not in out_types:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.CONDITIONAL_MISSING_TRUE,
                    message=(f"Conditional node {node.id!r} missing TRUE branch"),
                    node_id=node.id,
                )
            )
        if WorkflowEdgeType.CONDITIONAL_FALSE not in out_types:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.CONDITIONAL_MISSING_FALSE,
                    message=(f"Conditional node {node.id!r} missing FALSE branch"),
                    node_id=node.id,
                )
            )
        extra = [t for t in out_types if t not in _CONDITIONAL_EDGE_TYPES]
        if extra:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.CONDITIONAL_EXTRA_OUTGOING,
                    message=(
                        f"Conditional node {node.id!r} has "
                        f"non-conditional outgoing edges: {extra}"
                    ),
                    node_id=node.id,
                )
            )
    return errors


def _check_parallel_splits(
    definition: WorkflowDefinition,
    outgoing: dict[str, list[WorkflowEdgeType]],
) -> list[WorkflowValidationError]:
    """Validate parallel split nodes have enough branches."""
    errors: list[WorkflowValidationError] = []
    for node in definition.nodes:
        if node.type != WorkflowNodeType.PARALLEL_SPLIT:
            continue
        out_types = outgoing.get(node.id, [])
        count = out_types.count(WorkflowEdgeType.PARALLEL_BRANCH)
        if count < _MIN_SPLIT_BRANCHES:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.SPLIT_TOO_FEW_BRANCHES,
                    message=(
                        f"Parallel split {node.id!r} has {count} "
                        f"branch(es), needs at least "
                        f"{_MIN_SPLIT_BRANCHES}"
                    ),
                    node_id=node.id,
                )
            )
    return errors


def _check_task_configs(
    definition: WorkflowDefinition,
) -> list[WorkflowValidationError]:
    """Validate task nodes have required config fields."""
    errors: list[WorkflowValidationError] = []
    for node in definition.nodes:
        if node.type != WorkflowNodeType.TASK:
            continue
        title = node.config.get("title")
        if not title or (isinstance(title, str) and not title.strip()):
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.TASK_MISSING_TITLE,
                    message=(f"Task node {node.id!r} missing title in config"),
                    node_id=node.id,
                )
            )
    return errors


def validate_workflow(
    definition: WorkflowDefinition,
) -> WorkflowValidationResult:
    """Validate a workflow definition for execution readiness.

    Args:
        definition: The workflow definition to validate.

    Returns:
        Validation result with any errors found.
    """
    adjacency: dict[str, list[str]] = defaultdict(list)
    outgoing_types: dict[str, list[WorkflowEdgeType]] = defaultdict(list)
    for edge in definition.edges:
        adjacency[edge.source_node_id].append(edge.target_node_id)
        outgoing_types[edge.source_node_id].append(edge.type)

    errors: list[WorkflowValidationError] = []
    errors.extend(_check_reachability(definition, adjacency))
    errors.extend(
        _check_conditional_edges(definition, outgoing_types),
    )
    errors.extend(
        _check_parallel_splits(definition, outgoing_types),
    )
    errors.extend(_check_task_configs(definition))

    all_ids = frozenset(n.id for n in definition.nodes)
    if _has_cycle(all_ids, adjacency):
        errors.append(
            WorkflowValidationError(
                code=ValidationErrorCode.CYCLE_DETECTED,
                message="Workflow graph contains a cycle",
            )
        )

    result = WorkflowValidationResult(errors=tuple(errors))

    if result.valid:
        logger.info(WORKFLOW_DEF_VALIDATED, workflow_id=definition.id)
    else:
        logger.warning(
            WORKFLOW_DEF_VALIDATION_FAILED,
            workflow_id=definition.id,
            error_count=len(errors),
        )

    return result
