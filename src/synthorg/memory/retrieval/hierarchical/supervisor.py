"""Supervisor router -- LLM-based query routing and retry evaluation.

Uses a small-tier model to decide which retrieval workers to invoke
and whether to retry with corrected queries when results are poor.
"""

import builtins
import json
from typing import TYPE_CHECKING

from synthorg.memory.retrieval.hierarchical.models import (
    RetrievalRetryCorrection,
    WorkerRoutingDecision,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_HIERARCHICAL_RETRY,
    MEMORY_HIERARCHICAL_ROUTING,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage
from synthorg.providers.resilience.errors import RetryExhaustedError

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.retrieval.models import (
        FinalRetrievalResult,
        RetrievalQuery,
    )
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)

_VALID_WORKERS = frozenset({"semantic", "episodic", "procedural"})

_ROUTING_SYSTEM_PROMPT = """\
You are a memory retrieval router. Given a query, decide which memory \
workers to invoke. Available workers:
- semantic: Full-spectrum hybrid search across all memory types
- episodic: Recent events and decisions (time-windowed)
- procedural: Skills, patterns, and how-to knowledge

Respond with JSON: {{"workers": ["worker1", ...], "reason": "..."}}
Select 1 to {max_workers} workers. Prefer "semantic" for broad queries. \
Use "episodic" for time-sensitive questions and "procedural" for how-to.
"""

_RETRY_SYSTEM_PROMPT = """\
You are evaluating retrieval quality. The original query returned \
{count} results with an average score of {avg_score:.2f}.

Decide if a retry is needed. If so, suggest ONE of:
- A corrected query (broader or more specific)
- An alternative strategy: "semantic_only", "episodic_only", or "skip"

Respond with JSON: {{"retry": true/false, "corrected_query": "..." \
or null, "alternative_strategy": "..." or null, "reason": "..."}}
"""

_QUALITY_THRESHOLD = 0.3
_DEFAULT_FALLBACK_WORKERS = ("semantic",)


class SupervisorRouter:
    """LLM-based routing supervisor for hierarchical retrieval.

    Args:
        provider: Completion provider for LLM calls.
        model: Model identifier (typically small-tier).
        max_workers_per_query: Maximum workers per query.
        reflective_retry_enabled: Whether retry evaluation is active.
        max_retry_count: Maximum retry attempts.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model: NotBlankStr,
        max_workers_per_query: int = 2,
        reflective_retry_enabled: bool = True,
        max_retry_count: int = 2,
    ) -> None:
        self._provider = provider
        self._model = model
        self._max_workers = max_workers_per_query
        self._retry_enabled = reflective_retry_enabled
        self._max_retries = max_retry_count

    @property
    def reflective_retry_enabled(self) -> bool:
        """Whether reflective retry is active."""
        return self._retry_enabled

    @property
    def max_retry_count(self) -> int:
        """Maximum retry attempts."""
        return self._max_retries

    async def route(
        self,
        query: RetrievalQuery,
    ) -> WorkerRoutingDecision:
        """Decide which workers to invoke for a query.

        Falls back to ``("semantic",)`` on any LLM failure.

        Args:
            query: The retrieval query to route.

        Returns:
            Routing decision with selected workers and reason.
        """
        try:
            return await self._route_via_llm(query)
        except builtins.MemoryError, RecursionError:
            raise
        except RetryExhaustedError:
            raise
        except Exception as exc:
            logger.warning(
                MEMORY_HIERARCHICAL_ROUTING,
                action="fallback",
                reason=f"LLM routing failed: {exc}",
                query_text=query.text[:80],
            )
            return WorkerRoutingDecision(
                selected_workers=_DEFAULT_FALLBACK_WORKERS,
                reason=f"LLM routing fallback: {exc}",
            )

    async def evaluate_for_retry(
        self,
        query: RetrievalQuery,
        result: FinalRetrievalResult,
    ) -> RetrievalRetryCorrection | None:
        """Evaluate result quality and suggest retry correction.

        Returns ``None`` when results are sufficient or retry is
        disabled.  Falls back to ``None`` on LLM failure.

        Args:
            query: The original retrieval query.
            result: The current retrieval result to evaluate.

        Returns:
            Retry correction if warranted, else ``None``.
        """
        if not self._retry_enabled:
            return None
        if not result.candidates:
            return RetrievalRetryCorrection(
                alternative_strategy="semantic_only",
                reason="No results returned, falling back to semantic",
            )
        avg_score = sum(c.combined_score for c in result.candidates) / len(
            result.candidates
        )
        if avg_score >= _QUALITY_THRESHOLD:
            return None
        try:
            return await self._evaluate_via_llm(query, result)
        except builtins.MemoryError, RecursionError:
            raise
        except RetryExhaustedError:
            raise
        except Exception as exc:
            logger.warning(
                MEMORY_HIERARCHICAL_RETRY,
                action="eval_failed",
                reason=f"LLM retry evaluation failed: {exc}",
            )
            return None

    async def _route_via_llm(
        self,
        query: RetrievalQuery,
    ) -> WorkerRoutingDecision:
        """Call LLM for routing decision."""
        system_prompt = _ROUTING_SYSTEM_PROMPT.format(
            max_workers=self._max_workers,
        )
        messages: list[ChatMessage] = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=query.text),
        ]
        response = await self._provider.complete(
            messages,
            self._model,
        )
        if response.content is None:
            msg = "LLM returned empty content for routing"
            raise ValueError(msg)
        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError as exc:
            logger.warning(
                MEMORY_HIERARCHICAL_ROUTING,
                action="json_parse_failed",
                raw_content=response.content[:200],
                error=str(exc),
            )
            raise
        workers = tuple(
            w for w in parsed.get("workers", ["semantic"]) if w in _VALID_WORKERS
        )[: self._max_workers]
        if not workers:
            workers = _DEFAULT_FALLBACK_WORKERS
        reason = parsed.get("reason", "LLM routing decision")
        logger.info(
            MEMORY_HIERARCHICAL_ROUTING,
            action="decided",
            workers=list(workers),
            reason=reason,
            query_text=query.text[:80],
        )
        return WorkerRoutingDecision(
            selected_workers=workers,
            reason=reason,
        )

    async def _evaluate_via_llm(
        self,
        query: RetrievalQuery,
        result: FinalRetrievalResult,
    ) -> RetrievalRetryCorrection | None:
        """Call LLM for retry evaluation."""
        avg_score = sum(c.combined_score for c in result.candidates) / max(
            len(result.candidates), 1
        )
        system_prompt = _RETRY_SYSTEM_PROMPT.format(
            count=len(result.candidates),
            avg_score=avg_score,
        )
        user_content = (
            f"Original query: {query.text}\n"
            f"Results: {len(result.candidates)} candidates, "
            f"avg score: {avg_score:.2f}"
        )
        messages: list[ChatMessage] = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_content),
        ]
        response = await self._provider.complete(
            messages,
            self._model,
        )
        if response.content is None:
            return None
        parsed = json.loads(response.content)
        if not parsed.get("retry", False):
            return None

        corrected_query = None
        corrected_text = parsed.get("corrected_query")
        if corrected_text:
            corrected_query = query.model_copy(
                update={"text": corrected_text},
            )

        alt_strategy = parsed.get("alternative_strategy")
        if alt_strategy and alt_strategy not in {
            "semantic_only",
            "episodic_only",
            "skip",
        }:
            alt_strategy = None

        reason = parsed.get("reason", "LLM suggested retry")
        logger.info(
            MEMORY_HIERARCHICAL_RETRY,
            action="correction",
            has_corrected_query=corrected_query is not None,
            alternative_strategy=alt_strategy,
            reason=reason,
        )
        return RetrievalRetryCorrection(
            corrected_query=corrected_query,
            alternative_strategy=alt_strategy,
            reason=reason,
        )
