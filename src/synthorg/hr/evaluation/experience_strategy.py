"""User Experience pillar scoring strategy.

Weighted average of interaction feedback ratings. Each rating
dimension can be independently toggled via ``ExperienceConfig``.
None ratings and disabled metrics have their weight redistributed.
"""

from synthorg.core.types import NotBlankStr
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

_MAX_SCORE: float = 10.0
_NEUTRAL_SCORE: float = 5.0


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
            logger.info(
                EVAL_PILLAR_INSUFFICIENT_DATA,
                agent_id=context.agent_id,
                pillar=self.pillar.value,
                reason="insufficient_feedback",
                count=len(feedback),
                min_required=cfg.min_feedback_count,
            )
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=len(feedback),
                evaluated_at=context.now,
            )

        # Map metric name -> (config_enabled, config_weight, field_name).
        metric_defs = [
            ("clarity", cfg.clarity_enabled, cfg.clarity_weight, "clarity_rating"),
            ("tone", cfg.tone_enabled, cfg.tone_weight, "tone_rating"),
            (
                "helpfulness",
                cfg.helpfulness_enabled,
                cfg.helpfulness_weight,
                "helpfulness_rating",
            ),
            ("trust", cfg.trust_enabled, cfg.trust_weight, "trust_rating"),
            (
                "satisfaction",
                cfg.satisfaction_enabled,
                cfg.satisfaction_weight,
                "satisfaction_rating",
            ),
        ]

        # Level 1: Filter by config-enabled.
        available: list[tuple[str, float, float]] = []  # (name, weight, avg_score)
        for metric_name, enabled, weight, field_name in metric_defs:
            if not enabled:
                continue
            avg = _avg_rating(feedback, field_name)
            if avg is not None:
                available.append((metric_name, weight, avg * _MAX_SCORE))

        if not available:
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=len(feedback),
                evaluated_at=context.now,
            )

        # Level 2: Redistribute weights among metrics with data.
        weights = redistribute_weights(
            [(name, w, True) for name, w, _ in available],
        )
        scores = {name: s for name, _, s in available}

        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(_MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )
        confidence = min(1.0, len(feedback) / (cfg.min_feedback_count * 3))

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
