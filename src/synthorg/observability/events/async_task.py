"""Async task protocol event constants."""

from typing import Final

# Async task lifecycle
ASYNC_TASK_STARTED: Final[str] = "async_task.started"
ASYNC_TASK_START_FAILED: Final[str] = "async_task.start_failed"
ASYNC_TASK_CHECKED: Final[str] = "async_task.checked"
ASYNC_TASK_UPDATED: Final[str] = "async_task.updated"
ASYNC_TASK_UPDATE_FAILED: Final[str] = "async_task.update_failed"
ASYNC_TASK_CANCELLED: Final[str] = "async_task.cancelled"
ASYNC_TASK_CANCEL_FAILED: Final[str] = "async_task.cancel_failed"
ASYNC_TASK_LISTED: Final[str] = "async_task.listed"
ASYNC_TASK_STATE_CHANNEL_UPDATED: Final[str] = "async_task.state_channel.updated"

# Delegation round limits
DELEGATION_ROUND_SOFT_LIMIT: Final[str] = "delegation.round.soft_limit"
DELEGATION_ROUND_HARD_LIMIT: Final[str] = "delegation.round.hard_limit"
