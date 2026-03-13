"""Checkpoint recovery for agent crash recovery.

Persists ``AgentContext`` snapshots after each completed turn and
resumes from the last checkpoint on crash, preserving progress.
"""

from ai_company.engine.checkpoint.callback import CheckpointCallback
from ai_company.engine.checkpoint.callback_factory import make_checkpoint_callback
from ai_company.engine.checkpoint.models import (
    Checkpoint,
    CheckpointConfig,
    Heartbeat,
)
from ai_company.engine.checkpoint.strategy import CheckpointRecoveryStrategy

__all__ = [
    "Checkpoint",
    "CheckpointCallback",
    "CheckpointConfig",
    "CheckpointRecoveryStrategy",
    "Heartbeat",
    "make_checkpoint_callback",
]
