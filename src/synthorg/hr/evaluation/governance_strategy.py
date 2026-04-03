"""Responsibility/Governance pillar scoring strategy.

Aggregates security audit compliance, trust level stability,
and autonomy compliance into a governance score. Each metric
can be independently toggled via ``GovernanceConfig``.
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
    EVAL_PILLAR_INSUFFICIENT_DATA,
    EVAL_PILLAR_SCORED,
    EVAL_TRUST_LEVEL_UNKNOWN,
)

logger = get_logger(__name__)

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
        total_audits = (
            context.audit_allow_count
            + context.audit_deny_count
            + context.audit_escalate_count
        )

        has_autonomy = context.config.governance.autonomy_compliance_enabled
        if total_audits == 0 and context.trust_level is None and not has_autonomy:
            return self._neutral(context, reason="no_governance_data")

        scores, enabled, data_points = self._collect_metrics(
            context,
            total_audits,
        )

        if not enabled:
            return self._neutral(
                context,
                reason="no_enabled_metrics_with_data",
            )

        return self._build_result(scores, enabled, data_points, context)

    def _collect_metrics(
        self,
        context: EvaluationContext,
        total_audits: int,
    ) -> tuple[dict[str, float], list[tuple[str, float, bool]], int]:
        """Gather enabled governance metrics.

        Returns:
            Tuple of (scores, enabled_metrics, data_points).
        """
        cfg = context.config.governance
        enabled: list[tuple[str, float, bool]] = []
        scores: dict[str, float] = {}
        data_points = 0

        if cfg.audit_compliance_enabled and total_audits > 0:
            scores["audit_compliance"] = self._audit_score(
                context,
                total_audits,
            )
            enabled.append(
                ("audit_compliance", cfg.audit_compliance_weight, True),
            )
            data_points += total_audits

        if cfg.trust_level_enabled and context.trust_level is not None:
            scores["trust_level"] = self._trust_score(
                context,
                context.trust_level,
            )
            enabled.append(
                ("trust_level", cfg.trust_level_weight, True),
            )
            data_points += 1

        if cfg.autonomy_compliance_enabled:
            scores["autonomy_compliance"] = max(
                0.0,
                MAX_SCORE - context.autonomy_downgrades_in_window * _DOWNGRADE_PENALTY,
            )
            enabled.append(
                ("autonomy_compliance", cfg.autonomy_compliance_weight, True),
            )
            data_points += 1

        return scores, enabled, data_points

    @staticmethod
    def _audit_score(ctx: EvaluationContext, total: int) -> float:
        """Compute audit compliance sub-score."""
        compliance = ctx.audit_allow_count / total
        high_risk_penalty = ctx.audit_high_risk_count / total
        return min(
            MAX_SCORE,
            max(0.0, compliance * MAX_SCORE - high_risk_penalty * MAX_SCORE),
        )

    def _trust_score(
        self,
        context: EvaluationContext,
        trust_level: NotBlankStr,
    ) -> float:
        """Compute trust level sub-score with demotion penalty."""
        trust_key = str(trust_level).lower()
        base_trust = _TRUST_LEVEL_SCORES.get(trust_key, NEUTRAL_SCORE)
        if trust_key not in _TRUST_LEVEL_SCORES:
            logger.warning(
                EVAL_TRUST_LEVEL_UNKNOWN,
                agent_id=context.agent_id,
                pillar=self.pillar.value,
                trust_level=trust_key,
                fallback_score=NEUTRAL_SCORE,
            )
        demotion_penalty = min(
            base_trust,
            context.trust_demotions_in_window * _DOWNGRADE_PENALTY,
        )
        return base_trust - demotion_penalty

    def _build_result(
        self,
        scores: dict[str, float],
        enabled: list[tuple[str, float, bool]],
        data_points: int,
        context: EvaluationContext,
    ) -> PillarScore:
        """Aggregate enabled metrics into a pillar score."""
        weights = redistribute_weights(enabled)
        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )
        confidence = min(1.0, data_points / FULL_CONFIDENCE_DATA_POINTS)

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
