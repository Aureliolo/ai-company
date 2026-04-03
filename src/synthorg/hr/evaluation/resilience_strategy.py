"""Reliability/Resilience pillar scoring strategy.

Evaluates success rate, failure recovery, quality consistency,
and success streak metrics. Each metric can be independently
toggled via ``ResilienceConfig``.
"""

from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.hr.evaluation.constants import (
    FULL_CONFIDENCE_DATA_POINTS,
    MAX_SCORE,
    NEUTRAL_SCORE,
)
from synthorg.hr.evaluation.enums import EvaluationPillar
from synthorg.hr.evaluation.models import (
    EvaluationContext,
    PillarScore,
    redistribute_weights,
)
from synthorg.observability import get_logger
from synthorg.observability.events.evaluation import (
    EVAL_PILLAR_INSUFFICIENT_DATA,
    EVAL_PILLAR_SCORED,
)

if TYPE_CHECKING:
    from synthorg.hr.evaluation.config import ResilienceConfig
    from synthorg.hr.evaluation.models import ResilienceMetrics

logger = get_logger(__name__)


class TaskBasedResilienceStrategy:
    """Resilience scoring from task execution patterns.

    Components (all toggleable):
        - success_rate: Task success rate scaled to 0-10.
        - recovery_rate: Ratio of recovered-after-failure tasks.
        - consistency: Quality score penalized linearly by stddev.
        - streak: Current success streak bonus.
    """

    @property
    def name(self) -> str:
        """Human-readable strategy name."""
        return "task_based_resilience"

    @property
    def pillar(self) -> EvaluationPillar:
        """Which pillar this strategy scores."""
        return EvaluationPillar.RESILIENCE

    async def score(self, *, context: EvaluationContext) -> PillarScore:
        """Score resilience from task execution metrics.

        Args:
            context: Evaluation context.

        Returns:
            Resilience pillar score.
        """
        rm = context.resilience_metrics

        if rm is None or rm.total_tasks == 0:
            return self._neutral(context, reason="no_resilience_metrics")

        scores, enabled = self._collect_metrics(
            context.config.resilience,
            rm,
        )

        if not enabled:
            return self._neutral(
                context,
                reason="no_enabled_metrics",
            )

        return self._build_result(scores, enabled, rm.total_tasks, context)

    @staticmethod
    def _collect_metrics(
        cfg: ResilienceConfig,
        rm: ResilienceMetrics,
    ) -> tuple[dict[str, float], list[tuple[str, float, bool]]]:
        """Gather enabled resilience metrics.

        Returns:
            Tuple of (scores, enabled_metrics).
        """
        enabled: list[tuple[str, float, bool]] = []
        scores: dict[str, float] = {}

        if cfg.success_rate_enabled:
            rate = (rm.total_tasks - rm.failed_tasks) / rm.total_tasks
            scores["success_rate"] = rate * MAX_SCORE
            enabled.append(("success_rate", cfg.success_rate_weight, True))

        if cfg.recovery_rate_enabled:
            if rm.failed_tasks > 0:
                recovery = min(1.0, rm.recovered_tasks / rm.failed_tasks)
            else:
                recovery = 1.0  # No failures = perfect recovery.
            scores["recovery_rate"] = recovery * MAX_SCORE
            enabled.append(("recovery_rate", cfg.recovery_rate_weight, True))

        if cfg.consistency_enabled:
            if rm.quality_score_stddev is not None:
                val = max(
                    0.0,
                    MAX_SCORE - rm.quality_score_stddev * cfg.consistency_k,
                )
            else:
                val = NEUTRAL_SCORE
            scores["consistency"] = val
            enabled.append(("consistency", cfg.consistency_weight, True))

        if cfg.streak_enabled:
            scores["streak"] = min(
                MAX_SCORE,
                rm.current_success_streak * cfg.streak_factor,
            )
            enabled.append(("streak", cfg.streak_weight, True))

        return scores, enabled

    def _build_result(
        self,
        scores: dict[str, float],
        enabled: list[tuple[str, float, bool]],
        total_tasks: int,
        context: EvaluationContext,
    ) -> PillarScore:
        """Aggregate enabled metrics into a pillar score."""
        weights = redistribute_weights(enabled)
        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )
        confidence = min(1.0, total_tasks / FULL_CONFIDENCE_DATA_POINTS)

        result = PillarScore(
            pillar=self.pillar,
            score=round(final_score, 4),
            confidence=round(confidence, 4),
            strategy_name=NotBlankStr(self.name),
            breakdown=breakdown,
            data_point_count=total_tasks,
            evaluated_at=context.now,
        )

        logger.debug(
            EVAL_PILLAR_SCORED,
            agent_id=context.agent_id,
            pillar=self.pillar.value,
            score=result.score,
            confidence=result.confidence,
        )
        return result

    def _neutral(
        self,
        context: EvaluationContext,
        *,
        reason: str,
    ) -> PillarScore:
        """Return a neutral score with zero confidence."""
        logger.info(
            EVAL_PILLAR_INSUFFICIENT_DATA,
            agent_id=context.agent_id,
            pillar=self.pillar.value,
            reason=reason,
        )
        return PillarScore(
            pillar=self.pillar,
            score=NEUTRAL_SCORE,
            confidence=0.0,
            strategy_name=NotBlankStr(self.name),
            data_point_count=0,
            evaluated_at=context.now,
        )
