"""Composite quality scoring strategy (D2 Layers 1+2+3).

Combines CI signal (Layer 1), LLM judge (Layer 2), and human
override (Layer 3) into a single ``QualityScoringStrategy``.
Human override has the highest priority and short-circuits
the other layers.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.hr.performance.models import QualityScoreResult
from synthorg.observability import get_logger
from synthorg.observability.events.performance import (
    PERF_COMPOSITE_SCORED,
    PERF_QUALITY_OVERRIDE_APPLIED,
)

if TYPE_CHECKING:
    from synthorg.core.task import AcceptanceCriterion
    from synthorg.hr.performance.models import TaskMetricRecord
    from synthorg.hr.performance.quality_override_store import (
        QualityOverrideStore,
    )
    from synthorg.hr.performance.quality_protocol import QualityScoringStrategy

logger = get_logger(__name__)


class CompositeQualityStrategy:
    """Composite quality scoring combining multiple layers.

    Evaluation order:
        1. Human override (Layer 3) -- if active, return immediately.
        2. LLM judge (Layer 2) -- if configured and succeeds.
        3. CI signal (Layer 1) -- always runs.

    When both CI and LLM layers succeed, scores are combined using
    configurable weights.  When only CI succeeds (LLM not configured
    or failed), the CI score is used directly with reduced confidence.

    Args:
        ci_strategy: CI signal scoring strategy (Layer 1).
        llm_strategy: LLM judge scoring strategy (Layer 2, optional).
        override_store: Quality override store (Layer 3, optional).
        ci_weight: Weight for CI signal (default 0.4).
        llm_weight: Weight for LLM judge (default 0.6).
    """

    def __init__(
        self,
        *,
        ci_strategy: QualityScoringStrategy,
        llm_strategy: QualityScoringStrategy | None = None,
        override_store: QualityOverrideStore | None = None,
        ci_weight: float = 0.4,
        llm_weight: float = 0.6,
    ) -> None:
        if ci_weight < 0.0 or llm_weight < 0.0:
            msg = (
                f"Weights must be non-negative, got "
                f"ci_weight={ci_weight}, llm_weight={llm_weight}"
            )
            raise ValueError(msg)
        self._ci_strategy = ci_strategy
        self._llm_strategy = llm_strategy
        self._override_store = override_store
        self._ci_weight = ci_weight
        self._llm_weight = llm_weight

    @property
    def name(self) -> str:
        """Human-readable strategy name."""
        return "composite"

    async def score(
        self,
        *,
        agent_id: NotBlankStr,
        task_id: NotBlankStr,
        task_result: TaskMetricRecord,
        acceptance_criteria: tuple[AcceptanceCriterion, ...],
    ) -> QualityScoreResult:
        """Score task quality using the composite layer stack.

        Args:
            agent_id: Agent who completed the task.
            task_id: Task identifier.
            task_result: Recorded task metrics.
            acceptance_criteria: Criteria to evaluate against.

        Returns:
            Quality score result with breakdown and confidence.
        """
        # Layer 3: Human override (highest priority).
        override_result = self._check_override(agent_id)
        if override_result is not None:
            return override_result

        # Layer 1: CI signal (always runs).
        ci_result = await self._ci_strategy.score(
            agent_id=agent_id,
            task_id=task_id,
            task_result=task_result,
            acceptance_criteria=acceptance_criteria,
        )

        # Layer 2: LLM judge (optional).
        llm_result = await self._try_llm(
            agent_id=agent_id,
            task_id=task_id,
            task_result=task_result,
            acceptance_criteria=acceptance_criteria,
        )

        # Combine layers.
        return self._combine(ci_result, llm_result)

    def _check_override(
        self,
        agent_id: NotBlankStr,
    ) -> QualityScoreResult | None:
        """Check for an active human override.

        Returns:
            Override result if active, ``None`` otherwise.
        """
        if self._override_store is None:
            return None

        override = self._override_store.get_active_override(agent_id)
        if override is None:
            return None

        logger.info(
            PERF_QUALITY_OVERRIDE_APPLIED,
            agent_id=agent_id,
            score=override.score,
            applied_by=override.applied_by,
        )
        return QualityScoreResult(
            score=override.score,
            strategy_name=NotBlankStr("human_override"),
            breakdown=(("human_override", override.score),),
            confidence=1.0,
        )

    async def _try_llm(
        self,
        *,
        agent_id: NotBlankStr,
        task_id: NotBlankStr,
        task_result: TaskMetricRecord,
        acceptance_criteria: tuple[AcceptanceCriterion, ...],
    ) -> QualityScoreResult | None:
        """Attempt LLM judge scoring.

        Returns ``None`` if the LLM strategy is not configured, fails,
        or returns zero confidence.
        """
        if self._llm_strategy is None:
            return None

        try:
            result = await self._llm_strategy.score(
                agent_id=agent_id,
                task_id=task_id,
                task_result=task_result,
                acceptance_criteria=acceptance_criteria,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                PERF_COMPOSITE_SCORED,
                agent_id=agent_id,
                task_id=task_id,
                note="llm_strategy_failed",
                exc_info=True,
            )
            return None

        # Zero confidence means the LLM judge failed gracefully.
        if result.confidence == 0.0:
            return None

        return result

    def _combine(
        self,
        ci_result: QualityScoreResult,
        llm_result: QualityScoreResult | None,
    ) -> QualityScoreResult:
        """Combine CI and optional LLM scores.

        When both layers are available, applies weighted combination.
        When only CI is available, uses the CI score directly with
        reduced confidence.
        """
        if llm_result is not None:
            # Weighted combination.
            combined_score = (
                ci_result.score * self._ci_weight + llm_result.score * self._llm_weight
            )
            combined_score = round(
                max(0.0, min(10.0, combined_score)),
                4,
            )
            confidence = round(
                min(ci_result.confidence, llm_result.confidence) * 0.9,
                4,
            )
            breakdown: tuple[tuple[NotBlankStr, float], ...] = (
                (NotBlankStr("ci_signal"), ci_result.score),
                (NotBlankStr("llm_judge"), llm_result.score),
            )
        else:
            # CI-only fallback.
            combined_score = round(ci_result.score, 4)
            confidence = round(ci_result.confidence * 0.7, 4)
            breakdown = ((NotBlankStr("ci_signal"), ci_result.score),)

        result = QualityScoreResult(
            score=combined_score,
            strategy_name=NotBlankStr(self.name),
            breakdown=breakdown,
            confidence=confidence,
        )

        logger.debug(
            PERF_COMPOSITE_SCORED,
            score=result.score,
            confidence=result.confidence,
            layers=len(breakdown),
        )
        return result
