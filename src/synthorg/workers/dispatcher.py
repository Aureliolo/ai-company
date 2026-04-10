"""Distributed dispatcher: observes task state changes, enqueues claims.

Registered with :meth:`TaskEngine.register_observer` at engine startup
when ``config.queue.enabled`` is true. The dispatcher is a passive
observer: it never mutates task state directly. Instead it publishes
claim messages to the JetStream work queue, and workers pull from
there to execute tasks.

Single-writer invariant: the dispatcher does not write task state.
Workers call the backend HTTP API to transition tasks, which routes
through the normal ``TaskEngine`` mutation queue. The dispatcher only
reacts to successful mutations and publishes the enqueue signal.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.workers import (
    WORKERS_DISPATCHER_CLAIM_ENQUEUED,
    WORKERS_DISPATCHER_PUBLISH_FAILED,
    WORKERS_DISPATCHER_QUEUE_NOT_RUNNING,
)
from synthorg.workers.claim import TaskClaim

if TYPE_CHECKING:
    from synthorg.engine.task_engine_models import TaskStateChanged
    from synthorg.workers.claim import JetStreamTaskQueue

logger = get_logger(__name__)

_DISPATCHABLE_TRANSITIONS: frozenset[str] = frozenset(
    {
        "assigned",
    },
)
"""Task statuses that trigger a claim enqueue.

The dispatcher fires when a task transitions *into* one of these
statuses. ``ASSIGNED`` is the "ready to run" state per the task
engine lifecycle (``CREATED -> ASSIGNED -> IN_PROGRESS``): a worker
picks up an assigned task, transitions it to ``IN_PROGRESS``, and
executes. Adding ``IN_PROGRESS`` here would cause double dispatch,
so it is deliberately omitted.

Values are matched case-insensitively against ``TaskStatus.value``.
"""


class DistributedDispatcher:
    """Observer that publishes task claims to the JetStream work queue.

    Args:
        task_queue: Connected :class:`JetStreamTaskQueue`.

    The dispatcher assumes the task queue is already started. Start
    it before registering the observer with the engine.
    """

    def __init__(self, *, task_queue: JetStreamTaskQueue) -> None:
        self._task_queue = task_queue

    async def on_task_state_changed(
        self,
        event: TaskStateChanged,
    ) -> None:
        """Handle a :class:`TaskStateChanged` event from the engine.

        Filters events to dispatchable status transitions and enqueues
        a claim for each matching task.
        """
        if not self._is_dispatchable(event):
            return

        if not self._task_queue.is_running:
            logger.warning(
                WORKERS_DISPATCHER_QUEUE_NOT_RUNNING,
                task_id=event.task_id,
            )
            return

        claim = self._build_claim(event)
        try:
            await self._task_queue.publish_claim(claim)
        except Exception:
            logger.exception(
                WORKERS_DISPATCHER_PUBLISH_FAILED,
                task_id=event.task_id,
            )
            return
        logger.info(
            WORKERS_DISPATCHER_CLAIM_ENQUEUED,
            task_id=event.task_id,
            new_status=claim.new_status,
        )

    @staticmethod
    def _is_dispatchable(event: TaskStateChanged) -> bool:
        """Return True if the event is a transition *into* a dispatchable status.

        Only fires when the task actually moves into one of the
        dispatchable statuses. Events that leave an already-assigned
        task in ``assigned`` (e.g., metadata edits, observer replays)
        are ignored so the same claim is never enqueued twice.
        """
        if event.new_status is None:
            return False
        new_value = str(event.new_status.value).lower()
        if new_value not in _DISPATCHABLE_TRANSITIONS:
            return False
        if event.previous_status is None:
            return True
        previous_value = str(event.previous_status.value).lower()
        return previous_value != new_value

    @staticmethod
    def _build_claim(event: TaskStateChanged) -> TaskClaim:
        """Build a :class:`TaskClaim` from a state-change event."""
        project_id: str | None = None
        if event.task is not None and event.task.project is not None:
            project_id = str(event.task.project)
        previous = None
        if event.previous_status is not None:
            previous = str(event.previous_status.value)
        return TaskClaim(
            task_id=event.task_id,
            project_id=project_id,
            previous_status=previous,
            new_status=str(event.new_status.value) if event.new_status else "unknown",
        )
