"""Evolution system event constants for structured logging.

Constants follow the ``evolution.<subject>.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

# ── Trigger events ───────────────────────────────────────────────

EVOLUTION_TRIGGER_REQUESTED: Final[str] = "evolution.trigger.requested"
EVOLUTION_TRIGGER_SKIPPED: Final[str] = "evolution.trigger.skipped"
EVOLUTION_TRIGGER_FAILED: Final[str] = "evolution.trigger.failed"

# ── Proposal events ─────────────────────────────────────────────

EVOLUTION_PROPOSAL_GENERATED: Final[str] = "evolution.proposal.generated"
EVOLUTION_PROPOSAL_REJECTED: Final[str] = "evolution.proposal.rejected"

# ── Proposer events ─────────────────────────────────────────────

EVOLUTION_PROPOSER_INIT: Final[str] = "evolution.proposer.init"
EVOLUTION_PROPOSER_ANALYZE: Final[str] = "evolution.proposer.analyze"
EVOLUTION_PROPOSER_PARSE_ERROR: Final[str] = "evolution.proposer.parse_error"
EVOLUTION_PROPOSER_ROUTE: Final[str] = "evolution.proposer.route"

# ── Guard events ─────────────────────────────────────────────────

EVOLUTION_GUARDS_PASSED: Final[str] = "evolution.guards.passed"
EVOLUTION_GUARDS_REJECTED: Final[str] = "evolution.guards.rejected"

# ── Adaptation events ───────────────────────────────────────────

EVOLUTION_ADAPTED: Final[str] = "evolution.adapted"
EVOLUTION_ADAPTATION_FAILED: Final[str] = "evolution.adaptation.failed"

# ── Rollback events ─────────────────────────────────────────────

EVOLUTION_ROLLBACK_TRIGGERED: Final[str] = "evolution.rollback.triggered"
EVOLUTION_ROLLBACK_FAILED: Final[str] = "evolution.rollback.failed"

# ── Rate limiting ───────────────────────────────────────────────

EVOLUTION_RATE_LIMITED: Final[str] = "evolution.rate_limited"

# ── Service-level events ────────────────────────────────────────

EVOLUTION_SERVICE_STARTED: Final[str] = "evolution.service.started"
EVOLUTION_SERVICE_COMPLETE: Final[str] = "evolution.service.complete"
EVOLUTION_CONTEXT_BUILD_FAILED: Final[str] = "evolution.context.build_failed"
