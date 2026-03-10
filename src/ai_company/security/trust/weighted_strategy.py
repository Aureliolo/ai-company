"""Weighted trust strategy.

Computes a single trust score from weighted performance factors
and promotes/demotes based on configurable thresholds.
"""

from typing import TYPE_CHECKING

from ai_company.core.enums import ToolAccessLevel
from ai_company.observability import get_logger
from ai_company.observability.events.trust import (
    TRUST_EVALUATE_COMPLETE,
    TRUST_EVALUATE_START,
)
from ai_company.security.trust.models import TrustEvaluationResult, TrustState

if TYPE_CHECKING:
    from ai_company.core.types import NotBlankStr
    from ai_company.hr.performance.models import AgentPerformanceSnapshot
    from ai_company.security.trust.config import TrustConfig, TrustThreshold

logger = get_logger(__name__)

# Ordered trust levels for threshold-based promotion.
_TRUST_LEVEL_ORDER: tuple[ToolAccessLevel, ...] = (
    ToolAccessLevel.SANDBOXED,
    ToolAccessLevel.RESTRICTED,
    ToolAccessLevel.STANDARD,
    ToolAccessLevel.ELEVATED,
)

_TRUST_LEVEL_RANK: dict[ToolAccessLevel, int] = {
    level: idx for idx, level in enumerate(_TRUST_LEVEL_ORDER)
}

# Transition key convention: "{from_level}_to_{to_level}"
_TRANSITION_KEYS: tuple[tuple[str, ToolAccessLevel, ToolAccessLevel], ...] = (
    ("sandboxed_to_restricted", ToolAccessLevel.SANDBOXED, ToolAccessLevel.RESTRICTED),
    ("restricted_to_standard", ToolAccessLevel.RESTRICTED, ToolAccessLevel.STANDARD),
    ("standard_to_elevated", ToolAccessLevel.STANDARD, ToolAccessLevel.ELEVATED),
)


class WeightedTrustStrategy:
    """Trust strategy using a single weighted score.

    Computes a trust score from four weighted factors derived from
    the agent's performance snapshot:
      - task_difficulty: average complexity of completed tasks
      - completion_rate: success rate
      - error_rate: inverse of failure rate
      - human_feedback: overall quality score

    The score is compared against configurable thresholds to
    determine the recommended trust level.
    """

    def __init__(self, *, config: TrustConfig) -> None:
        self._config = config
        self._weights = config.weights
        self._thresholds = config.promotion_thresholds

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return "weighted"

    async def evaluate(
        self,
        *,
        agent_id: NotBlankStr,
        current_state: TrustState,
        snapshot: AgentPerformanceSnapshot,
    ) -> TrustEvaluationResult:
        """Compute weighted trust score and recommend level.

        Args:
            agent_id: Agent to evaluate.
            current_state: Current trust state.
            snapshot: Agent performance snapshot.

        Returns:
            Evaluation result with score and recommended level.
        """
        logger.debug(
            TRUST_EVALUATE_START,
            agent_id=agent_id,
            strategy="weighted",
        )

        score = self._compute_score(snapshot)
        recommended = self._score_to_level(score, current_state.global_level)
        requires_human = self._check_human_approval(
            current_state.global_level,
            recommended,
        )

        result = TrustEvaluationResult(
            agent_id=agent_id,
            recommended_level=recommended,
            current_level=current_state.global_level,
            requires_human_approval=requires_human,
            score=score,
            details=(f"Weighted score {score:.4f}; recommended {recommended.value}"),
            strategy_name="weighted",
        )

        logger.debug(
            TRUST_EVALUATE_COMPLETE,
            agent_id=agent_id,
            score=score,
            recommended=recommended.value,
        )
        return result

    def initial_state(self, *, agent_id: NotBlankStr) -> TrustState:
        """Create initial trust state at the configured level.

        Args:
            agent_id: Agent identifier.

        Returns:
            Initial trust state.
        """
        return TrustState(
            agent_id=agent_id,
            global_level=self._config.initial_level,
            trust_score=0.0,
        )

    def _compute_score(self, snapshot: AgentPerformanceSnapshot) -> float:
        """Compute the weighted trust score from performance data.

        Missing data defaults to 0.0 for that factor.
        """
        # Task difficulty: use overall quality as proxy (normalized 0-1)
        difficulty_factor = (
            snapshot.overall_quality_score / 10.0
            if snapshot.overall_quality_score is not None
            else 0.0
        )

        # Completion rate: derive from windows
        completion_factor = 0.0
        for window in snapshot.windows:
            if window.success_rate is not None:
                completion_factor = window.success_rate
                break

        # Error rate: inverse of failure rate
        error_factor = 1.0
        for window in snapshot.windows:
            if window.data_point_count > 0 and window.success_rate is not None:
                error_factor = window.success_rate
                break

        # Human feedback: overall quality score (normalized 0-1)
        feedback_factor = (
            snapshot.overall_quality_score / 10.0
            if snapshot.overall_quality_score is not None
            else 0.0
        )

        score = (
            self._weights.task_difficulty * difficulty_factor
            + self._weights.completion_rate * completion_factor
            + self._weights.error_rate * error_factor
            + self._weights.human_feedback * feedback_factor
        )
        return round(min(max(score, 0.0), 1.0), 4)

    def _score_to_level(
        self,
        score: float,
        current_level: ToolAccessLevel,
    ) -> ToolAccessLevel:
        """Determine the appropriate trust level from score.

        Walks through transitions in order; the highest level whose
        threshold is met becomes the recommendation.
        """
        recommended = current_level

        for key, from_level, to_level in _TRANSITION_KEYS:
            threshold = self._thresholds.get(key)
            if threshold is None:
                continue

            current_rank = _TRUST_LEVEL_RANK.get(current_level, 0)
            from_rank = _TRUST_LEVEL_RANK.get(from_level, 0)

            # Only consider transitions from the current or lower level
            if current_rank <= from_rank and score >= threshold.score:
                recommended = to_level

        return recommended

    def _check_human_approval(
        self,
        current: ToolAccessLevel,
        recommended: ToolAccessLevel,
    ) -> bool:
        """Check if the transition requires human approval."""
        if current == recommended:
            return False

        for key, from_level, to_level in _TRANSITION_KEYS:
            if from_level == current and to_level == recommended:
                threshold: TrustThreshold | None = self._thresholds.get(key)
                if threshold is not None:
                    return threshold.requires_human_approval
        return False
