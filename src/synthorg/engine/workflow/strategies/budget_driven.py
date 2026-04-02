"""Budget-driven ceremony scheduling strategy.

Ceremonies fire at cost-consumption thresholds.  Ties directly into
the budget module (cost tracking, quota degradation).

**Config keys** (per-ceremony ``policy_override.strategy_config``):

- ``budget_thresholds`` (list[float]): percentages at which to fire
  the ceremony (e.g. ``[25, 50, 75]``).

**Config keys** (sprint-level ``ceremony_policy.strategy_config``):

- ``transition_threshold`` (float): budget percentage that triggers
  sprint auto-transition (default: 100.0).
"""

from typing import TYPE_CHECKING, Any

from synthorg.engine.workflow.ceremony_policy import (
    CeremonyStrategyType,
)
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.engine.workflow.velocity_types import VelocityCalcType
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
    SPRINT_AUTO_TRANSITION_BUDGET,
    SPRINT_CEREMONY_BUDGET_THRESHOLD_CROSSED,
    SPRINT_CEREMONY_SKIPPED,
    SPRINT_CEREMONY_TRIGGERED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.engine.workflow.ceremony_context import CeremonyEvalContext
    from synthorg.engine.workflow.sprint_config import (
        SprintCeremonyConfig,
        SprintConfig,
    )

logger = get_logger(__name__)

# -- Config keys ---------------------------------------------------------------

_KEY_BUDGET_THRESHOLDS: str = "budget_thresholds"
_KEY_TRANSITION_THRESHOLD: str = "transition_threshold"

_KNOWN_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        _KEY_BUDGET_THRESHOLDS,
        _KEY_TRANSITION_THRESHOLD,
    }
)

_DEFAULT_TRANSITION_THRESHOLD_PCT: float = 100.0
_MAX_THRESHOLD_PCT: float = 100.0


class BudgetDrivenStrategy:
    """Ceremony scheduling strategy driven by budget consumption.

    Ceremonies fire when ``context.budget_consumed_fraction`` crosses
    configured percentage thresholds.  Each threshold fires at most
    once per sprint.  When multiple thresholds are crossed
    simultaneously, only the lowest unfired threshold fires per
    evaluation call (the scheduler calls repeatedly, so thresholds
    catch up quickly without cascading ceremonies in a single cycle).

    State is tracked per-sprint and cleared on sprint transitions.
    """

    __slots__ = ("_fired_thresholds",)

    def __init__(self) -> None:
        self._fired_thresholds: dict[str, set[float]] = {}

    # -- Core evaluation -------------------------------------------------------

    def should_fire_ceremony(
        self,
        ceremony: SprintCeremonyConfig,
        sprint: Sprint,  # noqa: ARG002
        context: CeremonyEvalContext,
    ) -> bool:
        """Check if a budget threshold has been crossed.

        Fires the lowest unfired threshold that the current budget
        fraction has reached.  Returns ``True`` for at most one
        threshold per call.

        Args:
            ceremony: The ceremony being evaluated.
            sprint: Current sprint state.
            context: Evaluation context with ``budget_consumed_fraction``.

        Returns:
            ``True`` if a threshold was newly crossed.
        """
        config = self._get_ceremony_config(ceremony)
        thresholds = config.get(_KEY_BUDGET_THRESHOLDS)

        if not thresholds:
            return False

        budget_pct = context.budget_consumed_fraction * _MAX_THRESHOLD_PCT
        fired = self._fired_thresholds.setdefault(ceremony.name, set())

        for threshold in sorted(thresholds):
            if threshold in fired:
                continue
            if budget_pct >= threshold:
                fired.add(threshold)
                logger.info(
                    SPRINT_CEREMONY_BUDGET_THRESHOLD_CROSSED,
                    ceremony=ceremony.name,
                    threshold=threshold,
                    budget_pct=budget_pct,
                    strategy="budget_driven",
                )
                logger.info(
                    SPRINT_CEREMONY_TRIGGERED,
                    ceremony=ceremony.name,
                    threshold=threshold,
                    strategy="budget_driven",
                )
                return True

        logger.debug(
            SPRINT_CEREMONY_SKIPPED,
            ceremony=ceremony.name,
            budget_pct=budget_pct,
            strategy="budget_driven",
        )
        return False

    def should_transition_sprint(
        self,
        sprint: Sprint,
        config: SprintConfig,
        context: CeremonyEvalContext,
    ) -> SprintStatus | None:
        """Return IN_REVIEW when budget consumption reaches threshold.

        Only transitions from ACTIVE status.

        Args:
            sprint: Current sprint state.
            config: Sprint configuration.
            context: Evaluation context.

        Returns:
            ``SprintStatus.IN_REVIEW`` if budget threshold met,
            else ``None``.
        """
        if sprint.status is not SprintStatus.ACTIVE:
            return None

        strategy_config = (
            config.ceremony_policy.strategy_config
            if config.ceremony_policy.strategy_config is not None
            else {}
        )
        transition_pct: float = strategy_config.get(
            _KEY_TRANSITION_THRESHOLD,
            _DEFAULT_TRANSITION_THRESHOLD_PCT,
        )
        budget_pct = context.budget_consumed_fraction * _MAX_THRESHOLD_PCT

        if budget_pct >= transition_pct:
            logger.info(
                SPRINT_AUTO_TRANSITION_BUDGET,
                budget_pct=budget_pct,
                transition_threshold=transition_pct,
                strategy="budget_driven",
            )
            return SprintStatus.IN_REVIEW

        return None

    # -- Lifecycle hooks -------------------------------------------------------

    async def on_sprint_activated(
        self,
        sprint: Sprint,  # noqa: ARG002
        config: SprintConfig,  # noqa: ARG002
    ) -> None:
        """Clear fired-threshold tracking for new sprint.

        Args:
            sprint: The activated sprint.
            config: Sprint configuration.
        """
        self._fired_thresholds.clear()

    async def on_sprint_deactivated(self) -> None:
        """Clear all internal state."""
        self._fired_thresholds.clear()

    async def on_task_completed(
        self,
        sprint: Sprint,
        task_id: str,
        story_points: float,
        context: CeremonyEvalContext,
    ) -> None:
        """No-op -- budget strategy does not track task events.

        Args:
            sprint: Current sprint state.
            task_id: The completed task ID.
            story_points: Points earned for the task.
            context: Evaluation context.
        """

    async def on_task_added(
        self,
        sprint: Sprint,
        task_id: str,
    ) -> None:
        """No-op.

        Args:
            sprint: Current sprint state.
            task_id: The added task ID.
        """

    async def on_task_blocked(
        self,
        sprint: Sprint,
        task_id: str,
    ) -> None:
        """No-op.

        Args:
            sprint: Current sprint state.
            task_id: The blocked task ID.
        """

    async def on_budget_updated(
        self,
        sprint: Sprint,
        budget_consumed_fraction: float,
    ) -> None:
        """No-op -- budget fraction is read from context in evaluation.

        Args:
            sprint: Current sprint state.
            budget_consumed_fraction: Budget consumed fraction.
        """

    async def on_external_event(
        self,
        sprint: Sprint,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        """No-op.

        Args:
            sprint: Current sprint state.
            event_name: Name of the external event.
            payload: Event payload data.
        """

    # -- Metadata --------------------------------------------------------------

    @property
    def strategy_type(self) -> CeremonyStrategyType:
        """Return BUDGET_DRIVEN."""
        return CeremonyStrategyType.BUDGET_DRIVEN

    def get_default_velocity_calculator(self) -> VelocityCalcType:
        """Return BUDGET."""
        return VelocityCalcType.BUDGET

    def validate_strategy_config(
        self,
        config: Mapping[str, Any],
    ) -> None:
        """Validate budget-driven strategy config.

        Args:
            config: Strategy config to validate.

        Raises:
            ValueError: If the config contains invalid keys or values.
        """
        unknown = set(config) - _KNOWN_CONFIG_KEYS
        if unknown:
            msg = f"Unknown config keys: {sorted(unknown)}"
            raise ValueError(msg)

        thresholds = config.get(_KEY_BUDGET_THRESHOLDS)
        if thresholds is not None:
            if not isinstance(thresholds, list):
                msg = (
                    f"'{_KEY_BUDGET_THRESHOLDS}' must be a list, "
                    f"got {type(thresholds).__name__}"
                )
                raise ValueError(msg)
            seen: set[float] = set()
            for t in thresholds:
                if not isinstance(t, int | float) or not (0 < t <= _MAX_THRESHOLD_PCT):
                    msg = (
                        f"Each budget threshold must be a number in (0, 100], got {t!r}"
                    )
                    raise ValueError(msg)
                if t in seen:
                    msg = f"Duplicate budget threshold: {t}"
                    raise ValueError(msg)
                seen.add(t)

        transition = config.get(_KEY_TRANSITION_THRESHOLD)
        if transition is not None and (
            not isinstance(transition, int | float)
            or not (0 < transition <= _MAX_THRESHOLD_PCT)
        ):
            msg = (
                f"'{_KEY_TRANSITION_THRESHOLD}' must be a number "
                f"in (0, 100], got {transition!r}"
            )
            raise ValueError(msg)

    # -- Private helpers -------------------------------------------------------

    @staticmethod
    def _get_ceremony_config(
        ceremony: SprintCeremonyConfig,
    ) -> Mapping[str, Any]:
        """Extract strategy config from a ceremony's policy override."""
        if ceremony.policy_override is None:
            return {}
        return ceremony.policy_override.strategy_config or {}
