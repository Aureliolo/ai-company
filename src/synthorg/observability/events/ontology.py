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
