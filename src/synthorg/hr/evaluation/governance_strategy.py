"""Responsibility/Governance pillar scoring strategy.

Aggregates security audit compliance, trust level stability,
and autonomy compliance into a governance score. Each metric
can be independently toggled via ``GovernanceConfig``.
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

# Trust level to score mapping.
_TRUST_LEVEL_SCORES: dict[str, float] = {
    "sandboxed": 2.5,
    "restricted": 5.0,
    "standard": 7.5,
    "elevated": 10.0,
}

# Penalty per autonomy downgrade.
_DOWNGRADE_PENALTY: float = 2.5


class AuditBasedGovernanceStrategy:
    """Governance scoring from security audit, trust, and autonomy data.

    Components (all toggleable):
        - audit_compliance: Ratio of allowed vs total audit entries.
        - trust_level: Score mapped from current trust level.
        - autonomy_compliance: Penalty per autonomy downgrade.
    """

    @property
    def name(self) -> str:
        """Human-readable strategy name."""
        return "audit_based_governance"

    @property
    def pillar(self) -> EvaluationPillar:
        """Which pillar this strategy scores."""
        return EvaluationPillar.GOVERNANCE

    async def score(self, *, context: EvaluationContext) -> PillarScore:
        """Score governance from audit, trust, and autonomy data.

        Args:
            context: Evaluation context.

        Returns:
            Governance pillar score.
        """
        cfg = context.config.governance
        total_audits = (
            context.audit_allow_count
            + context.audit_deny_count
            + context.audit_escalate_count
        )

        if total_audits == 0 and context.trust_level is None:
            logger.info(
                EVAL_PILLAR_INSUFFICIENT_DATA,
                agent_id=context.agent_id,
                pillar=self.pillar.value,
                reason="no_governance_data",
            )
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=0,
                evaluated_at=context.now,
            )

        enabled_metrics: list[tuple[str, float, bool]] = []
        scores: dict[str, float] = {}
        data_points = 0

        if cfg.audit_compliance_enabled and total_audits > 0:
            compliance = context.audit_allow_count / max(1, total_audits)
            high_risk_penalty = context.audit_high_risk_count / max(1, total_audits)
            audit_score = max(
                0.0,
                compliance * _MAX_SCORE - high_risk_penalty * _MAX_SCORE,
            )
            scores["audit_compliance"] = min(_MAX_SCORE, audit_score)
            enabled_metrics.append(
                ("audit_compliance", cfg.audit_compliance_weight, True),
            )
            data_points += total_audits

        if cfg.trust_level_enabled and context.trust_level is not None:
            base_trust = _TRUST_LEVEL_SCORES.get(
                str(context.trust_level).lower(),
                _NEUTRAL_SCORE,
            )
            demotion_penalty = min(
                base_trust,
                context.trust_demotions_in_window * _DOWNGRADE_PENALTY,
            )
            scores["trust_level"] = base_trust - demotion_penalty
            enabled_metrics.append(
                ("trust_level", cfg.trust_level_weight, True),
            )
            data_points += 1

        if cfg.autonomy_compliance_enabled:
            autonomy_score = max(
                0.0,
                _MAX_SCORE - context.autonomy_downgrades_in_window * _DOWNGRADE_PENALTY,
            )
            scores["autonomy_compliance"] = autonomy_score
            enabled_metrics.append(
                ("autonomy_compliance", cfg.autonomy_compliance_weight, True),
            )
            data_points += 1

        if not enabled_metrics:
            return PillarScore(
                pillar=self.pillar,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr(self.name),
                data_point_count=0,
                evaluated_at=context.now,
            )

        weights = redistribute_weights(enabled_metrics)
        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(_MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )
        confidence = min(1.0, data_points / 10.0)

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
