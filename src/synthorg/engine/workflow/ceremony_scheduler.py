"""Ceremony scheduler -- runtime coordination between sprints and meetings.

The ``CeremonyScheduler`` owns ceremony trigger state (counters,
fired-once tracking) and delegates scheduling decisions to the active
``CeremonySchedulingStrategy``.  It bridges triggered ceremonies into
``MeetingScheduler.trigger_event()`` calls.

See ``docs/design/ceremony-scheduling.md`` for the full design.
"""

import time
from typing import TYPE_CHECKING, Any

from synthorg.engine.workflow.ceremony_bridge import (
    build_trigger_event_name,
)
from synthorg.engine.workflow.ceremony_context import CeremonyEvalContext
from synthorg.engine.workflow.sprint_lifecycle import Sprint, SprintStatus
from synthorg.observability import get_logger
from synthorg.observability.events.workflow import (
    SPRINT_AUTO_TRANSITION,
    SPRINT_CEREMONY_SCHEDULER_STARTED,
    SPRINT_CEREMONY_SCHEDULER_STOPPED,
    SPRINT_CEREMONY_TRIGGERED,
)

if TYPE_CHECKING:
    from synthorg.communication.meeting.scheduler import MeetingScheduler
    from synthorg.engine.workflow.ceremony_strategy import (
        CeremonySchedulingStrategy,
    )
    from synthorg.engine.workflow.sprint_config import SprintConfig
    from synthorg.engine.workflow.sprint_velocity import VelocityRecord

logger = get_logger(__name__)


class CeremonyScheduler:
    """Runtime coordinator between sprint lifecycle and meeting system.

    Owns ceremony trigger state (counters, fired-once tracking).
    Delegates scheduling decisions to the active
    ``CeremonySchedulingStrategy``.  Delegates meeting execution to the
    existing ``MeetingScheduler``.

    Strategy is locked per-sprint (set at ``activate_sprint`` time).
    Counters are ephemeral and reset per sprint.

    Args:
        meeting_scheduler: The existing MeetingScheduler for executing
            ceremonies as meetings.
    """

    __slots__ = (
        "_activation_time",
        "_active_sprint",
        "_active_strategy",
        "_completion_counters",
        "_fired_once_triggers",
        "_meeting_scheduler",
        "_running",
        "_sprint_config",
        "_total_completions",
        "_velocity_history",
    )

    def __init__(
        self,
        *,
        meeting_scheduler: MeetingScheduler,
    ) -> None:
        self._meeting_scheduler = meeting_scheduler
        self._active_strategy: CeremonySchedulingStrategy | None = None
        self._active_sprint: Sprint | None = None
        self._sprint_config: SprintConfig | None = None
        self._completion_counters: dict[str, int] = {}
        self._fired_once_triggers: set[str] = set()
        self._total_completions: int = 0
        self._running = False
        self._activation_time: float = 0.0
        self._velocity_history: tuple[VelocityRecord, ...] = ()

    @property
    def running(self) -> bool:
        """Whether the scheduler has an active sprint."""
        return self._running

    @property
    def active_sprint(self) -> Sprint | None:
        """The currently active sprint, or None."""
        return self._active_sprint

    async def activate_sprint(
        self,
        sprint: Sprint,
        config: SprintConfig,
        strategy: CeremonySchedulingStrategy,
        *,
        velocity_history: tuple[VelocityRecord, ...] = (),
    ) -> None:
        """Start tracking ceremonies for the given sprint.

        Initializes counters, locks the strategy, and calls the
        strategy's ``on_sprint_activated`` hook.

        Fires any ``sprint_start`` one-shot ceremonies immediately.

        Args:
            sprint: The sprint to activate (should be ACTIVE).
            config: Sprint configuration.
            strategy: The ceremony scheduling strategy to use.
            velocity_history: Recent velocity records for context.
        """
        if self._running:
            await self.deactivate_sprint()

        self._active_sprint = sprint
        self._sprint_config = config
        self._active_strategy = strategy
        self._velocity_history = velocity_history
        self._completion_counters = {c.name: 0 for c in config.ceremonies}
        self._fired_once_triggers = set()
        self._total_completions = 0
        self._activation_time = time.monotonic()
        self._running = True

        await strategy.on_sprint_activated(sprint, config)

        # Fire sprint_start one-shot ceremonies.
        await self._fire_sprint_start_ceremonies(sprint, config)

        logger.info(
            SPRINT_CEREMONY_SCHEDULER_STARTED,
            sprint_id=sprint.id,
            strategy=strategy.strategy_type.value,
            ceremony_count=len(config.ceremonies),
        )

    async def deactivate_sprint(self) -> None:
        """Stop tracking the current sprint's ceremonies.

        Calls the strategy's ``on_sprint_deactivated`` hook.
        """
        if not self._running:
            return

        if self._active_strategy is not None:
            await self._active_strategy.on_sprint_deactivated()

        sprint_id = self._active_sprint.id if self._active_sprint else "unknown"

        self._active_sprint = None
        self._sprint_config = None
        self._active_strategy = None
        self._completion_counters = {}
        self._fired_once_triggers = set()
        self._total_completions = 0
        self._running = False

        logger.info(
            SPRINT_CEREMONY_SCHEDULER_STOPPED,
            sprint_id=sprint_id,
        )

    async def on_task_completed(
        self,
        sprint: Sprint,
        task_id: str,
        story_points: float,
    ) -> Sprint:
        """Handle a task completion event.

        Evaluates all trigger-based ceremonies via the active strategy,
        fires matching ones via ``MeetingScheduler.trigger_event()``,
        and checks auto-transition.

        Args:
            sprint: Current sprint state (after task completion).
            task_id: The completed task ID.
            story_points: Points earned.

        Returns:
            The sprint, possibly transitioned to IN_REVIEW.
        """
        if not self._running or self._active_strategy is None:
            return sprint
        assert self._sprint_config is not None  # noqa: S101

        self._active_sprint = sprint
        self._total_completions += 1

        # Build context for this evaluation.
        context = self._build_context(sprint)

        # Notify strategy.
        await self._active_strategy.on_task_completed(
            sprint,
            task_id,
            story_points,
            context,
        )

        # Evaluate each ceremony.
        for ceremony in self._sprint_config.ceremonies:
            self._completion_counters.setdefault(ceremony.name, 0)
            self._completion_counters[ceremony.name] += 1

            ceremony_context = self._build_ceremony_context(
                ceremony.name,
                sprint,
            )

            if self._is_one_shot_fired(ceremony.name):
                continue

            if self._active_strategy.should_fire_ceremony(
                ceremony,
                sprint,
                ceremony_context,
            ):
                await self._trigger_ceremony(ceremony.name, sprint)
                self._completion_counters[ceremony.name] = 0

        # Check for midpoint and end one-shots.
        await self._check_one_shot_triggers(sprint, context)

        # Check auto-transition.
        target = self._active_strategy.should_transition_sprint(
            sprint,
            self._sprint_config,
            context,
        )
        if target is not None and sprint.status is SprintStatus.ACTIVE:
            logger.info(
                SPRINT_AUTO_TRANSITION,
                sprint_id=sprint.id,
                from_status=sprint.status.value,
                to_status=target.value,
                strategy=self._active_strategy.strategy_type.value,
            )
            sprint = sprint.with_transition(target)
            self._active_sprint = sprint

        return sprint

    # -- Internal helpers ----------------------------------------------------

    def _build_context(self, sprint: Sprint) -> CeremonyEvalContext:
        """Build a CeremonyEvalContext for the current state."""
        total_tasks = len(sprint.task_ids)
        completed = len(sprint.completed_task_ids)
        pct = completed / total_tasks if total_tasks > 0 else 0.0

        return CeremonyEvalContext(
            completions_since_last_trigger=self._total_completions,
            total_completions_this_sprint=self._total_completions,
            total_tasks_in_sprint=total_tasks,
            elapsed_seconds=time.monotonic() - self._activation_time,
            budget_consumed_fraction=0.0,
            budget_remaining=0.0,
            velocity_history=self._velocity_history,
            external_events=(),
            sprint_percentage_complete=pct,
            story_points_completed=sprint.story_points_completed,
            story_points_committed=sprint.story_points_committed,
        )

    def _build_ceremony_context(
        self,
        ceremony_name: str,
        sprint: Sprint,
    ) -> CeremonyEvalContext:
        """Build context for a specific ceremony (per-ceremony counter)."""
        total_tasks = len(sprint.task_ids)
        completed = len(sprint.completed_task_ids)
        pct = completed / total_tasks if total_tasks > 0 else 0.0

        return CeremonyEvalContext(
            completions_since_last_trigger=self._completion_counters.get(
                ceremony_name,
                0,
            ),
            total_completions_this_sprint=self._total_completions,
            total_tasks_in_sprint=total_tasks,
            elapsed_seconds=time.monotonic() - self._activation_time,
            budget_consumed_fraction=0.0,
            budget_remaining=0.0,
            velocity_history=self._velocity_history,
            external_events=(),
            sprint_percentage_complete=pct,
            story_points_completed=sprint.story_points_completed,
            story_points_committed=sprint.story_points_committed,
        )

    def _is_one_shot_fired(self, ceremony_name: str) -> bool:
        """Check if a one-shot ceremony has already fired."""
        return ceremony_name in self._fired_once_triggers

    async def _fire_sprint_start_ceremonies(
        self,
        sprint: Sprint,
        config: SprintConfig,
    ) -> None:
        """Fire ceremonies configured with sprint_start trigger."""
        for ceremony in config.ceremonies:
            if ceremony.policy_override is None:
                continue
            sc = ceremony.policy_override.strategy_config or {}
            if sc.get("trigger") == "sprint_start":
                await self._trigger_ceremony(ceremony.name, sprint)
                self._fired_once_triggers.add(ceremony.name)

    _MIDPOINT_THRESHOLD: float = 0.5
    _COMPLETE_THRESHOLD: float = 1.0

    async def _check_one_shot_triggers(
        self,
        sprint: Sprint,
        context: CeremonyEvalContext,
    ) -> None:
        """Check and fire midpoint/end one-shot ceremonies."""
        if self._sprint_config is None:
            return

        for ceremony in self._sprint_config.ceremonies:
            if ceremony.policy_override is None:
                continue
            sc = ceremony.policy_override.strategy_config or {}
            trigger = sc.get("trigger")
            not_fired = ceremony.name not in self._fired_once_triggers
            pct = context.sprint_percentage_complete

            is_midpoint = (
                trigger == "sprint_midpoint" and pct >= self._MIDPOINT_THRESHOLD
            )
            is_end = trigger == "sprint_end" and pct >= self._COMPLETE_THRESHOLD
            if not_fired and (is_midpoint or is_end):
                await self._trigger_ceremony(ceremony.name, sprint)
                self._fired_once_triggers.add(ceremony.name)

    async def _trigger_ceremony(
        self,
        ceremony_name: str,
        sprint: Sprint,
    ) -> None:
        """Fire a ceremony via MeetingScheduler.trigger_event."""
        event_name = build_trigger_event_name(ceremony_name, sprint.id)
        context: dict[str, Any] = {
            "sprint_id": sprint.id,
            "ceremony": ceremony_name,
            "completed_tasks": len(sprint.completed_task_ids),
            "total_tasks": len(sprint.task_ids),
        }

        logger.info(
            SPRINT_CEREMONY_TRIGGERED,
            ceremony=ceremony_name,
            sprint_id=sprint.id,
            event_name=event_name,
        )

        try:
            await self._meeting_scheduler.trigger_event(
                event_name,
                context=context,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SPRINT_CEREMONY_TRIGGERED,
                ceremony=ceremony_name,
                sprint_id=sprint.id,
                note="trigger_event failed",
            )
