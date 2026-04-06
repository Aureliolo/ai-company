"""Cross-provider uncertainty check for hallucination detection.

Sends the same prompt to multiple LLM providers and measures
agreement between responses using keyword overlap (Jaccard
similarity) and TF-IDF cosine similarity.  Low agreement produces
a low confidence score, signaling potential hallucination.

Design invariants:
    - No external dependencies beyond stdlib (TF-IDF via Counter).
    - Skips gracefully when fewer than ``min_providers`` are
      available (returns confidence 1.0).
    - Provider failures reduce ``provider_count``; if only one
      response remains, returns confidence 1.0 (insufficient data).
    - Each provider call is individually timeout-guarded.
"""

import asyncio
import math
import re
import time
from collections import Counter
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_UNCERTAINTY_CHECK_COMPLETE,
    SECURITY_UNCERTAINTY_CHECK_ERROR,
    SECURITY_UNCERTAINTY_CHECK_SKIPPED,
    SECURITY_UNCERTAINTY_CHECK_START,
    SECURITY_UNCERTAINTY_LOW_CONFIDENCE,
)
from synthorg.providers.models import ChatMessage, CompletionConfig
from synthorg.security.config import UncertaintyCheckConfig  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.config.schema import ProviderConfig
    from synthorg.providers.base import BaseCompletionProvider
    from synthorg.providers.registry import ProviderRegistry
    from synthorg.providers.routing.models import ResolvedModel
    from synthorg.providers.routing.resolver import ModelResolver

logger = get_logger(__name__)

# Word tokenization: split on non-alphanumeric characters.
_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")


# ── Models ────────────────────────────────────────────────────────


class UncertaintyResult(BaseModel):
    """Result of the cross-provider uncertainty check.

    Attributes:
        confidence_score: Agreement score between providers (0-1).
            1.0 = full agreement or check skipped, 0.0 = no overlap.
        provider_count: Number of providers that responded
            successfully.
        keyword_overlap: Jaccard similarity of word sets (0-1).
        embedding_similarity: TF-IDF cosine similarity (0-1).
        reason: Human-readable explanation of the result.
        check_duration_ms: Total time for the check.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    confidence_score: float = Field(ge=0.0, le=1.0)
    provider_count: int = Field(ge=0)
    keyword_overlap: float | None = Field(default=None, ge=0.0, le=1.0)
    embedding_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    reason: NotBlankStr
    check_duration_ms: float = Field(ge=0.0)


# ── Similarity functions (pure, no deps) ──────────────────────────


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase word set."""
    return set(_WORD_RE.findall(text.lower()))


def _compute_keyword_overlap(responses: list[str]) -> float:
    """Compute average pairwise Jaccard similarity of word sets.

    Args:
        responses: List of response texts.

    Returns:
        Average Jaccard similarity (0-1).  Returns 1.0 for a single
        response or empty responses.
    """
    if len(responses) < 2:  # noqa: PLR2004
        return 1.0

    word_sets = [_tokenize(r) for r in responses]

    # Handle all-empty case.
    if all(len(s) == 0 for s in word_sets):
        return 1.0

    total = 0.0
    pairs = 0
    for i in range(len(word_sets)):
        for j in range(i + 1, len(word_sets)):
            a, b = word_sets[i], word_sets[j]
            union = a | b
            if not union:
                total += 1.0
            else:
                total += len(a & b) / len(union)
            pairs += 1

    return total / pairs if pairs > 0 else 1.0


def _compute_tfidf_cosine_similarity(responses: list[str]) -> float:
    """Compute average pairwise cosine similarity of TF-IDF vectors.

    Uses pure Python (Counter + math.sqrt).  Each response is a
    document; IDF is computed across all responses.

    Args:
        responses: List of response texts.

    Returns:
        Average cosine similarity (0-1).  Returns 1.0 for a single
        response.
    """
    if len(responses) < 2:  # noqa: PLR2004
        return 1.0

    # Build term frequency per document.
    tf_docs = [Counter(_WORD_RE.findall(r.lower())) for r in responses]

    # Build vocabulary.
    vocab: set[str] = set()
    for tf in tf_docs:
        vocab.update(tf.keys())

    if not vocab:
        return 1.0

    n_docs = len(tf_docs)

    # Smoothed IDF: log(1 + N / (1 + df)).  The standard log(N/df)
    # zeros out terms shared by all documents, which breaks with
    # only 2 docs (every shared term gets IDF=0).
    df: Counter[str] = Counter()
    for tf in tf_docs:
        for word in tf:
            df[word] += 1
    idf = {word: math.log(1.0 + n_docs / (1.0 + df[word])) for word in vocab}

    # Build TF-IDF vectors.  When all documents contain the same
    # terms, IDF is zero for every term (log(N/N) = 0) and all
    # vectors are empty -- this means the documents are identical
    # (or near-identical), so return 1.0.
    tfidf_vecs: list[dict[str, float]] = []
    for tf in tf_docs:
        vec = {word: tf[word] * idf[word] for word in tf if idf[word] > 0}
        tfidf_vecs.append(vec)

    if all(len(v) == 0 for v in tfidf_vecs):
        return 1.0

    # Compute pairwise cosine similarity.
    total = 0.0
    pairs = 0
    for i in range(len(tfidf_vecs)):
        for j in range(i + 1, len(tfidf_vecs)):
            total += _cosine_sim(tfidf_vecs[i], tfidf_vecs[j])
            pairs += 1

    return total / pairs if pairs > 0 else 1.0


def _cosine_sim(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not a or not b:
        return 0.0

    dot = sum(a[k] * b[k] for k in a if k in b)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── UncertaintyChecker ────────────────────────────────────────────


class UncertaintyChecker:
    """Cross-provider uncertainty check for hallucination detection.

    Sends the same prompt to multiple providers, compares responses
    via keyword overlap and TF-IDF cosine similarity, and returns
    a confidence score.

    Args:
        provider_registry: Registry of provider drivers.
        provider_configs: Provider config dict for model selection.
        model_resolver: Resolver for multi-provider model lookup.
        config: Uncertainty check configuration.
    """

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        provider_configs: Mapping[str, ProviderConfig],
        model_resolver: ModelResolver,
        config: UncertaintyCheckConfig,
    ) -> None:
        self._registry = provider_registry
        self._configs = provider_configs
        self._resolver = model_resolver
        self._config = config

    async def check(self, prompt: str) -> UncertaintyResult:
        """Run cross-provider uncertainty check.

        Args:
            prompt: The prompt to send to multiple providers.

        Returns:
            An ``UncertaintyResult`` with the confidence score
            and similarity metrics.
        """
        start = time.monotonic()

        # Skip if no model ref configured.
        if self._config.model_ref is None:
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                SECURITY_UNCERTAINTY_CHECK_SKIPPED,
                reason="no model_ref configured",
            )
            return UncertaintyResult(
                confidence_score=1.0,
                provider_count=0,
                reason="Uncertainty check skipped: no model_ref configured",
                check_duration_ms=duration_ms,
            )

        # Resolve all provider variants for the model ref.
        candidates = self._resolver.resolve_all(self._config.model_ref)
        if len(candidates) < self._config.min_providers:
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                SECURITY_UNCERTAINTY_CHECK_SKIPPED,
                reason="insufficient providers",
                available=len(candidates),
                required=self._config.min_providers,
            )
            return UncertaintyResult(
                confidence_score=1.0,
                provider_count=0,
                reason=(
                    f"Uncertainty check skipped: {len(candidates)} "
                    f"provider(s) available, {self._config.min_providers} "
                    f"required"
                ),
                check_duration_ms=duration_ms,
            )

        logger.info(
            SECURITY_UNCERTAINTY_CHECK_START,
            model_ref=self._config.model_ref,
            provider_count=len(candidates),
        )

        # Send prompt to all providers in parallel.
        responses = await self._collect_responses(prompt, candidates)

        duration_ms = (time.monotonic() - start) * 1000

        # If only one response, insufficient for comparison.
        if len(responses) < 2:  # noqa: PLR2004
            logger.info(
                SECURITY_UNCERTAINTY_CHECK_SKIPPED,
                reason="insufficient successful responses",
                successful=len(responses),
            )
            return UncertaintyResult(
                confidence_score=1.0,
                provider_count=len(responses),
                reason=(
                    "Uncertainty check skipped: insufficient "
                    "successful responses for comparison"
                ),
                check_duration_ms=duration_ms,
            )

        # Compute similarity metrics.
        keyword_overlap = _compute_keyword_overlap(responses)
        embedding_sim = _compute_tfidf_cosine_similarity(responses)
        confidence = 0.6 * embedding_sim + 0.4 * keyword_overlap

        if confidence < self._config.low_confidence_threshold:
            logger.warning(
                SECURITY_UNCERTAINTY_LOW_CONFIDENCE,
                confidence_score=confidence,
                threshold=self._config.low_confidence_threshold,
                keyword_overlap=keyword_overlap,
                embedding_similarity=embedding_sim,
            )

        logger.info(
            SECURITY_UNCERTAINTY_CHECK_COMPLETE,
            confidence_score=confidence,
            provider_count=len(responses),
            keyword_overlap=keyword_overlap,
            embedding_similarity=embedding_sim,
            duration_ms=duration_ms,
        )

        return UncertaintyResult(
            confidence_score=confidence,
            provider_count=len(responses),
            keyword_overlap=keyword_overlap,
            embedding_similarity=embedding_sim,
            reason="Cross-provider uncertainty check complete",
            check_duration_ms=duration_ms,
        )

    async def _collect_responses(
        self,
        prompt: str,
        candidates: tuple[ResolvedModel, ...],
    ) -> list[str]:
        """Send prompt to all providers and collect responses.

        Individual provider failures are logged and skipped.
        """
        from synthorg.providers.enums import MessageRole  # noqa: PLC0415

        messages = [
            ChatMessage(role=MessageRole.USER, content=prompt),
        ]
        config = CompletionConfig(temperature=0.0, max_tokens=512)

        results: list[str] = []

        async def _call_provider(candidate: ResolvedModel) -> str | None:
            driver: BaseCompletionProvider = self._registry.get(
                candidate.provider_name,
            )
            try:
                response = await asyncio.wait_for(
                    driver.complete(
                        messages,
                        candidate.model_id,
                        config=config,
                    ),
                    timeout=self._config.timeout_seconds,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    SECURITY_UNCERTAINTY_CHECK_ERROR,
                    provider=candidate.provider_name,
                    model=candidate.model_id,
                )
                return None
            else:
                return response.content or ""

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_call_provider(c)) for c in candidates]

        for task in tasks:
            result = task.result()
            if result is not None:
                results.append(result)

        return results
