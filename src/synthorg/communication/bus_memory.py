"""Backward-compatibility shim for the in-memory message bus.

The in-memory implementation moved to ``synthorg.communication.bus.memory``
as part of the distributed runtime work (see ``docs/design/distributed-runtime.md``).
This module re-exports the public class and module-level constants so existing
absolute imports continue to work without changes.
"""

from synthorg.communication.bus.memory import (
    _IDLE_SUMMARY_INTERVAL_SECONDS,
    InMemoryMessageBus,
)

__all__ = ("_IDLE_SUMMARY_INTERVAL_SECONDS", "InMemoryMessageBus")
