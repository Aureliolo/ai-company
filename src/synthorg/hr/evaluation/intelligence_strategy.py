"""Intelligence/Accuracy pillar scoring strategy.

Blends existing CI (continuous integration) signal quality score with
LLM calibration data. When LLM calibration is disabled or unavailable,
falls back to CI quality alone.

Note: LLM calibration records originate from the collaboration scoring
pipeline; their LLM-assigned scores serve as a proxy for reasoning
quality, measuring how closely the LLM's independent assessment aligns
with behavioral signals.
"""

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
    EVAL_CALIBRATION_DRIFT_HIGH,
    EVAL_METRIC_SKIPPED,
    EVAL_PILLAR_INSUFFICIENT_DATA,
    EVAL_PILLAR_SCORED,
)

logger = get_logger(__name__)


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
        ci_score = context.snapshot.overall_quality_score

        if ci_score is None:
            return self._neutral(context, reason="no_quality_score")

        available, data_points, drift = self._collect_metrics(
            ci_score,
            context,
        )
        if not available:
            return self._neutral(context, reason="no_enabled_metrics")

        return self._build_result(available, data_points, drift, context)

    def _collect_metrics(
        self,
        ci_score: float,
        context: EvaluationContext,
    ) -> tuple[list[tuple[str, float, float]], int, float]:
        """Gather enabled metrics with data.

        Returns:
            Tuple of (available_metrics, data_points, calibration_drift).
        """
        available: list[tuple[str, float, float]] = []
        data_points = len(context.task_records)
        calibration_drift = 0.0

        if context.config.intelligence.ci_quality_enabled:
            available.append(
                (
                    "ci_quality",
                    context.config.intelligence.ci_quality_weight,
                    ci_score,
                )
            )

        if context.config.intelligence.llm_calibration_enabled:
            records = context.calibration_records
            if records:
                avg_llm = sum(r.llm_score for r in records) / len(records)
                available.append(
                    (
                        "llm_calibration",
                        context.config.intelligence.llm_calibration_weight,
                        avg_llm,
                    )
                )
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

        return available, data_points, calibration_drift

    def _build_result(
        self,
        available: list[tuple[str, float, float]],
        data_points: int,
        calibration_drift: float,
        context: EvaluationContext,
    ) -> PillarScore:
        """Aggregate available metrics into a pillar score."""
        weights = redistribute_weights(
            [(name, w, True) for name, w, _ in available],
        )
        scores = {name: s for name, _, s in available}
        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )

        confidence = self._compute_confidence(
            data_points,
            calibration_drift,
            context,
        )

        result = PillarScore(
            pillar=self.pillar,
            score=round(final_score, 4),
            confidence=round(confidence, 4),
            strategy_name=NotBlankStr(self.name),
            breakdown=breakdown,
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

    def _compute_confidence(
        self,
        data_points: int,
        calibration_drift: float,
        context: EvaluationContext,
    ) -> float:
        """Compute confidence, reduced by high calibration drift."""
        confidence = min(1.0, data_points / FULL_CONFIDENCE_DATA_POINTS)
        threshold = context.config.calibration_drift_threshold
        if calibration_drift > threshold:
            logger.info(
                EVAL_CALIBRATION_DRIFT_HIGH,
                agent_id=context.agent_id,
                pillar=self.pillar.value,
                drift=round(calibration_drift, 4),
                threshold=threshold,
            )
            confidence *= max(
                0.1,
                1.0 - (calibration_drift - threshold) / MAX_SCORE,
            )
        return confidence

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
