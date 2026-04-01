"""Ceremony scheduler -- runtime coordination between sprints and meetings.

The ``CeremonyScheduler`` owns ceremony trigger state (counters,
fired-once tracking) and delegates scheduling decisions to the active
``CeremonySchedulingStrategy``.  It bridges triggered ceremonies into
``MeetingScheduler.trigger_event()`` calls.

See ``docs/design/ceremony-scheduling.md`` for the full design.
"""

import asyncio
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
    from synthorg.engine.workflow.sprint_config import (
        SprintCeremonyConfig,
        SprintConfig,
    )
    from synthorg.engine.workflow.sprint_velocity import VelocityRecord

logger = get_logger(__name__)

_MIDPOINT_THRESHOLD: float = 0.5
_COMPLETE_THRESHOLD: float = 1.0


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
        If activation fails partway through, the scheduler is
        deactivated to avoid partial state.

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

        try:
            await strategy.on_sprint_activated(sprint, config)
            await self._fire_sprint_start_ceremonies(sprint, config)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SPRINT_CEREMONY_SCHEDULER_STARTED,
                sprint_id=sprint.id,
                note="activation failed, deactivating",
            )
            await self.deactivate_sprint()
            raise

        logger.info(
            SPRINT_CEREMONY_SCHEDULER_STARTED,
            sprint_id=sprint.id,
            strategy=strategy.strategy_type.value,
            ceremony_count=len(config.ceremonies),
        )

    async def deactivate_sprint(self) -> None:
        """Stop tracking the current sprint's ceremonies.

        Calls the strategy's ``on_sprint_deactivated`` hook.
        No-op if the scheduler is not running.
        """
        if not self._running:
            logger.debug(
                SPRINT_CEREMONY_SCHEDULER_STOPPED,
                note="already_inactive",
            )
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
            logger.debug(
                SPRINT_CEREMONY_TRIGGERED,
                note="scheduler_not_active",
                task_id=task_id,
            )
            return sprint
        assert self._sprint_config is not None  # noqa: S101

        self._active_sprint = sprint
        self._total_completions += 1

        context = self._build_context(sprint)
        await self._active_strategy.on_task_completed(
            sprint,
            task_id,
            story_points,
            context,
        )
        await self._evaluate_ceremonies(sprint)
        await self._check_one_shot_triggers(sprint, context)
        return self._check_auto_transition(sprint, context)

    # -- Ceremony evaluation -------------------------------------------------

    async def _evaluate_ceremonies(self, sprint: Sprint) -> None:
        """Evaluate and fire per-task ceremonies."""
        assert self._sprint_config is not None  # noqa: S101
        assert self._active_strategy is not None  # noqa: S101

        for ceremony in self._sprint_config.ceremonies:
            self._completion_counters[ceremony.name] += 1

            if self._is_one_shot_fired(ceremony.name):
                continue

            ctx = self._build_ceremony_context(ceremony.name, sprint)
            if self._active_strategy.should_fire_ceremony(
                ceremony,
                sprint,
                ctx,
            ):
                success = await self._trigger_ceremony(
                    ceremony.name,
                    sprint,
                )
                if success:
                    self._completion_counters[ceremony.name] = 0

    def _check_auto_transition(
        self,
        sprint: Sprint,
        context: CeremonyEvalContext,
    ) -> Sprint:
        """Check and apply auto-transition if strategy says so."""
        assert self._active_strategy is not None  # noqa: S101
        assert self._sprint_config is not None  # noqa: S101

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

    # -- One-shot ceremonies -------------------------------------------------

    async def _fire_sprint_start_ceremonies(
        self,
        sprint: Sprint,
        config: SprintConfig,
    ) -> None:
        """Fire ceremonies configured with sprint_start trigger."""
        tasks: list[tuple[str, Sprint]] = []
        for ceremony in config.ceremonies:
            if ceremony.policy_override is None:
                continue
            sc = ceremony.policy_override.strategy_config or {}
            if sc.get("trigger") == "sprint_start":
                tasks.append((ceremony.name, sprint))

        await self._fire_ceremonies_parallel(tasks)

    async def _check_one_shot_triggers(
        self,
        sprint: Sprint,
        context: CeremonyEvalContext,
    ) -> None:
        """Check and fire midpoint/end one-shot ceremonies."""
        if self._sprint_config is None:
            return

        tasks: list[tuple[str, Sprint]] = []
        for ceremony in self._sprint_config.ceremonies:
            trigger = _get_trigger(ceremony)
            if trigger is None:
                continue
            not_fired = ceremony.name not in self._fired_once_triggers
            pct = context.sprint_percentage_complete

            is_midpoint = trigger == "sprint_midpoint" and pct >= _MIDPOINT_THRESHOLD
            is_end = trigger == "sprint_end" and pct >= _COMPLETE_THRESHOLD
            if not_fired and (is_midpoint or is_end):
                tasks.append((ceremony.name, sprint))

        await self._fire_ceremonies_parallel(tasks)

    async def _fire_ceremonies_parallel(
        self,
        ceremonies: list[tuple[str, Sprint]],
    ) -> None:
        """Fire multiple ceremonies in parallel, marking one-shots."""
        if not ceremonies:
            return

        async def _fire(name: str, sprint: Sprint) -> tuple[str, bool]:
            success = await self._trigger_ceremony(name, sprint)
            return (name, success)

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_fire(name, sprint)) for name, sprint in ceremonies]

        for task in tasks:
            name, success = task.result()
            if success:
                self._fired_once_triggers.add(name)

    # -- Context building ----------------------------------------------------

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
            # Budget integration is a follow-up (#972).
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
            # Budget integration is a follow-up (#972).
            budget_consumed_fraction=0.0,
            budget_remaining=0.0,
            velocity_history=self._velocity_history,
            external_events=(),
            sprint_percentage_complete=pct,
            story_points_completed=sprint.story_points_completed,
            story_points_committed=sprint.story_points_committed,
        )

    # -- Trigger execution ---------------------------------------------------

    def _is_one_shot_fired(self, ceremony_name: str) -> bool:
        """Check if a one-shot ceremony has already fired."""
        return ceremony_name in self._fired_once_triggers

    async def _trigger_ceremony(
        self,
        ceremony_name: str,
        sprint: Sprint,
    ) -> bool:
        """Fire a ceremony via MeetingScheduler.trigger_event.

        Returns:
            ``True`` if the ceremony was successfully triggered,
            ``False`` if the trigger failed (logged and swallowed).
        """
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
            return False
        return True


def _get_trigger(ceremony: SprintCeremonyConfig) -> str | None:
    """Extract the trigger string from a ceremony's policy override."""
    if ceremony.policy_override is None:
        return None
    sc = ceremony.policy_override.strategy_config or {}
    return sc.get("trigger")
