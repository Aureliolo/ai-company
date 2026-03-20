"""Oldest-turns summarization compaction callback factory.

Creates a ``CompactionCallback`` that archives the oldest conversation
turns into a summary message when the context fill level exceeds a
configurable threshold.
"""

from typing import TYPE_CHECKING

from synthorg.engine.compaction.models import (
    CompactionConfig,
    CompressionMetadata,
)
from synthorg.engine.sanitization import sanitize_message
from synthorg.engine.token_estimation import (
    DefaultTokenEstimator,
    PromptTokenEstimator,
)
from synthorg.observability import get_logger
from synthorg.observability.events.context_budget import (
    CONTEXT_BUDGET_COMPACTION_COMPLETED,
    CONTEXT_BUDGET_COMPACTION_FALLBACK,
    CONTEXT_BUDGET_COMPACTION_SKIPPED,
    CONTEXT_BUDGET_COMPACTION_STARTED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage

if TYPE_CHECKING:
    from synthorg.engine.compaction.protocol import CompactionCallback
    from synthorg.engine.context import AgentContext

logger = get_logger(__name__)

_MAX_SUMMARY_CHARS: int = 500
"""Maximum characters in the generated summary text."""


def make_compaction_callback(
    *,
    config: CompactionConfig,
    estimator: PromptTokenEstimator | None = None,
) -> CompactionCallback:
    """Create a compaction callback with the given configuration.

    The returned async callable checks whether the context fill level
    exceeds ``config.fill_threshold_percent`` and, if so, replaces
    the oldest conversation turns with a summary message.

    Args:
        config: Compaction configuration.
        estimator: Token estimator for summary size estimation;
            defaults to ``DefaultTokenEstimator``.

    Returns:
        An async compaction callback.
    """
    est = estimator or DefaultTokenEstimator()

    async def _compact(ctx: AgentContext) -> AgentContext | None:
        return _do_compaction(ctx, config, est)

    return _compact


def _do_compaction(
    ctx: AgentContext,
    config: CompactionConfig,
    estimator: PromptTokenEstimator,
) -> AgentContext | None:
    """Core compaction logic.

    Args:
        ctx: Current agent context.
        config: Compaction configuration.
        estimator: Token estimator.

    Returns:
        New compacted ``AgentContext`` or ``None`` if no compaction needed.
    """
    fill_pct = ctx.context_fill_percent
    if fill_pct is None or fill_pct < config.fill_threshold_percent:
        return None

    conversation = ctx.conversation
    if len(conversation) < config.min_messages_to_compact:
        logger.debug(
            CONTEXT_BUDGET_COMPACTION_SKIPPED,
            execution_id=ctx.execution_id,
            reason="too_few_messages",
            message_count=len(conversation),
            min_required=config.min_messages_to_compact,
        )
        return None

    logger.info(
        CONTEXT_BUDGET_COMPACTION_STARTED,
        execution_id=ctx.execution_id,
        fill_percent=fill_pct,
        message_count=len(conversation),
    )

    split = _split_conversation(ctx, config)
    if split is None:
        return None
    head, archivable, recent = split

    compressed, metadata, summary_tokens = _compress(
        ctx,
        head,
        archivable,
        recent,
        estimator,
    )

    # Re-estimate fill with compressed conversation.  Counts
    # conversation tokens only — system prompt and tool overhead
    # are excluded.  The loop's next ``update_context_fill``
    # call restores the full estimate.
    new_fill = estimator.estimate_conversation_tokens(compressed)

    logger.info(
        CONTEXT_BUDGET_COMPACTION_COMPLETED,
        execution_id=ctx.execution_id,
        original_messages=len(conversation),
        compacted_messages=len(compressed),
        archived_turns=metadata.archived_turns,
        summary_tokens=summary_tokens,
        compactions_total=metadata.compactions_performed,
    )
    return ctx.with_compression(metadata, compressed, new_fill)


def _split_conversation(
    ctx: AgentContext,
    config: CompactionConfig,
) -> (
    tuple[
        tuple[ChatMessage, ...],
        tuple[ChatMessage, ...],
        tuple[ChatMessage, ...],
    ]
    | None
):
    """Split conversation into head, archivable, and recent segments.

    Returns ``None`` when there is nothing to archive.
    """
    conversation = ctx.conversation
    preserve_count = config.preserve_recent_turns * 2
    # Preserve all leading SYSTEM messages (original system prompt
    # and any prior compaction summaries).
    start_idx = 0
    while (
        start_idx < len(conversation)
        and conversation[start_idx].role == MessageRole.SYSTEM
    ):
        start_idx += 1
    head = tuple(conversation[:start_idx])

    if preserve_count >= len(conversation) - start_idx:
        logger.debug(
            CONTEXT_BUDGET_COMPACTION_SKIPPED,
            execution_id=ctx.execution_id,
            reason="nothing_to_archive",
            preserve_count=preserve_count,
            message_count=len(conversation),
        )
        return None

    archivable = conversation[start_idx:-preserve_count]
    recent = conversation[-preserve_count:]
    return head, archivable, recent


def _compress(
    ctx: AgentContext,
    head: tuple[ChatMessage, ...],
    archivable: tuple[ChatMessage, ...],
    recent: tuple[ChatMessage, ...],
    estimator: PromptTokenEstimator,
) -> tuple[tuple[ChatMessage, ...], CompressionMetadata, int]:
    """Build compressed conversation and metadata.

    Returns ``(compressed_conversation, metadata, summary_tokens)``.
    """
    summary_text = _build_summary(archivable, ctx.execution_id)
    summary_msg = ChatMessage(
        role=MessageRole.SYSTEM,
        content=summary_text,
    )
    summary_tokens = estimator.estimate_tokens(summary_text)
    compressed = (*head, summary_msg, *recent)

    prior = ctx.compression_metadata
    compactions_count = prior.compactions_performed + 1 if prior is not None else 1
    prior_archived = prior.archived_turns if prior is not None else 0

    archived_turn_count = sum(1 for m in archivable if m.role == MessageRole.ASSISTANT)
    metadata = CompressionMetadata(
        compression_point=ctx.turn_count,
        archived_turns=prior_archived + archived_turn_count,
        summary_tokens=summary_tokens,
        compactions_performed=compactions_count,
    )
    return compressed, metadata, summary_tokens


def _build_summary(
    messages: tuple[ChatMessage, ...],
    execution_id: str,
) -> str:
    """Build a simple text summary from archived messages.

    Concatenates sanitized assistant message content snippets into a
    summary paragraph, capped at ``_MAX_SUMMARY_CHARS``. Each snippet
    is redacted for file paths and URLs via ``sanitize_message``.

    Args:
        messages: The archived messages to summarize.
        execution_id: Execution identifier for log correlation.

    Returns:
        Summary text describing the archived conversation.
    """
    snippets: list[str] = []
    for msg in messages:
        if msg.role == MessageRole.ASSISTANT and msg.content:
            cleaned = msg.content.replace("\n", " ").strip()
            if cleaned:
                snippet = sanitize_message(cleaned, max_length=100)
                snippets.append(snippet)

    # Drop useless "details redacted" placeholders so the summary
    # retains only meaningful content.
    useful = [s for s in snippets if s != "details redacted"]
    if not useful:
        logger.debug(
            CONTEXT_BUDGET_COMPACTION_FALLBACK,
            execution_id=execution_id,
            reason="no_useful_assistant_content_for_summary",
            archived_count=len(messages),
        )
        return f"[Archived {len(messages)} messages from earlier in the conversation.]"

    joined = "; ".join(useful)
    if len(joined) > _MAX_SUMMARY_CHARS:
        joined = joined[:_MAX_SUMMARY_CHARS] + "..."

    return f"[Archived {len(messages)} messages. Summary of prior work: {joined}]"
