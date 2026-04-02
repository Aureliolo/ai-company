"""Intelligence/Accuracy pillar scoring strategy.

Blends existing CI (continuous integration) signal quality score with
LLM calibration data. When LLM calibration is disabled or unavailable,
falls back to CI quality alone with reduced confidence.
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
    EVAL_CALIBRATION_DRIFT_HIGH,
    EVAL_METRIC_SKIPPED,
    EVAL_PILLAR_INSUFFICIENT_DATA,
    EVAL_PILLAR_SCORED,
)

logger = get_logger(__name__)

_MAX_SCORE: float = 10.0
_NEUTRAL_SCORE: float = 5.0
_FULL_CONFIDENCE_DATA_POINTS: int = 10


class QualityBlendIntelligenceStrategy:
    """Intelligence scoring by blending CI quality with LLM calibration.

    Uses the existing ``overall_quality_score`` from the performance
    snapshot as the CI (continuous integration) signal, and blends it
    with the average LLM calibration score when available. High
    calibration drift reduces confidence.
    """

    @property
    def name(self) -> str:
        """Human-readable strategy name."""
        return "quality_blend_intelligence"

    @property
    def pillar(self) -> EvaluationPillar:
        """Which pillar this strategy scores."""
        return EvaluationPillar.INTELLIGENCE

    async def score(self, *, context: EvaluationContext) -> PillarScore:
        """Score intelligence from quality + calibration data.

        Args:
            context: Evaluation context.

        Returns:
            Intelligence pillar score.
        """
        cfg = context.config.intelligence
        ci_score = context.snapshot.overall_quality_score

        if ci_score is None:
            logger.info(
                EVAL_PILLAR_INSUFFICIENT_DATA,
                agent_id=context.agent_id,
                pillar=self.pillar.value,
                reason="no_quality_score",
            )
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=0,
                evaluated_at=context.now,
            )

        # Build enabled metrics list.
        metrics: list[tuple[str, float, bool]] = []
        if cfg.ci_quality_enabled:
            metrics.append(("ci_quality", cfg.ci_quality_weight, True))
        if cfg.llm_calibration_enabled:
            metrics.append(("llm_calibration", cfg.llm_calibration_weight, True))

        if not metrics:
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=0,
                evaluated_at=context.now,
            )

        weights = redistribute_weights(metrics)

        # Compute CI quality component.
        breakdown: list[tuple[str, float]] = []
        weighted_sum = 0.0
        data_points = len(context.task_records)

        if "ci_quality" in weights:
            breakdown.append(("ci_quality", round(ci_score, 4)))
            weighted_sum += ci_score * weights["ci_quality"]

        # Compute LLM calibration component.
        calibration_drift = 0.0
        if "llm_calibration" in weights:
            records = context.calibration_records
            if records:
                avg_llm = sum(r.llm_score for r in records) / len(records)
                breakdown.append(("llm_calibration", round(avg_llm, 4)))
                weighted_sum += avg_llm * weights["llm_calibration"]
                calibration_drift = sum(r.drift for r in records) / len(records)
                data_points += len(records)
            else:
                logger.debug(
                    EVAL_METRIC_SKIPPED,
                    agent_id=context.agent_id,
                    pillar=self.pillar.value,
                    metric="llm_calibration",
                    reason="no_calibration_records",
                )
                # Redistribute to CI quality only.
                weighted_sum = ci_score
                breakdown = [("ci_quality", round(ci_score, 4))]

        final_score = max(0.0, min(_MAX_SCORE, weighted_sum))

        # Confidence: base from data volume, reduced by drift.
        confidence = min(1.0, data_points / _FULL_CONFIDENCE_DATA_POINTS)
        if calibration_drift > context.config.calibration_drift_threshold:
            logger.info(
                EVAL_CALIBRATION_DRIFT_HIGH,
                agent_id=context.agent_id,
                pillar=self.pillar.value,
                drift=round(calibration_drift, 4),
                threshold=context.config.calibration_drift_threshold,
            )
            confidence *= max(
                0.1,
                1.0
                - (calibration_drift - context.config.calibration_drift_threshold)
                / _MAX_SCORE,
            )

        result = PillarScore(
            pillar=self.pillar,
            score=round(final_score, 4),
            confidence=round(confidence, 4),
            strategy_name=NotBlankStr(self.name),
            breakdown=tuple((NotBlankStr(k), v) for k, v in breakdown),
            data_point_count=data_points,
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
