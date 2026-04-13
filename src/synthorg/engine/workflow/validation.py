"""Graph-level validation for workflow definitions.

Model-level validators on ``WorkflowDefinition`` ensure structural
integrity (unique IDs, edge references, terminal nodes).  This module
adds *semantic* validation: connectivity, edge-type constraints,
conditional/parallel correctness, config completeness, and
subworkflow reference correctness (static cycle detection and I/O
contract compatibility).
"""

from collections import defaultdict, deque
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, computed_field

from synthorg.core.enums import (
    WorkflowEdgeType,
    WorkflowNodeType,
    WorkflowValueType,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.definition import WorkflowIODeclaration  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.workflow_definition import (
    SUBWORKFLOW_CYCLE_DETECTED,
    SUBWORKFLOW_IO_INVALID,
    WORKFLOW_DEF_VALIDATED,
    WORKFLOW_DEF_VALIDATION_FAILED,
)

if TYPE_CHECKING:
    from synthorg.engine.workflow.definition import WorkflowDefinition
    from synthorg.engine.workflow.subworkflow_registry import (
        SubworkflowRegistry,
    )

logger = get_logger(__name__)

_MIN_SPLIT_BRANCHES = 2

_CONDITIONAL_EDGE_TYPES = frozenset(
    {
        WorkflowEdgeType.CONDITIONAL_TRUE,
        WorkflowEdgeType.CONDITIONAL_FALSE,
    }
)

_VERIFICATION_EDGE_TYPES = frozenset(
    {
        WorkflowEdgeType.VERIFICATION_PASS,
        WorkflowEdgeType.VERIFICATION_FAIL,
        WorkflowEdgeType.VERIFICATION_REFER,
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
    SUBWORKFLOW_REF_MISSING = "subworkflow_ref_missing"
    SUBWORKFLOW_VERSION_UNPINNED = "subworkflow_version_unpinned"
    SUBWORKFLOW_NOT_FOUND = "subworkflow_not_found"
    SUBWORKFLOW_INPUT_MISSING = "subworkflow_input_missing"
    SUBWORKFLOW_INPUT_UNKNOWN = "subworkflow_input_unknown"
    SUBWORKFLOW_INPUT_TYPE_MISMATCH = "subworkflow_input_type_mismatch"
    SUBWORKFLOW_OUTPUT_MISSING = "subworkflow_output_missing"
    SUBWORKFLOW_OUTPUT_UNKNOWN = "subworkflow_output_unknown"
    SUBWORKFLOW_OUTPUT_TYPE_MISMATCH = "subworkflow_output_type_mismatch"
    SUBWORKFLOW_CYCLE_DETECTED = "subworkflow_cycle_detected"
    VERIFICATION_MISSING_PASS = "verification_missing_pass"  # noqa: S105
    VERIFICATION_MISSING_FAIL = "verification_missing_fail"
    VERIFICATION_MISSING_REFER = "verification_missing_refer"
    VERIFICATION_DUPLICATE_EDGE = "verification_duplicate_edge"
    VERIFICATION_EXTRA_OUTGOING = "verification_extra_outgoing"
    VERIFICATION_EDGE_OUTSIDE = "verification_edge_outside"
    VERIFICATION_MISSING_CONFIG = "verification_missing_config"


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


def _check_verification_edges(
    definition: WorkflowDefinition,
    outgoing: dict[str, list[WorkflowEdgeType]],
) -> list[WorkflowValidationError]:
    """Validate verification node edge constraints."""
    errors: list[WorkflowValidationError] = []
    for node in definition.nodes:
        if node.type != WorkflowNodeType.VERIFICATION:
            continue
        out_types = outgoing.get(node.id, [])
        if WorkflowEdgeType.VERIFICATION_PASS not in out_types:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.VERIFICATION_MISSING_PASS,
                    message=f"Verification node {node.id!r} missing PASS edge",
                    node_id=node.id,
                )
            )
        if WorkflowEdgeType.VERIFICATION_FAIL not in out_types:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.VERIFICATION_MISSING_FAIL,
                    message=f"Verification node {node.id!r} missing FAIL edge",
                    node_id=node.id,
                )
            )
        if WorkflowEdgeType.VERIFICATION_REFER not in out_types:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.VERIFICATION_MISSING_REFER,
                    message=f"Verification node {node.id!r} missing REFER edge",
                    node_id=node.id,
                )
            )
        errors.extend(
            WorkflowValidationError(
                code=ValidationErrorCode.VERIFICATION_DUPLICATE_EDGE,
                message=(
                    f"Verification node {node.id!r} has duplicate "
                    f"{edge_type.value} edge"
                ),
                node_id=node.id,
            )
            for edge_type in _VERIFICATION_EDGE_TYPES
            if out_types.count(edge_type) > 1
        )
        extra = [t for t in out_types if t not in _VERIFICATION_EDGE_TYPES]
        if extra:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.VERIFICATION_EXTRA_OUTGOING,
                    message=(
                        f"Verification node {node.id!r} has "
                        f"non-verification outgoing edges: {extra}"
                    ),
                    node_id=node.id,
                )
            )
    return errors


def _check_verification_edge_scope(
    definition: WorkflowDefinition,
    outgoing: dict[str, list[WorkflowEdgeType]],
) -> list[WorkflowValidationError]:
    """Reject verification edges leaving non-verification nodes."""
    errors: list[WorkflowValidationError] = []
    for node in definition.nodes:
        if node.type == WorkflowNodeType.VERIFICATION:
            continue
        out_types = outgoing.get(node.id, [])
        bad = [t for t in out_types if t in _VERIFICATION_EDGE_TYPES]
        if bad:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.VERIFICATION_EDGE_OUTSIDE,
                    message=(
                        f"Non-verification node {node.id!r} has "
                        f"verification edge(s): {bad}"
                    ),
                    node_id=node.id,
                )
            )
    return errors


def _check_verification_configs(
    definition: WorkflowDefinition,
) -> list[WorkflowValidationError]:
    """Validate verification nodes have required config fields."""
    errors: list[WorkflowValidationError] = []
    for node in definition.nodes:
        if node.type != WorkflowNodeType.VERIFICATION:
            continue
        rubric_name = node.config.get("rubric_name")
        if not isinstance(rubric_name, str) or not rubric_name.strip():
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.VERIFICATION_MISSING_CONFIG,
                    message=(
                        f"Verification node {node.id!r} missing rubric_name in config"
                    ),
                    node_id=node.id,
                )
            )
        evaluator = node.config.get("evaluator_agent_id")
        if not isinstance(evaluator, str) or not evaluator.strip():
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.VERIFICATION_MISSING_CONFIG,
                    message=(
                        f"Verification node {node.id!r} missing "
                        f"evaluator_agent_id in config"
                    ),
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
    errors.extend(
        _check_verification_edges(definition, outgoing_types),
    )
    errors.extend(
        _check_verification_edge_scope(definition, outgoing_types),
    )
    errors.extend(_check_verification_configs(definition))

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


# ---------------------------------------------------------------------------
# Subworkflow save-time validation
# ---------------------------------------------------------------------------


def _extract_subworkflow_config(
    node_config: object,
) -> tuple[str, str | None, dict[str, object], dict[str, object]] | None:
    """Unpack subworkflow node config into ``(id, version, ib, ob)``.

    Returns ``None`` when ``subworkflow_id`` is missing or malformed
    (the node is not a valid subworkflow reference at all).  When
    ``version`` is blank or missing, returns it as ``None`` so
    callers can emit ``SUBWORKFLOW_VERSION_UNPINNED``.
    """
    if not isinstance(node_config, dict):
        return None
    subworkflow_id = node_config.get("subworkflow_id")
    if not isinstance(subworkflow_id, str) or not subworkflow_id.strip():
        return None
    version_obj = node_config.get("version")
    if version_obj is None:
        version = None
    elif isinstance(version_obj, str):
        version = version_obj.strip() or None
    else:
        # Non-string, non-None version is malformed -- return None
        # so downstream validation can surface the error.
        return None
    ib = node_config.get("input_bindings") or {}
    ob = node_config.get("output_bindings") or {}
    if not isinstance(ib, dict):
        ib = {}
    if not isinstance(ob, dict):
        ob = {}
    return subworkflow_id, version, ib, ob


def _literal_matches_type(  # noqa: C901, PLR0911
    value: object,
    value_type: WorkflowValueType,
) -> bool:
    """Return ``True`` if *value* is compatible with *value_type*.

    Used at save time to reject obviously-wrong literal bindings.
    Dotted-path expressions (``@parent.x``) cannot be resolved at save
    time, so they are skipped and validated again at runtime.
    """
    if value_type is WorkflowValueType.STRING:
        return isinstance(value, str)
    if value_type is WorkflowValueType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type is WorkflowValueType.FLOAT:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type is WorkflowValueType.BOOLEAN:
        return isinstance(value, bool)
    if value_type in (
        WorkflowValueType.TASK_REF,
        WorkflowValueType.AGENT_REF,
    ):
        return isinstance(value, str) and bool(value.strip())
    if value_type is WorkflowValueType.DATETIME:
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value)
            except ValueError:
                return False
            else:
                return True
        return False
    # JSON is permissive at save time.
    return True


def _is_deferred_expression(value: object, *, direction: str = "") -> bool:
    """Return ``True`` when *value* is a valid deferred lookup for *direction*."""
    if not isinstance(value, str):
        return False
    if direction == "input":
        return value.startswith("@parent.")
    if direction == "output":
        return value.startswith(("@child.", "@parent."))
    return value.startswith(("@parent.", "@child."))


def _check_bindings_against_declarations(  # noqa: PLR0913
    *,
    node_id: str,
    ref_label: str,
    bindings: dict[str, object],
    declarations: tuple[WorkflowIODeclaration, ...],
    direction: str,
    missing_code: ValidationErrorCode,
    unknown_code: ValidationErrorCode,
    type_code: ValidationErrorCode,
) -> list[WorkflowValidationError]:
    """Validate binding keys/literals against a set of declarations."""
    errors: list[WorkflowValidationError] = [
        WorkflowValidationError(
            code=missing_code,
            message=(
                f"Subworkflow node {node_id!r} missing required "
                f"{direction} {d.name!r} for {ref_label}"
            ),
            node_id=node_id,
        )
        for d in declarations
        if d.required and d.name not in bindings
    ]
    by_name = {d.name: d for d in declarations}
    for name, value in bindings.items():
        if name not in by_name:
            errors.append(
                WorkflowValidationError(
                    code=unknown_code,
                    message=(
                        f"Subworkflow node {node_id!r} binds unknown "
                        f"{direction} {name!r} for {ref_label}"
                    ),
                    node_id=node_id,
                ),
            )
            continue
        decl = by_name[name]
        if _is_deferred_expression(value, direction=direction):
            continue
        if isinstance(value, str) and value.startswith("@"):
            errors.append(
                WorkflowValidationError(
                    code=type_code,
                    message=(
                        f"Subworkflow node {node_id!r} binds {direction} "
                        f"{name!r} with unsupported expression {value!r}"
                    ),
                    node_id=node_id,
                ),
            )
            continue
        if not _literal_matches_type(value, decl.type):
            errors.append(
                WorkflowValidationError(
                    code=type_code,
                    message=(
                        f"Subworkflow node {node_id!r} binds {direction} "
                        f"{name!r} with literal incompatible with "
                        f"declared type {decl.type.value}"
                    ),
                    node_id=node_id,
                ),
            )
    return errors


def _check_subworkflow_io_for_node(  # noqa: PLR0913
    *,
    node_id: str,
    subworkflow_id: str,
    version: str,
    input_bindings: dict[str, object],
    output_bindings: dict[str, object],
    child_inputs: tuple[WorkflowIODeclaration, ...],
    child_outputs: tuple[WorkflowIODeclaration, ...],
) -> list[WorkflowValidationError]:
    """Check a single SUBWORKFLOW node's bindings against child I/O."""
    ref_label = f"{subworkflow_id!r}@{version!r}"
    errors = _check_bindings_against_declarations(
        node_id=node_id,
        ref_label=ref_label,
        bindings=input_bindings,
        declarations=child_inputs,
        direction="input",
        missing_code=ValidationErrorCode.SUBWORKFLOW_INPUT_MISSING,
        unknown_code=ValidationErrorCode.SUBWORKFLOW_INPUT_UNKNOWN,
        type_code=ValidationErrorCode.SUBWORKFLOW_INPUT_TYPE_MISMATCH,
    )
    errors.extend(
        _check_bindings_against_declarations(
            node_id=node_id,
            ref_label=ref_label,
            bindings=output_bindings,
            declarations=child_outputs,
            direction="output",
            missing_code=ValidationErrorCode.SUBWORKFLOW_OUTPUT_MISSING,
            unknown_code=ValidationErrorCode.SUBWORKFLOW_OUTPUT_UNKNOWN,
            type_code=ValidationErrorCode.SUBWORKFLOW_OUTPUT_TYPE_MISMATCH,
        ),
    )
    return errors


async def validate_subworkflow_io(
    definition: WorkflowDefinition,
    registry: SubworkflowRegistry,
) -> WorkflowValidationResult:
    """Validate every SUBWORKFLOW node's bindings against its child.

    Args:
        definition: The workflow definition to validate.
        registry: A :class:`SubworkflowRegistry` used to resolve
            pinned subworkflows.

    Returns:
        A ``WorkflowValidationResult`` with errors (possibly empty).
        Errors cover: missing ``subworkflow_id`` / ``version`` config,
        unresolvable pinned versions, missing required inputs, unknown
        inputs/outputs, and literal type mismatches.
    """
    errors: list[WorkflowValidationError] = []
    from synthorg.engine.errors import SubworkflowNotFoundError  # noqa: PLC0415

    for node in definition.nodes:
        if node.type is not WorkflowNodeType.SUBWORKFLOW:
            continue
        parsed = _extract_subworkflow_config(dict(node.config))
        if parsed is None:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.SUBWORKFLOW_REF_MISSING,
                    message=(
                        f"Subworkflow node {node.id!r} is missing "
                        "subworkflow_id or version in config"
                    ),
                    node_id=node.id,
                ),
            )
            continue
        subworkflow_id, version, ib, ob = parsed

        if version is None:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.SUBWORKFLOW_VERSION_UNPINNED,
                    message=(
                        f"Subworkflow node {node.id!r} references "
                        f"{subworkflow_id!r} without a pinned version"
                    ),
                    node_id=node.id,
                ),
            )
            continue

        try:
            child = await registry.get(subworkflow_id, version)
        except SubworkflowNotFoundError:
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.SUBWORKFLOW_NOT_FOUND,
                    message=(
                        f"Subworkflow node {node.id!r} references "
                        f"{subworkflow_id!r}@{version!r}, which is "
                        "not in the registry"
                    ),
                    node_id=node.id,
                ),
            )
            continue

        errors.extend(
            _check_subworkflow_io_for_node(
                node_id=node.id,
                subworkflow_id=subworkflow_id,
                version=version,
                input_bindings=ib,
                output_bindings=ob,
                child_inputs=child.inputs,
                child_outputs=child.outputs,
            ),
        )

    result = WorkflowValidationResult(errors=tuple(errors))
    if errors:
        logger.warning(
            SUBWORKFLOW_IO_INVALID,
            workflow_id=definition.id,
            error_count=len(errors),
        )
    return result


async def validate_subworkflow_graph(
    definition: WorkflowDefinition,
    registry: SubworkflowRegistry,
) -> WorkflowValidationResult:
    """Detect cycles across the static subworkflow reference graph.

    Starting from *definition*, walk every SUBWORKFLOW node config's
    pinned ``(id, version)`` reference (via the registry) and then
    recurse into the child's own SUBWORKFLOW nodes.  Any back-edge
    (revisiting a ``(id, version)`` coordinate currently on the DFS
    stack) is a cycle and is reported with the cycle path.

    Unresolvable references are NOT reported here -- that's
    :func:`validate_subworkflow_io`'s job.

    Returns:
        A ``WorkflowValidationResult`` with one ``SUBWORKFLOW_CYCLE_DETECTED``
        error per detected cycle.  Empty errors mean no cycles.
    """
    errors: list[WorkflowValidationError] = []
    root_key = (definition.id, definition.version)
    visiting: set[tuple[str, str]] = set()
    finished: set[tuple[str, str]] = set()

    from synthorg.engine.errors import SubworkflowNotFoundError  # noqa: PLC0415

    async def _visit(
        node_key: tuple[str, str],
        source_definition: WorkflowDefinition,
        path: list[tuple[str, str]],
    ) -> None:
        if node_key in visiting:
            cycle_slice = [*path[path.index(node_key) :], node_key]
            cycle_repr = " -> ".join(f"{sid}@{ver}" for sid, ver in cycle_slice)
            errors.append(
                WorkflowValidationError(
                    code=ValidationErrorCode.SUBWORKFLOW_CYCLE_DETECTED,
                    message=(f"Subworkflow reference cycle detected: {cycle_repr}"),
                ),
            )
            return
        if node_key in finished:
            return

        visiting.add(node_key)
        path.append(node_key)
        try:
            for child_node in source_definition.nodes:
                if child_node.type is not WorkflowNodeType.SUBWORKFLOW:
                    continue
                parsed = _extract_subworkflow_config(dict(child_node.config))
                if parsed is None:
                    continue
                child_sub_id, child_version, _, _ = parsed
                if child_version is None:
                    # Unpinned -- skip cycle check (no concrete version).
                    continue
                child_key = (child_sub_id, child_version)

                try:
                    child_definition = await registry.get(
                        child_sub_id,
                        child_version,
                    )
                except SubworkflowNotFoundError:
                    continue
                await _visit(child_key, child_definition, path)
        finally:
            visiting.discard(node_key)
            path.pop()
            finished.add(node_key)

    await _visit(root_key, definition, [])

    if errors:
        logger.warning(
            SUBWORKFLOW_CYCLE_DETECTED,
            workflow_id=definition.id,
            cycle_count=len(errors),
        )
    return WorkflowValidationResult(errors=tuple(errors))
