"""Memory consolidation event constants for structured logging.

Constants follow the ``consolidation.<entity>.<action>`` naming convention.
"""

from typing import Final

# ── Consolidation operations ──────────────────────────────────────

CONSOLIDATION_START: Final[str] = "consolidation.run.start"
CONSOLIDATION_COMPLETE: Final[str] = "consolidation.run.complete"
CONSOLIDATION_FAILED: Final[str] = "consolidation.run.failed"
CONSOLIDATION_SKIPPED: Final[str] = "consolidation.run.skipped"

# ── Retention cleanup ────────────────────────────────────────────

RETENTION_CLEANUP_START: Final[str] = "consolidation.retention.start"
RETENTION_CLEANUP_COMPLETE: Final[str] = "consolidation.retention.complete"

# ── Archival operations ──────────────────────────────────────────

ARCHIVAL_ENTRY_STORED: Final[str] = "consolidation.archival.stored"
ARCHIVAL_SEARCH_COMPLETE: Final[str] = "consolidation.archival.search_complete"

# ── Max memories enforcement ─────────────────────────────────────

MAX_MEMORIES_ENFORCED: Final[str] = "consolidation.max_memories.enforced"
