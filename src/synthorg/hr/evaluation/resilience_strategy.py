"""Reliability/Resilience pillar scoring strategy.

Evaluates success rate, failure recovery, quality consistency,
and success streak metrics. Each metric can be independently
toggled via ``ResilienceConfig``.
"""

from synthorg.core.types import NotBlankStr
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

logger = get_logger(__name__)

_MAX_SCORE: float = 10.0
_NEUTRAL_SCORE: float = 5.0
_FULL_CONFIDENCE_DATA_POINTS: int = 10


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
        cfg = context.config.resilience
        rm = context.resilience_metrics

        if rm is None or rm.total_tasks == 0:
            logger.info(
                EVAL_PILLAR_INSUFFICIENT_DATA,
                agent_id=context.agent_id,
                pillar=self.pillar.value,
                reason="no_resilience_metrics",
            )
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=0,
                evaluated_at=context.now,
            )

        # Build enabled metrics.
        enabled_metrics: list[tuple[str, float, bool]] = []
        scores: dict[str, float] = {}

        if cfg.success_rate_enabled:
            success_rate = (rm.total_tasks - rm.failed_tasks) / rm.total_tasks
            scores["success_rate"] = success_rate * _MAX_SCORE
            enabled_metrics.append(
                ("success_rate", cfg.success_rate_weight, True),
            )

        if cfg.recovery_rate_enabled:
            if rm.failed_tasks > 0:
                recovery = min(1.0, rm.recovered_tasks / rm.failed_tasks)
            else:
                recovery = 1.0  # No failures = perfect recovery.
            scores["recovery_rate"] = recovery * _MAX_SCORE
            enabled_metrics.append(
                ("recovery_rate", cfg.recovery_rate_weight, True),
            )

        if cfg.consistency_enabled:
            if rm.quality_score_stddev is not None:
                consistency = max(
                    0.0,
                    _MAX_SCORE - rm.quality_score_stddev * cfg.consistency_k,
                )
            else:
                consistency = _NEUTRAL_SCORE
            scores["consistency"] = consistency
            enabled_metrics.append(
                ("consistency", cfg.consistency_weight, True),
            )

        if cfg.streak_enabled:
            streak = min(
                _MAX_SCORE,
                rm.current_success_streak * cfg.streak_factor,
            )
            scores["streak"] = streak
            enabled_metrics.append(
                ("streak", cfg.streak_weight, True),
            )

        if not enabled_metrics:
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=rm.total_tasks,
                evaluated_at=context.now,
            )

        weights = redistribute_weights(enabled_metrics)
        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(_MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )
        confidence = min(1.0, rm.total_tasks / _FULL_CONFIDENCE_DATA_POINTS)

        result = PillarScore(
            pillar=self.pillar,
            score=round(final_score, 4),
            confidence=round(confidence, 4),
            strategy_name=NotBlankStr(self.name),
            breakdown=breakdown,
            data_point_count=rm.total_tasks,
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
