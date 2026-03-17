"""Compaction callback type alias.

Follows the ``CheckpointCallback`` pattern — a simple callable type
alias rather than a protocol class, since the callback has a single
responsibility with no configuration methods.
"""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from synthorg.engine.context import AgentContext

CompactionCallback = Callable[
    ["AgentContext"],
    Coroutine[Any, Any, "AgentContext | None"],
]
"""Async callback invoked at turn boundaries to compress conversation.

Receives the current ``AgentContext`` and returns either:

- A new ``AgentContext`` with compressed conversation (compaction ran).
- ``None`` to signal no compaction was needed or possible.
"""
