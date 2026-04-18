"""Escalation queue repository protocol.

Re-exports the canonical ``EscalationQueueStore`` from the communication
subsystem under the persistence-layer naming convention so the boundary
linter finds one canonical import for callers inside ``persistence/``.
The concrete implementations live at
``persistence/{sqlite,postgres}/escalation_repo.py``.
"""

from synthorg.communication.conflict_resolution.escalation.protocol import (
    EscalationQueueStore as EscalationQueueRepository,
)

__all__ = ["EscalationQueueRepository"]
