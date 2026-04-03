"""End-to-end pipeline for procedural memory auto-generation.

Extracts a failure analysis payload from execution and recovery data,
invokes the proposer, and stores the resulting procedural memory entry.
"""

from synthorg.core.enums import MemoryCategory
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.loop_protocol import ExecutionResult  # noqa: TC001
from synthorg.engine.recovery import RecoveryResult  # noqa: TC001
from synthorg.memory.models import MemoryMetadata, MemoryStoreRequest
from synthorg.memory.procedural.models import (
    FailureAnalysisPayload,
    ProceduralMemoryProposal,
)
from synthorg.memory.procedural.proposer import ProceduralMemoryProposer  # noqa: TC001
from synthorg.memory.protocol import MemoryBackend  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.procedural_memory import (
    PROCEDURAL_MEMORY_SKIPPED,
    PROCEDURAL_MEMORY_START,
    PROCEDURAL_MEMORY_STORE_FAILED,
    PROCEDURAL_MEMORY_STORED,
)

logger = get_logger(__name__)


def _build_payload(
    execution_result: ExecutionResult,
    recovery_result: RecoveryResult,
) -> FailureAnalysisPayload:
    """Build a failure analysis payload from execution and recovery data.

    Flattens tool call names from all turn records and extracts task
    metadata from the recovery result's task execution.

    Args:
        execution_result: Completed execution result with turn records.
        recovery_result: Recovery result with task and error context.

    Returns:
        Structured payload for the proposer LLM.
    """
    task = recovery_result.task_execution.task
    tool_calls: list[str] = []
    for turn in execution_result.turns:
        tool_calls.extend(turn.tool_calls_made)

    return FailureAnalysisPayload(
        task_id=task.id,
        task_title=task.title,
        task_description=task.description,
        task_type=task.type,
        error_message=recovery_result.error_message,
        strategy_type=recovery_result.strategy_type,
        termination_reason=execution_result.termination_reason.value,
        turn_count=recovery_result.context_snapshot.turn_count,
        tool_calls_made=tuple(tool_calls),
        retry_count=recovery_result.task_execution.retry_count,
        max_retries=task.max_retries,
        can_reassign=recovery_result.can_reassign,
    )


def _format_procedural_content(
    proposal: ProceduralMemoryProposal,
) -> str:
    """Format a proposal into the three-tier progressive disclosure text.

    The discovery line provides retrieval signal; condition/action/rationale
    form the activation-level detail.

    Args:
        proposal: Validated proposer output.

    Returns:
        Formatted memory content string.
    """
    return (
        f"[DISCOVERY] {proposal.discovery}\n\n"
        f"[CONDITION] {proposal.condition}\n\n"
        f"[ACTION] {proposal.action}\n\n"
        f"[RATIONALE] {proposal.rationale}"
    )


async def propose_procedural_memory(  # noqa: PLR0913
    execution_result: ExecutionResult,
    recovery_result: RecoveryResult,
    agent_id: NotBlankStr,
    task_id: NotBlankStr,
    *,
    proposer: ProceduralMemoryProposer,
    memory_backend: MemoryBackend,
) -> NotBlankStr | None:
    """Build payload, propose, and store a procedural memory entry.

    Returns the backend-assigned memory ID if stored, ``None`` if
    the proposal was skipped or storage failed.  Never raises
    (except ``MemoryError`` / ``RecursionError``).

    Args:
        execution_result: Completed execution result.
        recovery_result: Recovery result from the failed execution.
        agent_id: Agent that failed the task.
        task_id: Failed task identifier.
        proposer: LLM-based proposer instance.
        memory_backend: Backend for storing the procedural memory.

    Returns:
        Memory ID or ``None``.
    """
    logger.info(
        PROCEDURAL_MEMORY_START,
        agent_id=agent_id,
        task_id=task_id,
    )

    payload = _build_payload(execution_result, recovery_result)
    proposal = await proposer.propose(payload)

    if proposal is None:
        logger.info(
            PROCEDURAL_MEMORY_SKIPPED,
            agent_id=agent_id,
            task_id=task_id,
            reason="proposer_returned_none",
        )
        return None

    content = _format_procedural_content(proposal)
    tags = ("non-inferable", *proposal.tags)
    request = MemoryStoreRequest(
        category=MemoryCategory.PROCEDURAL,
        content=content,
        metadata=MemoryMetadata(
            source=f"failure:{task_id}",
            confidence=proposal.confidence,
            tags=tags,
        ),
    )

    try:
        memory_id = await memory_backend.store(agent_id, request)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.warning(
            PROCEDURAL_MEMORY_STORE_FAILED,
            agent_id=agent_id,
            task_id=task_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return None

    logger.info(
        PROCEDURAL_MEMORY_STORED,
        agent_id=agent_id,
        task_id=task_id,
        memory_id=memory_id,
        confidence=proposal.confidence,
    )
    return memory_id
