"""Abstractive summarizer for sparse memory content.

Uses an LLM (via ``CompletionProvider``) to generate concise summaries
of conversational/narrative memory content.  Falls back to truncation
if the LLM call fails.
"""

import asyncio

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.models import MemoryEntry  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.consolidation import (
    DUAL_MODE_ABSTRACTIVE_FALLBACK,
    DUAL_MODE_ABSTRACTIVE_SUMMARY,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.errors import ProviderError
from synthorg.providers.models import ChatMessage, CompletionConfig
from synthorg.providers.protocol import CompletionProvider  # noqa: TC001

logger = get_logger(__name__)

_TRUNCATE_LENGTH = 200

_SYSTEM_PROMPT = (
    "You are a memory consolidation assistant. Summarize the following "
    "memory content concisely, preserving key decisions, events, and "
    "learnings. Be factual, specific, and brief."
)


def _truncate_fallback(content: str) -> str:
    """Truncate content as a fallback when LLM summarization fails."""
    if len(content) <= _TRUNCATE_LENGTH:
        return content
    return content[:_TRUNCATE_LENGTH] + "..."


class AbstractiveSummarizer:
    """LLM-based abstractive summarizer for sparse content.

    Uses a ``CompletionProvider`` to generate concise summaries of
    conversational/narrative memory content.  Falls back to truncation
    if the LLM call fails with a retryable error.

    Args:
        provider: Completion provider for LLM calls.
        model: Model identifier to use for summarization.
        max_summary_tokens: Maximum tokens for the summary response.
        temperature: Sampling temperature for summarization.

    Raises:
        ValueError: If ``model`` is empty or whitespace-only.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model: NotBlankStr,
        max_summary_tokens: int = 200,
        temperature: float = 0.3,
    ) -> None:
        if not model or not model.strip():
            msg = "model must be a non-blank string"
            raise ValueError(msg)
        self._provider = provider
        self._model = model
        self._config = CompletionConfig(
            temperature=temperature,
            max_tokens=max_summary_tokens,
        )

    async def summarize(self, content: str) -> str:
        """Generate an abstractive summary of the given content.

        Falls back to truncation if the LLM call fails with a
        retryable error or returns empty content.  Non-retryable
        provider errors (authentication, invalid model) propagate.

        Args:
            content: The sparse/conversational text to summarize.

        Returns:
            Summary text.
        """
        try:
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT),
                ChatMessage(role=MessageRole.USER, content=content),
            ]
            response = await self._provider.complete(
                messages,
                self._model,
                config=self._config,
            )
            if response.content and response.content.strip():
                logger.debug(
                    DUAL_MODE_ABSTRACTIVE_SUMMARY,
                    content_length=len(content),
                    summary_length=len(response.content),
                    model=self._model,
                )
                return response.content.strip()
        except MemoryError, RecursionError:
            raise
        except ProviderError as exc:
            if not exc.is_retryable:
                logger.warning(
                    DUAL_MODE_ABSTRACTIVE_FALLBACK,
                    content_length=len(content),
                    error=str(exc),
                    error_type=type(exc).__name__,
                    retryable=False,
                )
                raise
            logger.warning(
                DUAL_MODE_ABSTRACTIVE_FALLBACK,
                content_length=len(content),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return _truncate_fallback(content)
        except Exception as exc:
            logger.warning(
                DUAL_MODE_ABSTRACTIVE_FALLBACK,
                content_length=len(content),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return _truncate_fallback(content)

        # Fallback: empty/whitespace-only LLM response
        logger.debug(
            DUAL_MODE_ABSTRACTIVE_FALLBACK,
            content_length=len(content),
            reason="empty_response",
        )
        return _truncate_fallback(content)

    async def summarize_batch(
        self,
        entries: tuple[MemoryEntry, ...],
    ) -> tuple[tuple[NotBlankStr, str], ...]:
        """Summarize multiple entries concurrently.

        Each entry is summarized independently via ``asyncio.TaskGroup``.
        Failures for individual entries fall back to truncation without
        aborting the batch.

        Args:
            entries: Memory entries to summarize.

        Returns:
            Tuple of ``(entry_id, summary)`` pairs in input order.
        """
        if not entries:
            return ()

        results: dict[NotBlankStr, str] = {}
        async with asyncio.TaskGroup() as tg:
            tasks: dict[NotBlankStr, asyncio.Task[str]] = {}
            for entry in entries:
                tasks[entry.id] = tg.create_task(
                    self.summarize(entry.content),
                )

        for entry_id, task in tasks.items():
            results[entry_id] = task.result()

        return tuple((entry.id, results[entry.id]) for entry in entries)
