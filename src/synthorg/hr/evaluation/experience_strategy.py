"""User Experience pillar scoring strategy.

Weighted average of interaction feedback ratings. Each rating
dimension can be independently toggled via ``ExperienceConfig``.
None ratings and disabled metrics have their weight redistributed.
"""

from synthorg.core.types import NotBlankStr
from synthorg.hr.evaluation.constants import MAX_SCORE, NEUTRAL_SCORE
from synthorg.hr.evaluation.enums import EvaluationPillar
from synthorg.hr.evaluation.models import (
    EvaluationContext,
    InteractionFeedback,
    PillarScore,
    redistribute_weights,
)
from synthorg.observability import get_logger
from synthorg.observability.events.evaluation import (
    EVAL_PILLAR_INSUFFICIENT_DATA,
    EVAL_PILLAR_SCORED,
)

logger = get_logger(__name__)

# Full confidence at min_feedback_count * this multiplier.
_FULL_CONFIDENCE_FEEDBACK_MULTIPLIER: int = 3

# Rating field accessors keyed by metric name.
_RATING_FIELDS: dict[str, str] = {
    "clarity": "clarity_rating",
    "tone": "tone_rating",
    "helpfulness": "helpfulness_rating",
    "trust": "trust_rating",
    "satisfaction": "satisfaction_rating",
}


def _avg_rating(
    feedback: tuple[InteractionFeedback, ...],
    field: str,
) -> float | None:
    """Compute average of a feedback rating field, ignoring None values."""
    vals: list[float] = [
        getattr(fb, field) for fb in feedback if getattr(fb, field) is not None
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


class FeedbackBasedUxStrategy:
    """UX scoring from interaction feedback ratings.

    Evaluates 5 feedback dimensions (all toggleable):
        - clarity: How clear the agent's output was.
        - tone: How appropriate the tone was.
        - helpfulness: How helpful the output was.
        - trust: How trustworthy the agent felt.
        - satisfaction: Overall satisfaction.

    Feedback ratings are 0.0-1.0; scaled to 0.0-10.0 for scoring.
    None ratings have weight redistributed to available ratings.
    """

    @property
    def name(self) -> str:
        """Human-readable strategy name."""
        return "feedback_based_ux"

    @property
    def pillar(self) -> EvaluationPillar:
        """Which pillar this strategy scores."""
        return EvaluationPillar.EXPERIENCE

    async def score(self, *, context: EvaluationContext) -> PillarScore:
        """Score UX from interaction feedback.

        Args:
            context: Evaluation context.

        Returns:
            Experience pillar score.
        """
        cfg = context.config.experience
        feedback = context.feedback

        if len(feedback) < cfg.min_feedback_count:
            return self._neutral(
                context,
                reason="insufficient_feedback",
                count=len(feedback),
                min_required=cfg.min_feedback_count,
            )

        available = self._collect_metrics(cfg, feedback)

        if not available:
            return self._neutral(
                context,
                reason="no_enabled_metrics_with_data",
            )

        return self._build_result(available, feedback, context)

    @staticmethod
    def _collect_metrics(
        cfg: object,
        feedback: tuple[InteractionFeedback, ...],
    ) -> list[tuple[str, float, float]]:
        """Gather enabled metrics with data.

        Returns:
            List of (name, weight, avg_score) tuples.
        """
        from synthorg.hr.evaluation.config import ExperienceConfig  # noqa: PLC0415

        assert isinstance(cfg, ExperienceConfig)  # noqa: S101

        metric_defs = [
            ("clarity", cfg.clarity_enabled, cfg.clarity_weight),
            ("tone", cfg.tone_enabled, cfg.tone_weight),
            ("helpfulness", cfg.helpfulness_enabled, cfg.helpfulness_weight),
            ("trust", cfg.trust_enabled, cfg.trust_weight),
            ("satisfaction", cfg.satisfaction_enabled, cfg.satisfaction_weight),
        ]

        available: list[tuple[str, float, float]] = []
        for metric_name, enabled, weight in metric_defs:
            if not enabled:
                continue
            avg = _avg_rating(feedback, _RATING_FIELDS[metric_name])
            if avg is not None:
                available.append((metric_name, weight, avg * MAX_SCORE))
        return available

    def _build_result(
        self,
        available: list[tuple[str, float, float]],
        feedback: tuple[InteractionFeedback, ...],
        context: EvaluationContext,
    ) -> PillarScore:
        """Aggregate available metrics into a pillar score."""
        cfg = context.config.experience
        weights = redistribute_weights(
            [(name, w, True) for name, w, _ in available],
        )
        scores = {name: s for name, _, s in available}

        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )
        confidence = min(
            1.0,
            len(feedback)
            / (cfg.min_feedback_count * _FULL_CONFIDENCE_FEEDBACK_MULTIPLIER),
        )

        result = PillarScore(
            pillar=self.pillar,
            score=round(final_score, 4),
            confidence=round(confidence, 4),
            strategy_name=NotBlankStr(self.name),
            breakdown=breakdown,
            data_point_count=len(feedback),
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
        **kwargs: object,
    ) -> PillarScore:
        """Return a neutral score with zero confidence."""
        logger.info(
            EVAL_PILLAR_INSUFFICIENT_DATA,
            agent_id=context.agent_id,
            pillar=self.pillar.value,
            reason=reason,
            **kwargs,
        )
        return PillarScore(
            pillar=self.pillar,
            score=NEUTRAL_SCORE,
            confidence=0.0,
            strategy_name=NotBlankStr(self.name),
            data_point_count=len(context.feedback),
            evaluated_at=context.now,
        )
