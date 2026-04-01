"""Hybrid (first-wins) ceremony scheduling strategy.

Both calendar and task-driven triggers exist on each ceremony.
Whichever fires first wins and resets the cadence counter.  Calendar
provides a heartbeat floor; task counts provide a throughput ceiling.
"""

from collections.abc import Mapping  # noqa: TC003 -- used at runtime
from typing import TYPE_CHECKING, Any

from synthorg.communication.meeting.frequency import (
    MeetingFrequency,
    frequency_to_seconds,
)
from synthorg.engine.workflow.ceremony_context import (
    CeremonyEvalContext,  # noqa: TC001 -- used at runtime
)
from synthorg.engine.workflow.ceremony_policy import (
    TRIGGER_EVERY_N,
    TRIGGER_SPRINT_END,
    TRIGGER_SPRINT_MIDPOINT,
    TRIGGER_SPRINT_PERCENTAGE,
    TRIGGER_SPRINT_START,
    CeremonyStrategyType,
)
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.engine.workflow.velocity_types import VelocityCalcType
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
    SPRINT_CEREMONY_SKIPPED,
    SPRINT_CEREMONY_TRIGGERED,
)

if TYPE_CHECKING:
    from synthorg.engine.workflow.sprint_config import (
        SprintCeremonyConfig,
        SprintConfig,
    )

logger = get_logger(__name__)

# Strategy config keys.
_KEY_DURATION_DAYS = "duration_days"
_KEY_EVERY_N = "every_n_completions"
_KEY_FREQUENCY = "frequency"
_KEY_SPRINT_PERCENTAGE = "sprint_percentage"
_KEY_TRIGGER = "trigger"

_SECONDS_PER_DAY: float = 86_400.0
_MIN_DURATION_DAYS: int = 1
_MAX_DURATION_DAYS: int = 90
_DEFAULT_EVERY_N: int = 5
_DEFAULT_SPRINT_PCT: float = 50.0
_MAX_SPRINT_PCT: float = 100.0
_DEFAULT_TRANSITION_THRESHOLD: float = 1.0
_MIDPOINT_THRESHOLD: float = 0.5

_KNOWN_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        _KEY_DURATION_DAYS,
        _KEY_EVERY_N,
        _KEY_FREQUENCY,
        _KEY_SPRINT_PERCENTAGE,
        _KEY_TRIGGER,
    }
)

_VALID_TRIGGERS: frozenset[str] = frozenset(
    {
        TRIGGER_SPRINT_START,
        TRIGGER_SPRINT_END,
        TRIGGER_SPRINT_MIDPOINT,
        TRIGGER_EVERY_N,
        TRIGGER_SPRINT_PERCENTAGE,
    }
)

_VALID_FREQUENCIES: frozenset[str] = frozenset(m.value for m in MeetingFrequency)


class HybridStrategy:
    """Hybrid (first-wins) ceremony scheduling strategy.

    Combines calendar and task-driven triggers.  Whichever fires
    first wins and resets the cadence:

    - **Calendar leg**: fires when wall-clock interval elapses
      (resolved from ``ceremony.frequency`` or
      ``strategy_config["frequency"]``).
    - **Task-driven leg**: fires on ``every_n_completions`` or
      ``sprint_percentage`` thresholds (from
      ``strategy_config``).

    When either leg fires, the calendar timer resets so that the
    next calendar check starts from the fire time.

    Auto-transition: ACTIVE to IN_REVIEW on whichever comes first --
    task completion threshold *or* calendar duration boundary.

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
        """Fire when either calendar interval or task threshold is met.

        Whichever fires first wins.  On fire, the calendar timer
        resets to the current ``elapsed_seconds``.

        Args:
            ceremony: The ceremony being evaluated.
            sprint: Current sprint state.
            context: Evaluation context with counters and timings.

        Returns:
            ``True`` if the ceremony should fire.
        """
        calendar_fires = self._check_calendar(ceremony, context)
        task_fires = self._check_task_driven(ceremony, context)

        fires = calendar_fires or task_fires
        if fires:
            # Reset calendar timer regardless of which leg fired.
            self._last_fire_elapsed[ceremony.name] = context.elapsed_seconds
            logger.info(
                SPRINT_CEREMONY_TRIGGERED,
                ceremony=ceremony.name,
                strategy="hybrid",
                calendar_fired=calendar_fires,
                task_fired=task_fires,
                elapsed_seconds=context.elapsed_seconds,
            )
        else:
            logger.debug(
                SPRINT_CEREMONY_SKIPPED,
                ceremony=ceremony.name,
                strategy="hybrid",
            )
        return fires

    def should_transition_sprint(
        self,
        sprint: Sprint,
        config: SprintConfig,
        context: CeremonyEvalContext,
    ) -> SprintStatus | None:
        """Return IN_REVIEW when either time or task threshold is met.

        Calendar leg: ``elapsed_seconds >= duration_days * 86400``.
        Task leg: ``sprint_percentage_complete >= transition_threshold``
        (only when there are tasks).

        Args:
            sprint: Current sprint state.
            config: Sprint configuration.
            context: Evaluation context.

        Returns:
            ``SprintStatus.IN_REVIEW`` if either threshold met,
            else ``None``.
        """
        if sprint.status is not SprintStatus.ACTIVE:
            return None

        # Calendar leg.
        duration_days = self._resolve_duration_days(config)
        duration_seconds = duration_days * _SECONDS_PER_DAY
        if context.elapsed_seconds >= duration_seconds:
            return SprintStatus.IN_REVIEW

        # Task-driven leg.
        if context.total_tasks_in_sprint > 0:
            threshold: float = (
                config.ceremony_policy.transition_threshold
                if config.ceremony_policy.transition_threshold is not None
                else _DEFAULT_TRANSITION_THRESHOLD
            )
            if context.sprint_percentage_complete >= threshold:
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
        """Return HYBRID."""
        return CeremonyStrategyType.HYBRID

    def get_default_velocity_calculator(self) -> VelocityCalcType:
        """Return MULTI_DIMENSIONAL velocity calculator."""
        return VelocityCalcType.MULTI_DIMENSIONAL

    def validate_strategy_config(
        self,
        config: Mapping[str, Any],
    ) -> None:
        """Validate hybrid strategy config.

        Accepts keys from both calendar and task-driven strategies.

        Args:
            config: Strategy config to validate.

        Raises:
            ValueError: If the config contains invalid keys or values.
        """
        unknown = set(config) - _KNOWN_CONFIG_KEYS
        if unknown:
            msg = f"Unknown config keys: {sorted(unknown)}"
            raise ValueError(msg)

        _validate_duration_days(config.get(_KEY_DURATION_DAYS))
        _validate_trigger(config.get(_KEY_TRIGGER))
        _validate_every_n(config.get(_KEY_EVERY_N))
        _validate_sprint_percentage(config.get(_KEY_SPRINT_PERCENTAGE))
        _validate_frequency(config.get(_KEY_FREQUENCY))

    # -- Internal helpers -----------------------------------------------

    @staticmethod
    def _get_ceremony_config(
        ceremony: SprintCeremonyConfig,
    ) -> Mapping[str, Any]:
        """Extract strategy config from a ceremony's policy override."""
        if ceremony.policy_override is None:
            return {}
        return ceremony.policy_override.strategy_config or {}

    def _check_calendar(
        self,
        ceremony: SprintCeremonyConfig,
        context: CeremonyEvalContext,
    ) -> bool:
        """Check the calendar (time-based) leg."""
        interval = self._resolve_interval(ceremony)
        if interval is None:
            return False
        last_fire = self._last_fire_elapsed.get(ceremony.name, 0.0)
        return context.elapsed_seconds - last_fire >= interval

    @staticmethod
    def _check_task_driven(
        ceremony: SprintCeremonyConfig,
        context: CeremonyEvalContext,
    ) -> bool:
        """Check the task-driven leg."""
        if ceremony.policy_override is None:
            return False
        config = ceremony.policy_override.strategy_config or {}
        trigger = config.get(_KEY_TRIGGER)
        if trigger is None:
            return False
        return _evaluate_task_trigger(trigger, config, context)

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


def _validate_duration_days(value: object) -> None:
    """Validate optional duration_days config value."""
    if value is None:
        return
    if not isinstance(value, int):
        msg = f"{_KEY_DURATION_DAYS} must be a positive integer, got {value!r}"
        raise ValueError(msg)  # noqa: TRY004 -- ValueError for consistency
    if value < _MIN_DURATION_DAYS or value > _MAX_DURATION_DAYS:
        msg = (
            f"{_KEY_DURATION_DAYS} must be between "
            f"{_MIN_DURATION_DAYS} and {_MAX_DURATION_DAYS}, "
            f"got {value!r}"
        )
        raise ValueError(msg)


def _validate_trigger(value: object) -> None:
    """Validate optional trigger config value."""
    if value is not None and value not in _VALID_TRIGGERS:
        msg = f"Invalid trigger {value!r}. Valid triggers: {sorted(_VALID_TRIGGERS)}"
        raise ValueError(msg)


def _validate_every_n(value: object) -> None:
    """Validate optional every_n_completions config value."""
    if value is not None and (not isinstance(value, int) or value < 1):
        msg = f"{_KEY_EVERY_N} must be a positive integer, got {value!r}"
        raise ValueError(msg)


def _validate_sprint_percentage(value: object) -> None:
    """Validate optional sprint_percentage config value."""
    if value is not None and (
        not isinstance(value, int | float) or value <= 0 or value > _MAX_SPRINT_PCT
    ):
        msg = (
            f"{_KEY_SPRINT_PERCENTAGE} must be between "
            f"0 (exclusive) and {_MAX_SPRINT_PCT} (inclusive),"
            f" got {value!r}"
        )
        raise ValueError(msg)


def _validate_frequency(value: object) -> None:
    """Validate optional frequency config value."""
    if value is not None and value not in _VALID_FREQUENCIES:
        msg = (
            f"Invalid frequency {value!r}. "
            f"Valid frequencies: {sorted(_VALID_FREQUENCIES)}"
        )
        raise ValueError(msg)


def _evaluate_task_trigger(
    trigger: str,
    config: Mapping[str, Any],
    context: CeremonyEvalContext,
) -> bool:
    """Evaluate a single task-driven trigger condition."""
    has_tasks = context.total_tasks_in_sprint > 0
    pct = context.sprint_percentage_complete

    if trigger == TRIGGER_SPRINT_START:
        return False

    if trigger == TRIGGER_SPRINT_END:
        return has_tasks and pct >= _DEFAULT_TRANSITION_THRESHOLD

    if trigger == TRIGGER_SPRINT_MIDPOINT:
        return has_tasks and pct >= _MIDPOINT_THRESHOLD

    if trigger == TRIGGER_EVERY_N:
        n: int = config.get(_KEY_EVERY_N, _DEFAULT_EVERY_N)
        return context.completions_since_last_trigger >= n

    if trigger == TRIGGER_SPRINT_PERCENTAGE:
        threshold: float = config.get(
            _KEY_SPRINT_PERCENTAGE,
            _DEFAULT_SPRINT_PCT,
        )
        return has_tasks and pct >= (threshold / _MAX_SPRINT_PCT)

    logger.warning(
        SPRINT_CEREMONY_SKIPPED,
        trigger=trigger,
        reason="unrecognized_trigger",
        valid_triggers=sorted(_VALID_TRIGGERS),
    )
    return False
