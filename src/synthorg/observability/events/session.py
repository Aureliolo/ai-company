"""Session replay event constants."""

from typing import Final

SESSION_REPLAY_START: Final[str] = "session.replay.start"
SESSION_REPLAY_COMPLETE: Final[str] = "session.replay.complete"
SESSION_REPLAY_PARTIAL: Final[str] = "session.replay.partial"
SESSION_REPLAY_NO_EVENTS: Final[str] = "session.replay.no_events"
SESSION_REPLAY_ERROR: Final[str] = "session.replay.error"
SESSION_REPLAY_LOW_COMPLETENESS: Final[str] = "session.replay.low_completeness"
SESSION_TASK_STATUS_CHANGED: Final[str] = "session.task.status_changed"
