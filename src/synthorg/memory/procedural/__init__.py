"""Procedural memory auto-generation from agent failures.

Provides a proposer pipeline that analyses failed task executions
using a separate LLM call and produces structured procedural memory
entries (``MemoryCategory.PROCEDURAL``).
"""

from synthorg.memory.procedural.models import (
    FailureAnalysisPayload,
    ProceduralMemoryConfig,
    ProceduralMemoryProposal,
)
from synthorg.memory.procedural.pipeline import propose_procedural_memory
from synthorg.memory.procedural.proposer import ProceduralMemoryProposer

__all__ = [
    "FailureAnalysisPayload",
    "ProceduralMemoryConfig",
    "ProceduralMemoryProposal",
    "ProceduralMemoryProposer",
    "propose_procedural_memory",
]
