"""Distillation request capture at task completion.

Captures trajectory summaries, outcomes, and retrieved memory IDs
from execution results to feed into the consolidation pipeline for
outcome-driven memory curation.
"""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.enums import MemoryCategory
from synthorg.core.types import NotBlankStr
from synthorg.engine.loop_protocol import (
    ExecutionResult,
    TerminationReason,
    TurnRecord,
)
from synthorg.memory.models import MemoryMetadata, MemoryStoreRequest
from synthorg.memory.protocol import MemoryBackend  # noqa: TC001
from synthorg.memory.tool_retriever import (
    RECALL_MEMORY_TOOL_NAME,
    SEARCH_MEMORY_TOOL_NAME,
)
from synthorg.observability import get_logger
from synthorg.observability.events.consolidation import (
    DISTILLATION_CAPTURE_FAILED,
    DISTILLATION_CAPTURED,
)

logger = get_logger(__name__)


class DistillationRequest(BaseModel):
    """Captured distillation data from a completed task execution.

    Attributes:
        agent_id: Which agent completed the task.
        task_id: Which task was completed.
        trajectory_summary: Summarized execution trajectory.
        outcome: Task outcome description.
        retrieved_memory_ids: IDs of memories retrieved during execution.
        created_at: Capture timestamp.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr = Field(description="Agent that completed the task")
    task_id: NotBlankStr = Field(description="Completed task identifier")
    trajectory_summary: NotBlankStr = Field(
        description="Summarized execution trajectory",
    )
    outcome: NotBlankStr = Field(description="Task outcome description")
    retrieved_memory_ids: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="IDs of memories retrieved during execution",
    )
    created_at: AwareDatetime = Field(description="Capture timestamp")


_MEMORY_TOOL_NAMES = frozenset({SEARCH_MEMORY_TOOL_NAME, RECALL_MEMORY_TOOL_NAME})


def build_trajectory_summary(turns: tuple[TurnRecord, ...]) -> str:
    """Build a trajectory summary from turn records.

    Args:
        turns: Per-turn metadata from the execution.

    Returns:
        Human-readable trajectory summary.
    """
    if not turns:
        return "No turns recorded."

    total_tokens = sum(t.total_tokens for t in turns)
    all_tools: list[str] = []
    for turn in turns:
        all_tools.extend(turn.tool_calls_made)
    unique_tools = sorted(set(all_tools))

    parts = [f"{len(turns)} turns, {total_tokens} tokens"]
    if unique_tools:
        parts.append(f"tools: {', '.join(unique_tools)}")
    if all_tools:
        parts.append(f"{len(all_tools)} tool calls total")

    return "; ".join(parts)


def build_outcome(
    termination_reason: TerminationReason,
    error_message: str | None,
) -> str:
    """Build an outcome description from termination metadata.

    Args:
        termination_reason: Why the execution loop stopped.
        error_message: Error description (when reason is ERROR).

    Returns:
        Human-readable outcome string.
    """
    if termination_reason == TerminationReason.COMPLETED:
        return "Task completed successfully."
    if termination_reason == TerminationReason.ERROR and error_message:
        return f"Task failed: {error_message}"
    return f"Task terminated: {termination_reason.value}"


def extract_memory_ids(
    turns: tuple[TurnRecord, ...],
) -> tuple[NotBlankStr, ...]:
    """Extract memory tool call names from turn records.

    Identifies turns where ``search_memory`` or ``recall_memory``
    tools were invoked.  Returns the tool names as identifiers
    (actual memory IDs are internal to the tool results, not
    available in ``TurnRecord``).

    Args:
        turns: Per-turn metadata from the execution.

    Returns:
        Tuple of memory-related tool call names found.
    """
    return tuple(
        NotBlankStr(tool_name)
        for turn in turns
        for tool_name in turn.tool_calls_made
        if tool_name in _MEMORY_TOOL_NAMES
    )


async def capture_distillation(
    execution_result: ExecutionResult,
    agent_id: NotBlankStr,
    task_id: NotBlankStr,
    *,
    backend: MemoryBackend,
) -> DistillationRequest | None:
    """Capture distillation data at task completion.

    Non-critical -- returns ``None`` on failure and logs a warning.
    The captured data is stored as an EPISODIC memory entry tagged
    with ``"distillation"`` for later consolidation.

    Args:
        execution_result: The completed execution result.
        agent_id: Agent that ran the task.
        task_id: Task identifier.
        backend: Memory backend for storing the distillation entry.

    Returns:
        The captured ``DistillationRequest``, or ``None`` on failure.
    """
    try:
        trajectory = build_trajectory_summary(execution_result.turns)
        outcome = build_outcome(
            execution_result.termination_reason,
            execution_result.error_message,
        )
        memory_ids = extract_memory_ids(execution_result.turns)

        request = DistillationRequest(
            agent_id=agent_id,
            task_id=task_id,
            trajectory_summary=trajectory,
            outcome=outcome,
            retrieved_memory_ids=memory_ids,
            created_at=datetime.now(UTC),
        )

        store_content = (
            f"Distillation -- {outcome}\n"
            f"Trajectory: {trajectory}\n"
            f"Memory lookups: {len(memory_ids)}"
        )

        store_request = MemoryStoreRequest(
            category=MemoryCategory.EPISODIC,
            content=store_content,
            metadata=MemoryMetadata(
                source="distillation",
                tags=("distillation",),
            ),
        )
        await backend.store(agent_id, store_request)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.warning(
            DISTILLATION_CAPTURE_FAILED,
            agent_id=agent_id,
            task_id=task_id,
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,
        )
        return None
    else:
        logger.info(
            DISTILLATION_CAPTURED,
            agent_id=agent_id,
            task_id=task_id,
            turns=len(execution_result.turns),
            memory_ids=len(memory_ids),
        )
        return request
