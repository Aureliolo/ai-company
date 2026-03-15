"""Intra-loop stagnation detection.

Detects repetitive tool-call patterns within execution loops and
intervenes with corrective prompt injection or early termination.

Re-exports the public API: config, models, protocol, and default
detector implementation.
"""

from synthorg.engine.stagnation.detector import ToolRepetitionDetector
from synthorg.engine.stagnation.models import (
    StagnationConfig,
    StagnationResult,
    StagnationVerdict,
)
from synthorg.engine.stagnation.protocol import StagnationDetector

__all__ = [
    "StagnationConfig",
    "StagnationDetector",
    "StagnationResult",
    "StagnationVerdict",
    "ToolRepetitionDetector",
]
