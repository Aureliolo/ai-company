"""Task engine event constants."""

from typing import Final

TASK_ENGINE_CREATED: Final[str] = "task_engine.created"
TASK_ENGINE_STARTED: Final[str] = "task_engine.started"
TASK_ENGINE_START_REJECTED: Final[str] = "task_engine.start.rejected"
"""Emitted when ``TaskEngine.start()`` refuses to start -- already running,
or unrestartable after a timed-out stop. Kept distinct from
``TASK_ENGINE_STARTED`` so rejected starts do not inflate successful-start
metrics / alerts."""
TASK_ENGINE_STOPPED: Final[str] = "task_engine.stopped"
TASK_ENGINE_MUTATION_RECEIVED: Final[str] = "task_engine.mutation.received"
TASK_ENGINE_MUTATION_APPLIED: Final[str] = "task_engine.mutation.applied"
TASK_ENGINE_MUTATION_FAILED: Final[str] = "task_engine.mutation.failed"
TASK_ENGINE_SNAPSHOT_PUBLISHED: Final[str] = "task_engine.snapshot.published"
TASK_ENGINE_SNAPSHOT_PUBLISH_FAILED: Final[str] = "task_engine.snapshot.publish_failed"
TASK_ENGINE_QUEUE_FULL: Final[str] = "task_engine.queue.full"
TASK_ENGINE_DRAIN_START: Final[str] = "task_engine.drain.start"
TASK_ENGINE_DRAIN_COMPLETE: Final[str] = "task_engine.drain.complete"
TASK_ENGINE_DRAIN_TIMEOUT: Final[str] = "task_engine.drain.timeout"
TASK_ENGINE_NOT_RUNNING: Final[str] = "task_engine.not_running"
TASK_ENGINE_VERSION_CONFLICT: Final[str] = "task_engine.version.conflict"
TASK_ENGINE_LOOP_ERROR: Final[str] = "task_engine.loop.error"
TASK_ENGINE_READ_FAILED: Final[str] = "task_engine.read.failed"
TASK_ENGINE_LIST_CAPPED: Final[str] = "task_engine.list.capped"
TASK_ENGINE_FUTURES_FAILED: Final[str] = "task_engine.futures.failed"
TASK_ENGINE_OBSERVER_FAILED: Final[str] = "task_engine.observer.failed"
TASK_ENGINE_OBSERVER_QUEUE_FULL: Final[str] = "task_engine.observer.queue_full"
TASK_ENGINE_OBSERVER_DRAIN_TIMEOUT: Final[str] = "task_engine.observer.drain_timeout"
TASK_ENGINE_LOOP_DIED: Final[str] = "task_engine.loop.died"
TASK_ENGINE_OBSERVER_LOOP_DIED: Final[str] = "task_engine.observer_loop.died"
