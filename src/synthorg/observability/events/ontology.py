"""Ontology event name constants for observability."""

from typing import Final

# ── Entity lifecycle ────────────────────────────────────────────

ONTOLOGY_ENTITY_REGISTERED: Final[str] = "ontology.entity.registered"
"""Entity definition registered in the backend."""

ONTOLOGY_ENTITY_UPDATED: Final[str] = "ontology.entity.updated"
"""Entity definition updated in the backend."""

ONTOLOGY_ENTITY_DELETED: Final[str] = "ontology.entity.deleted"
"""Entity definition deleted from the backend."""

# ── Bootstrap ───────────────────────────────────────────────────

ONTOLOGY_BOOTSTRAP_COMPLETED: Final[str] = "ontology.bootstrap.completed"
"""Ontology bootstrap completed successfully."""

ONTOLOGY_BOOTSTRAP_ENTITY_SKIPPED: Final[str] = "ontology.bootstrap.entity_skipped"
"""Entity skipped during bootstrap (already registered)."""

# ── Versioning ──────────────────────────────────────────────────

ONTOLOGY_VERSION_SNAPSHOT: Final[str] = "ontology.version.snapshot"
"""Version snapshot created for an entity definition."""

# ── Config ──────────────────────────────────────────────────────

ONTOLOGY_CONFIG_LOADED: Final[str] = "ontology.config.loaded"
"""Ontology configuration loaded successfully."""

# ── Backend lifecycle ───────────────────────────────────────────

ONTOLOGY_BACKEND_CONNECTING: Final[str] = "ontology.backend.connecting"
"""Ontology backend connection attempt started."""

ONTOLOGY_BACKEND_CONNECTION_FAILED: Final[str] = "ontology.backend.connection_failed"
"""Ontology backend connection attempt failed."""

ONTOLOGY_BACKEND_CONNECTED: Final[str] = "ontology.backend.connected"
"""Ontology backend connected successfully."""

ONTOLOGY_BACKEND_DISCONNECTED: Final[str] = "ontology.backend.disconnected"
"""Ontology backend disconnected."""

ONTOLOGY_BACKEND_HEALTH_CHECK: Final[str] = "ontology.backend.health_check"
"""Ontology backend health check executed."""

# ── Search ──────────────────────────────────────────────────────

ONTOLOGY_SEARCH_EXECUTED: Final[str] = "ontology.search.executed"
"""Entity search query executed."""

# ── Schema ──────────────────────────────────────────────────────

ONTOLOGY_SCHEMA_FAILED: Final[str] = "ontology.backend.schema_failed"
"""Ontology schema application failed."""

# ── Auto-wire ───────────────────────────────────────────────────

ONTOLOGY_AUTO_WIRE_FAILED: Final[str] = "ontology.auto_wire.failed"
"""Ontology auto-wiring failed during startup."""

# ── Decorator ──────────────────────────────────────────────────

ONTOLOGY_ENTITY_DECORATOR_REGISTERED: Final[str] = (
    "ontology.entity.decorator_registered"
)
"""Entity model registered via ``@ontology_entity`` decorator."""

# ── Deserialization ─────────────────────────────────────────────

ONTOLOGY_ENTITY_DESERIALIZATION_FAILED: Final[str] = (
    "ontology.entity.deserialization_failed"
)
"""Entity definition deserialization from database failed."""

# ── Injection ──────────────────────────────────────────────────

ONTOLOGY_INJECTION_PREPARED: Final[str] = "ontology.injection.prepared"
"""Ontology context injection messages prepared for agent."""

ONTOLOGY_TOOL_LOOKUP: Final[str] = "ontology.tool.lookup"
"""Agent invoked the entity lookup tool."""

# ── Delegation guard ───────────────────────────────────────────

ONTOLOGY_GUARD_STAMPED: Final[str] = "ontology.guard.stamped"
"""Entity version manifest stamped onto delegation record."""

ONTOLOGY_GUARD_DRIFT_DETECTED: Final[str] = "ontology.guard.drift_detected"
"""Entity version drift detected during delegation validation."""

ONTOLOGY_GUARD_BLOCKED: Final[str] = "ontology.guard.blocked"
"""Delegation blocked due to stale entity versions (enforce mode)."""

# ── Memory wrapper ─────────────────────────────────────────────

ONTOLOGY_MEMORY_TAGGED: Final[str] = "ontology.memory.tagged"
"""Memory entry auto-tagged with entity references."""

ONTOLOGY_MEMORY_DRIFT_WARNED: Final[str] = "ontology.memory.drift_warned"
"""Memory content diverges from canonical entity definition."""

ONTOLOGY_MEMORY_ENRICHED: Final[str] = "ontology.memory.enriched"
"""Retrieved memory entries enriched with entity version info."""

# ── Drift detection ────────────────────────────────────────────

ONTOLOGY_DRIFT_CHECK_STARTED: Final[str] = "ontology.drift.check_started"
"""Drift detection check started for entity."""

ONTOLOGY_DRIFT_CHECK_COMPLETED: Final[str] = "ontology.drift.check_completed"
"""Drift detection check completed for entity."""

ONTOLOGY_DRIFT_DETECTED: Final[str] = "ontology.drift.detected"
"""Semantic drift detected for entity above threshold."""

# ── OrgMemory sync ─────────────────────────────────────────────

ONTOLOGY_SYNC_PUBLISHED: Final[str] = "ontology.sync.published"
"""Entity definition published as OrgFact."""

ONTOLOGY_SYNC_SKIPPED: Final[str] = "ontology.sync.skipped"
"""Entity sync skipped (content unchanged)."""

ONTOLOGY_ADMIN_SYNC_COMPLETED: Final[str] = "ontology.admin.sync_completed"
"""Admin-triggered OrgMemory sync completed."""
