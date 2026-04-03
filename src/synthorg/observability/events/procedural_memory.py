"""Event constants for procedural memory auto-generation.

Used when a failed task execution triggers a proposer LLM call
to generate reusable procedural knowledge.
"""

from typing import Final

PROCEDURAL_MEMORY_START: Final[str] = "procedural_memory.proposal.start"
"""Pipeline started for a failed execution."""

PROCEDURAL_MEMORY_PAYLOAD_BUILT: Final[str] = "procedural_memory.payload.built"
"""Failure analysis payload constructed from execution data."""

PROCEDURAL_MEMORY_PROPOSED: Final[str] = "procedural_memory.proposal.complete"
"""Proposer LLM returned a valid proposal."""

PROCEDURAL_MEMORY_SKIPPED: Final[str] = "procedural_memory.proposal.skipped"
"""Proposal skipped (proposer returned None or disabled)."""

PROCEDURAL_MEMORY_LOW_CONFIDENCE: Final[str] = (
    "procedural_memory.proposal.low_confidence"
)
"""Proposal discarded because confidence was below threshold."""

PROCEDURAL_MEMORY_STORED: Final[str] = "procedural_memory.entry.stored"
"""Procedural memory entry stored in backend."""

PROCEDURAL_MEMORY_STORE_FAILED: Final[str] = "procedural_memory.entry.store_failed"
"""Failed to store procedural memory entry."""

PROCEDURAL_MEMORY_ERROR: Final[str] = "procedural_memory.error"
"""Unrecoverable error in procedural memory pipeline."""

PROCEDURAL_MEMORY_DISABLED: Final[str] = "procedural_memory.disabled"
"""Procedural memory generation is disabled in config."""

PROCEDURAL_MEMORY_SKILL_MD: Final[str] = "procedural_memory.skill_md.written"
"""SKILL.md file materialized from a procedural memory proposal."""
