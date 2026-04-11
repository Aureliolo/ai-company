"""Skill gap strategy.

Identifies missing skills from task requirements and proposes
targeted hires. Disabled by default (requires LLM analysis
for rich matching).
"""

from datetime import UTC, datetime

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.enums import ScalingActionType, ScalingStrategyName
from synthorg.hr.scaling.models import ScalingContext, ScalingDecision
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_SCALING_STRATEGY_EVALUATED

logger = get_logger(__name__)

_NAME = NotBlankStr("skill_gap")
_ACTION_TYPES = frozenset({ScalingActionType.HIRE})


class SkillGapStrategy:
    """Skill coverage analysis strategy.

    Examines skill signals to find gaps between required and
    available skills. Proposes targeted hires when gaps are found.

    Args:
        enabled: Whether the strategy is active.
        min_missing_skills: Minimum number of missing skills to
            trigger a hire proposal.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        min_missing_skills: int = 1,
    ) -> None:
        if min_missing_skills < 1:
            msg = f"min_missing_skills must be >= 1, got {min_missing_skills}"
            raise ValueError(msg)
        self._enabled = enabled
        self._min_missing = min_missing_skills

    @property
    def name(self) -> NotBlankStr:
        """Strategy identifier."""
        return _NAME

    @property
    def action_types(self) -> frozenset[ScalingActionType]:
        """Action types this strategy can produce."""
        return _ACTION_TYPES

    async def evaluate(
        self,
        context: ScalingContext,
    ) -> tuple[ScalingDecision, ...]:
        """Evaluate skill signals and propose hires for gaps.

        Args:
            context: Aggregated company state snapshot.

        Returns:
            Hire decisions for missing skills, or empty if disabled.
        """
        if not self._enabled:
            return ()

        now = datetime.now(UTC)

        missing_signal = next(
            (s for s in context.skill_signals if s.name == "missing_skill_count"),
            None,
        )
        coverage_signal = next(
            (s for s in context.skill_signals if s.name == "coverage_ratio"),
            None,
        )

        if missing_signal is None or missing_signal.value < self._min_missing:
            logger.debug(
                HR_SCALING_STRATEGY_EVALUATED,
                strategy="skill_gap",
                decisions=0,
                reason="no_gaps_or_below_threshold",
            )
            return ()

        raw_confidence = 1.0 - (coverage_signal.value if coverage_signal else 0.0)
        confidence = max(0.0, min(raw_confidence, 1.0))
        skill_signals = tuple(context.skill_signals)

        decision = ScalingDecision(
            action_type=ScalingActionType.HIRE,
            source_strategy=ScalingStrategyName.SKILL_GAP,
            target_role=NotBlankStr("specialist"),
            rationale=NotBlankStr(
                f"{int(missing_signal.value)} missing skills detected"
            ),
            confidence=round(confidence, 4),
            signals=skill_signals,
            created_at=now,
        )

        logger.info(
            HR_SCALING_STRATEGY_EVALUATED,
            strategy="skill_gap",
            decisions=1,
            missing_skills=int(missing_signal.value),
        )
        return (decision,)
