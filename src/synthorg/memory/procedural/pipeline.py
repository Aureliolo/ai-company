"""End-to-end pipeline for procedural memory auto-generation.

Extracts a failure analysis payload from execution and recovery data,
invokes the proposer, stores the resulting procedural memory entry,
and optionally materializes a SKILL.md file.
"""

import re
from pathlib import Path

from synthorg.core.enums import MemoryCategory
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.loop_protocol import ExecutionResult  # noqa: TC001
from synthorg.engine.recovery import RecoveryResult  # noqa: TC001
from synthorg.engine.sanitization import sanitize_message
from synthorg.memory.models import MemoryMetadata, MemoryStoreRequest
from synthorg.memory.procedural.models import (
    FailureAnalysisPayload,
    ProceduralMemoryConfig,
    ProceduralMemoryProposal,
)
from synthorg.memory.procedural.proposer import ProceduralMemoryProposer  # noqa: TC001
from synthorg.memory.protocol import MemoryBackend  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.procedural_memory import (
    PROCEDURAL_MEMORY_PAYLOAD_BUILT,
    PROCEDURAL_MEMORY_SKIPPED,
    PROCEDURAL_MEMORY_START,
    PROCEDURAL_MEMORY_STORE_FAILED,
    PROCEDURAL_MEMORY_STORED,
)

logger = get_logger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _build_payload(
    execution_result: ExecutionResult,
    recovery_result: RecoveryResult,
) -> FailureAnalysisPayload:
    """Build a failure analysis payload from execution and recovery data.

    Flattens tool call names from all turn records in the execution
    result and extracts task metadata from the recovery result's
    task execution and context snapshot.

    The ``error_message`` is sanitized via ``sanitize_message`` to
    strip file paths, URLs, and non-printable characters before it
    reaches the proposer LLM.

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
        error_message=sanitize_message(recovery_result.error_message),
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
    """Format a proposal into three-tier progressive disclosure text.

    * Discovery: retrieval signal (~100 tokens).
    * Activation: condition/action/rationale.
    * Execution: ordered steps for applying the knowledge.

    Args:
        proposal: Validated proposer output.

    Returns:
        Formatted memory content string.
    """
    parts = [
        f"[DISCOVERY] {proposal.discovery}",
        f"[CONDITION] {proposal.condition}",
        f"[ACTION] {proposal.action}",
        f"[RATIONALE] {proposal.rationale}",
    ]
    if proposal.execution_steps:
        steps = "\n".join(
            f"  {i}. {step}" for i, step in enumerate(proposal.execution_steps, 1)
        )
        parts.append(f"[EXECUTION]\n{steps}")
    return "\n\n".join(parts)


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    return _SLUG_RE.sub("-", text.lower()).strip("-")[:80]


def materialize_skill_md(
    proposal: ProceduralMemoryProposal,
    task_id: str,
    directory: str,
) -> Path:
    """Write a proposal as a SKILL.md file for git-native versioning.

    The file follows the Agent Skills (agentskills.io) format with
    YAML frontmatter and three-tier progressive disclosure sections.

    Args:
        proposal: Validated proposer output.
        task_id: Task identifier (used in filename).
        directory: Target directory for the SKILL.md file.

    Returns:
        Path to the written file.
    """
    slug = _slugify(proposal.discovery[:60])
    filename = f"SKILL-{task_id}-{slug}.md"
    path = Path(directory) / filename

    tags_str = ", ".join(proposal.tags) if proposal.tags else ""
    steps_block = ""
    if proposal.execution_steps:
        lines = "\n".join(
            f"{i}. {step}" for i, step in enumerate(proposal.execution_steps, 1)
        )
        steps_block = f"\n## Execution Steps\n\n{lines}\n"

    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {proposal.discovery}\n"
        f"trigger: {proposal.condition}\n"
        f"confidence: {proposal.confidence}\n"
        f"tags: [{tags_str}]\n"
        f"source: failure:{task_id}\n"
        "---\n\n"
        f"# {proposal.discovery}\n\n"
        f"## Condition\n\n{proposal.condition}\n\n"
        f"## Action\n\n{proposal.action}\n\n"
        f"## Rationale\n\n{proposal.rationale}\n"
        f"{steps_block}"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


async def propose_procedural_memory(  # noqa: PLR0913
    execution_result: ExecutionResult,
    recovery_result: RecoveryResult,
    agent_id: NotBlankStr,
    task_id: NotBlankStr,
    *,
    proposer: ProceduralMemoryProposer,
    memory_backend: MemoryBackend,
    config: ProceduralMemoryConfig | None = None,
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
        config: Optional config for SKILL.md materialization.

    Returns:
        Memory ID or ``None``.
    """
    logger.info(
        PROCEDURAL_MEMORY_START,
        agent_id=agent_id,
        task_id=task_id,
    )

    try:
        payload = _build_payload(execution_result, recovery_result)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.warning(
            PROCEDURAL_MEMORY_STORE_FAILED,
            agent_id=agent_id,
            task_id=task_id,
            error=f"payload construction failed: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        return None

    logger.debug(
        PROCEDURAL_MEMORY_PAYLOAD_BUILT,
        agent_id=agent_id,
        task_id=task_id,
        turn_count=payload.turn_count,
        tool_count=len(payload.tool_calls_made),
    )

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
            exc_info=True,
        )
        return None

    logger.info(
        PROCEDURAL_MEMORY_STORED,
        agent_id=agent_id,
        task_id=task_id,
        memory_id=memory_id,
        confidence=proposal.confidence,
    )

    # Materialize SKILL.md file when configured.
    if config is not None and config.skill_md_directory is not None:
        try:
            materialize_skill_md(proposal, task_id, config.skill_md_directory)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                PROCEDURAL_MEMORY_STORE_FAILED,
                agent_id=agent_id,
                task_id=task_id,
                error=f"SKILL.md write failed: {type(exc).__name__}: {exc}",
                exc_info=True,
            )

    return memory_id
