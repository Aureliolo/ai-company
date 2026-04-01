"""Calendar ceremony scheduling strategy.

Ceremonies fire on wall-clock cadence using ``MeetingFrequency`` intervals,
regardless of task progress.  Sprints auto-transition at the configured
``duration_days`` boundary.  This is a time-based strategy with minimal
internal state for tracking when each ceremony last fired.
"""

from typing import TYPE_CHECKING, Any

from synthorg.communication.meeting.frequency import (
    MeetingFrequency,
    frequency_to_seconds,
)
from synthorg.engine.workflow.ceremony_policy import CeremonyStrategyType
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.engine.workflow.velocity_types import VelocityCalcType
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
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

# Strategy config keys.
_KEY_DURATION_DAYS = "duration_days"
_KEY_FREQUENCY = "frequency"

_SECONDS_PER_DAY: float = 86_400.0
_MIN_DURATION_DAYS: int = 1
_MAX_DURATION_DAYS: int = 90

_KNOWN_CONFIG_KEYS: frozenset[str] = frozenset({_KEY_DURATION_DAYS, _KEY_FREQUENCY})

_VALID_FREQUENCIES: frozenset[str] = frozenset(m.value for m in MeetingFrequency)


class CalendarStrategy:
    """Calendar ceremony scheduling strategy.

    Ceremonies fire on a wall-clock cadence defined by
    ``MeetingFrequency`` intervals:

    - ``daily``, ``weekly``, ``bi_weekly``, ``per_sprint_day``,
      ``monthly``.

    The frequency is resolved from ``ceremony.frequency`` first,
    then falls back to ``strategy_config["frequency"]``.

    Auto-transition: ACTIVE to IN_REVIEW when elapsed time reaches
    the configured ``duration_days`` boundary.  Task completion
    does **not** trigger transition.

    This strategy maintains a small ``_last_fire_elapsed`` dict to
    track when each ceremony last fired, preventing double-firing
    within the same interval.  State is cleared on sprint lifecycle
    transitions.
    """

    __slots__ = ("_last_fire_elapsed",)

    def __init__(self) -> None:
        self._last_fire_elapsed: dict[str, float] = {}

    def should_fire_ceremony(
        self,
        ceremony: SprintCeremonyConfig,
        sprint: Sprint,  # noqa: ARG002
        context: CeremonyEvalContext,
    ) -> bool:
        """Fire when wall-clock interval has elapsed since last fire.

        Resolves the interval from ``ceremony.frequency`` (primary)
        or ``strategy_config["frequency"]`` (fallback).

        Args:
            ceremony: The ceremony being evaluated.
            sprint: Current sprint state.
            context: Evaluation context with elapsed time.

        Returns:
            ``True`` if the ceremony should fire.
        """
        interval = self._resolve_interval(ceremony)
        if interval is None:
            logger.debug(
                SPRINT_CEREMONY_SKIPPED,
                ceremony=ceremony.name,
                reason="no_frequency",
                strategy="calendar",
            )
            return False

        last_fire = self._last_fire_elapsed.get(ceremony.name, 0.0)
        if context.elapsed_seconds - last_fire >= interval:
            self._last_fire_elapsed[ceremony.name] = context.elapsed_seconds
            logger.info(
                SPRINT_CEREMONY_TRIGGERED,
                ceremony=ceremony.name,
                strategy="calendar",
                elapsed_seconds=context.elapsed_seconds,
                interval_seconds=interval,
            )
            return True

        logger.debug(
            SPRINT_CEREMONY_SKIPPED,
            ceremony=ceremony.name,
            strategy="calendar",
            elapsed_seconds=context.elapsed_seconds,
            next_fire_at=last_fire + interval,
        )
        return False

    def should_transition_sprint(
        self,
        sprint: Sprint,
        config: SprintConfig,
        context: CeremonyEvalContext,
    ) -> SprintStatus | None:
        """Return IN_REVIEW when the duration_days boundary is reached.

        Only transitions from ACTIVE status.  Task completion does
        not affect calendar-based transition.

        Args:
            sprint: Current sprint state.
            config: Sprint configuration.
            context: Evaluation context with elapsed time.

        Returns:
            ``SprintStatus.IN_REVIEW`` if boundary reached, else ``None``.
        """
        if sprint.status is not SprintStatus.ACTIVE:
            return None

        duration_days = self._resolve_duration_days(config)
        duration_seconds = duration_days * _SECONDS_PER_DAY
        if context.elapsed_seconds >= duration_seconds:
            return SprintStatus.IN_REVIEW
        return None

    # -- Lifecycle hooks (clear state on sprint transitions) ----------

    async def on_sprint_activated(
        self,
        sprint: Sprint,  # noqa: ARG002
        config: SprintConfig,  # noqa: ARG002
    ) -> None:
        """Clear fire tracking for a new sprint."""
        self._last_fire_elapsed.clear()

    async def on_sprint_deactivated(self) -> None:
        """Clear fire tracking when sprint ends."""
        self._last_fire_elapsed.clear()

    async def on_task_completed(
        self,
        sprint: Sprint,
        task_id: str,
        story_points: float,
        context: CeremonyEvalContext,
    ) -> None:
        """No-op."""

    async def on_task_added(
        self,
        sprint: Sprint,
        task_id: str,
    ) -> None:
        """No-op."""

    async def on_task_blocked(
        self,
        sprint: Sprint,
        task_id: str,
    ) -> None:
        """No-op."""

    async def on_budget_updated(
        self,
        sprint: Sprint,
        budget_consumed_fraction: float,
    ) -> None:
        """No-op."""

    async def on_external_event(
        self,
        sprint: Sprint,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        """No-op."""

    @property
    def strategy_type(self) -> CeremonyStrategyType:
        """Return CALENDAR."""
        return CeremonyStrategyType.CALENDAR

    def get_default_velocity_calculator(self) -> VelocityCalcType:
        """Return CALENDAR velocity calculator."""
        return VelocityCalcType.CALENDAR

    def validate_strategy_config(
        self,
        config: Mapping[str, Any],
    ) -> None:
        """Validate calendar strategy config.

        Args:
            config: Strategy config to validate.

        Raises:
            ValueError: If the config contains invalid keys or values.
        """
        unknown = set(config) - _KNOWN_CONFIG_KEYS
        if unknown:
            msg = f"Unknown config keys: {sorted(unknown)}"
            raise ValueError(msg)

        duration = config.get(_KEY_DURATION_DAYS)
        if duration is not None:
            if not isinstance(duration, int):
                msg = (
                    f"{_KEY_DURATION_DAYS} must be a positive integer, got {duration!r}"
                )
                raise ValueError(msg)
            if duration < _MIN_DURATION_DAYS or duration > _MAX_DURATION_DAYS:
                msg = (
                    f"{_KEY_DURATION_DAYS} must be between "
                    f"{_MIN_DURATION_DAYS} and {_MAX_DURATION_DAYS}, "
                    f"got {duration!r}"
                )
                raise ValueError(msg)

        freq = config.get(_KEY_FREQUENCY)
        if freq is not None and freq not in _VALID_FREQUENCIES:
            msg = (
                f"Invalid frequency {freq!r}. "
                f"Valid frequencies: {sorted(_VALID_FREQUENCIES)}"
            )
            raise ValueError(msg)

    # -- Internal helpers -----------------------------------------------

    @staticmethod
    def _get_ceremony_config(
        ceremony: SprintCeremonyConfig,
    ) -> Mapping[str, Any]:
        """Extract strategy config from a ceremony's policy override."""
        if ceremony.policy_override is None:
            return {}
        return ceremony.policy_override.strategy_config or {}

    def _resolve_interval(
        self,
        ceremony: SprintCeremonyConfig,
    ) -> float | None:
        """Resolve the firing interval in seconds.

        Priority: ``ceremony.frequency`` > ``strategy_config["frequency"]``.
        """
        if ceremony.frequency is not None:
            return frequency_to_seconds(ceremony.frequency)

        config = self._get_ceremony_config(ceremony)
        freq_str = config.get(_KEY_FREQUENCY)
        if freq_str is not None:
            try:
                freq = MeetingFrequency(freq_str)
            except ValueError:
                return None
            return frequency_to_seconds(freq)
        return None

    @staticmethod
    def _resolve_duration_days(config: SprintConfig) -> int:
        """Resolve duration_days from strategy_config or SprintConfig."""
        sc = config.ceremony_policy.strategy_config or {}
        duration = sc.get(_KEY_DURATION_DAYS)
        if isinstance(duration, int) and duration >= _MIN_DURATION_DAYS:
            return duration
        return config.duration_days
