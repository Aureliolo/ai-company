"""Org memory event constants for structured logging.

Constants follow the ``org_memory.<entity>.<action>`` naming convention.
"""

from typing import Final

# ── Query operations ──────────────────────────────────────────────

ORG_MEMORY_QUERY_START: Final[str] = "org_memory.query.start"
ORG_MEMORY_QUERY_COMPLETE: Final[str] = "org_memory.query.complete"
ORG_MEMORY_QUERY_FAILED: Final[str] = "org_memory.query.failed"

# ── Write operations ─────────────────────────────────────────────

ORG_MEMORY_WRITE_START: Final[str] = "org_memory.write.start"
ORG_MEMORY_WRITE_COMPLETE: Final[str] = "org_memory.write.complete"
ORG_MEMORY_WRITE_DENIED: Final[str] = "org_memory.write.denied"
ORG_MEMORY_WRITE_FAILED: Final[str] = "org_memory.write.failed"

# ── Policy listing ───────────────────────────────────────────────

ORG_MEMORY_POLICIES_LISTED: Final[str] = "org_memory.policies.listed"

# ── Backend lifecycle ────────────────────────────────────────────

ORG_MEMORY_BACKEND_CREATED: Final[str] = "org_memory.backend.created"

# ── Model validation ────────────────────────────────────────────

ORG_MEMORY_MODEL_INVALID: Final[str] = "org_memory.model.invalid"
