"""Checkpoint callback type alias.

The callback is invoked after each completed turn with the current
``AgentContext``.  Implementations persist a checkpoint and update
the heartbeat.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from ai_company.engine.context import AgentContext

CheckpointCallback = Callable[[AgentContext], Coroutine[Any, Any, None]]
"""Async callback invoked after each turn to persist a checkpoint."""
