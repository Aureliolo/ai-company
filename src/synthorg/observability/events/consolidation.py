"""Memory consolidation event constants for structured logging.

Constants follow the ``consolidation.<entity>.<action>`` naming convention.
"""

from typing import Final

# ── Maintenance orchestration ─────────────────────────────────────

MAINTENANCE_START: Final[str] = "consolidation.maintenance.start"
MAINTENANCE_COMPLETE: Final[str] = "consolidation.maintenance.complete"
MAINTENANCE_FAILED: Final[str] = "consolidation.maintenance.failed"

# ── Consolidation operations ──────────────────────────────────────

CONSOLIDATION_START: Final[str] = "consolidation.run.start"
CONSOLIDATION_COMPLETE: Final[str] = "consolidation.run.complete"
CONSOLIDATION_FAILED: Final[str] = "consolidation.run.failed"
CONSOLIDATION_SKIPPED: Final[str] = "consolidation.run.skipped"

# ── Strategy operations ──────────────────────────────────────────

STRATEGY_START: Final[str] = "consolidation.strategy.start"
STRATEGY_COMPLETE: Final[str] = "consolidation.strategy.complete"

# ── Retention cleanup ────────────────────────────────────────────

RETENTION_CLEANUP_START: Final[str] = "consolidation.retention.start"
RETENTION_CLEANUP_COMPLETE: Final[str] = "consolidation.retention.complete"
RETENTION_CLEANUP_FAILED: Final[str] = "consolidation.retention.failed"
RETENTION_DELETE_SKIPPED: Final[str] = "consolidation.retention.delete_skipped"
RETENTION_AGENT_OVERRIDE_APPLIED: Final[str] = (
    "consolidation.retention.agent_override_applied"
)

# ── Archival operations ──────────────────────────────────────────

ARCHIVAL_ENTRY_STORED: Final[str] = "consolidation.archival.stored"
ARCHIVAL_SEARCH_COMPLETE: Final[str] = "consolidation.archival.search_complete"
ARCHIVAL_FAILED: Final[str] = "consolidation.archival.failed"

# ── Density classification ──────────────────────────────────────

DENSITY_CLASSIFICATION_COMPLETE: Final[str] = "consolidation.density.classified"

# ── Dual-mode strategy ─────────────────────────────────────────

DUAL_MODE_GROUP_CLASSIFIED: Final[str] = "consolidation.dual_mode.group_classified"
DUAL_MODE_ABSTRACTIVE_SUMMARY: Final[str] = (
    "consolidation.dual_mode.abstractive_summary"
)
DUAL_MODE_ABSTRACTIVE_FALLBACK: Final[str] = (
    "consolidation.dual_mode.abstractive_fallback"
)
DUAL_MODE_EXTRACTIVE_PRESERVED: Final[str] = (
    "consolidation.dual_mode.extractive_preserved"
)

# ── Archival index ──────────────────────────────────────────────

ARCHIVAL_INDEX_BUILT: Final[str] = "consolidation.archival.index_built"

# ── Max memories enforcement ─────────────────────────────────────

MAX_MEMORIES_ENFORCED: Final[str] = "consolidation.max_memories.enforced"
MAX_MEMORIES_ENFORCE_FAILED: Final[str] = "consolidation.max_memories.failed"

# ── LLM consolidation strategy ──────────────────────────────────

LLM_STRATEGY_SYNTHESIZED: Final[str] = "consolidation.llm.synthesized"
LLM_STRATEGY_FALLBACK: Final[str] = "consolidation.llm.fallback"
LLM_STRATEGY_ERROR: Final[str] = "consolidation.llm.error"

# ── Distillation capture ────────────────────────────────────────

DISTILLATION_CAPTURED: Final[str] = "consolidation.distillation.captured"
DISTILLATION_CAPTURE_FAILED: Final[str] = "consolidation.distillation.capture_failed"
DISTILLATION_CAPTURE_SKIPPED: Final[str] = "consolidation.distillation.capture_skipped"
