"""Per-category trust strategy.

Maintains separate trust tracks per tool category, allowing
fine-grained access control where an agent can be trusted for
file operations but sandboxed for deployment.
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
    from ai_company.security.trust.config import TrustConfig

logger = get_logger(__name__)


class PerCategoryTrustStrategy:
    """Trust strategy with separate tracks per tool category.

    Each tool category has its own trust level and promotion criteria.
    The global_level is derived as the minimum across all categories.
    """

    def __init__(self, *, config: TrustConfig) -> None:
        self._config = config
        self._initial_levels = config.initial_category_levels
        self._criteria = config.category_criteria

    @property
    def name(self) -> str:
        """Strategy name identifier."""
        return "per_category"

    async def evaluate(
        self,
        *,
        agent_id: NotBlankStr,
        current_state: TrustState,
        snapshot: AgentPerformanceSnapshot,
    ) -> TrustEvaluationResult:
        """Evaluate trust per category and derive global level.

        Args:
            agent_id: Agent to evaluate.
            current_state: Current trust state.
            snapshot: Agent performance snapshot.

        Returns:
            Evaluation result with recommended global level.
        """
        logger.debug(
            TRUST_EVALUATE_START,
            agent_id=agent_id,
            strategy="per_category",
        )

        category_updates: dict[str, ToolAccessLevel] = {}
        requires_human = False

        for category, current_level in current_state.category_levels.items():
            cat_criteria = self._criteria.get(category, {})
            new_level = current_level

            for transition_key, criteria in cat_criteria.items():
                from_to = transition_key.split("_to_")
                if len(from_to) != 2:  # noqa: PLR2004
                    continue
                from_str, to_str = from_to

                if current_level.value != from_str:
                    continue

                # Check if criteria are met
                if self._check_category_criteria(
                    criteria_config=criteria,
                    snapshot=snapshot,
                ):
                    try:
                        new_level = ToolAccessLevel(to_str)
                    except ValueError:
                        continue

                    if criteria.requires_human_approval:
                        requires_human = True

            category_updates[category] = new_level

        # Global level = minimum across all categories
        if category_updates:
            level_order = [
                ToolAccessLevel.SANDBOXED,
                ToolAccessLevel.RESTRICTED,
                ToolAccessLevel.STANDARD,
                ToolAccessLevel.ELEVATED,
            ]
            rank = {lv: i for i, lv in enumerate(level_order)}
            min_rank = min(rank.get(lv, 0) for lv in category_updates.values())
            recommended = level_order[min_rank]
        else:
            recommended = current_state.global_level

        result = TrustEvaluationResult(
            agent_id=agent_id,
            recommended_level=recommended,
            current_level=current_state.global_level,
            requires_human_approval=requires_human,
            details=(
                f"Per-category evaluation; recommended global {recommended.value}"
            ),
            strategy_name="per_category",
        )

        logger.debug(
            TRUST_EVALUATE_COMPLETE,
            agent_id=agent_id,
            recommended=recommended.value,
        )
        return result

    def initial_state(self, *, agent_id: NotBlankStr) -> TrustState:
        """Create initial trust state with per-category levels.

        Args:
            agent_id: Agent identifier.

        Returns:
            Initial trust state with category levels.
        """
        return TrustState(
            agent_id=agent_id,
            global_level=self._config.initial_level,
            category_levels=dict(self._initial_levels),
        )

    @staticmethod
    def _check_category_criteria(
        *,
        criteria_config: object,
        snapshot: AgentPerformanceSnapshot,
    ) -> bool:
        """Check whether performance snapshot meets category criteria.

        Uses duck typing on the criteria_config which has
        tasks_completed and quality_score_min attributes.
        """
        tasks_completed = getattr(criteria_config, "tasks_completed", 0)
        quality_min = getattr(criteria_config, "quality_score_min", 0.0)

        # Count total completed tasks from windows
        total_tasks = 0
        for window in snapshot.windows:
            total_tasks = max(total_tasks, window.tasks_completed)

        if total_tasks < tasks_completed:
            return False

        return not (
            snapshot.overall_quality_score is not None
            and snapshot.overall_quality_score < quality_min
        )
