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
from synthorg.engine.token_estimation import (
    DefaultTokenEstimator,
    PromptTokenEstimator,
)
from synthorg.observability import get_logger
from synthorg.observability.events.context_budget import (
    CONTEXT_BUDGET_COMPACTION_COMPLETED,
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

    # Keep system message (index 0) and recent messages.
    # preserve_recent_turns * 2 for user+assistant pairs.
    preserve_count = config.preserve_recent_turns * 2
    if preserve_count >= len(conversation) - 1:
        logger.debug(
            CONTEXT_BUDGET_COMPACTION_SKIPPED,
            execution_id=ctx.execution_id,
            reason="nothing_to_archive",
            preserve_count=preserve_count,
            message_count=len(conversation),
        )
        return None

    system_msg = conversation[0]
    archivable = conversation[1:-preserve_count]
    recent = conversation[-preserve_count:]

    summary_text = _build_summary(archivable)
    summary_msg = ChatMessage(
        role=MessageRole.SYSTEM,
        content=summary_text,
    )
    summary_tokens = estimator.estimate_tokens(summary_text)

    compressed_conversation = (system_msg, summary_msg, *recent)

    # Build compression metadata.
    prior = ctx.compression_metadata
    compactions_count = prior.compactions_performed + 1 if prior is not None else 1
    prior_archived = prior.archived_turns if prior is not None else 0

    metadata = CompressionMetadata(
        compression_point=ctx.turn_count,
        archived_turns=prior_archived + len(archivable),
        summary_tokens=summary_tokens,
        compactions_performed=compactions_count,
    )

    # Re-estimate fill with compressed conversation.  This counts
    # conversation tokens only — system prompt and tool overhead are
    # excluded because the compaction callback does not have access to
    # those values.  The execution loop's next call to
    # ``update_context_fill`` will restore the full estimate.
    new_fill = estimator.estimate_conversation_tokens(
        compressed_conversation,
    )

    logger.info(
        CONTEXT_BUDGET_COMPACTION_COMPLETED,
        execution_id=ctx.execution_id,
        original_messages=len(conversation),
        compacted_messages=len(compressed_conversation),
        archived_turns=len(archivable),
        summary_tokens=summary_tokens,
        compactions_total=compactions_count,
    )

    return ctx.with_compression(
        metadata,
        compressed_conversation,
        new_fill,
    )


def _build_summary(messages: tuple[ChatMessage, ...]) -> str:
    """Build a simple text summary from archived messages.

    Concatenates assistant message content snippets into a summary
    paragraph, capped at ``_MAX_SUMMARY_CHARS``.

    Args:
        messages: The archived messages to summarize.

    Returns:
        Summary text describing the archived conversation.
    """
    snippets: list[str] = []
    for msg in messages:
        if msg.role == MessageRole.ASSISTANT and msg.content:
            snippet = msg.content[:100].replace("\n", " ").strip()
            if snippet:
                snippets.append(snippet)

    if not snippets:
        logger.debug(
            CONTEXT_BUDGET_COMPACTION_SKIPPED,
            reason="no_assistant_content",
            archived_count=len(messages),
        )
        return f"[Archived {len(messages)} messages from earlier in the conversation.]"

    joined = "; ".join(snippets)
    if len(joined) > _MAX_SUMMARY_CHARS:
        joined = joined[:_MAX_SUMMARY_CHARS] + "..."

    return f"[Archived {len(messages)} messages. Summary of prior work: {joined}]"
