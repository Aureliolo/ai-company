"""Evolution system event constants for structured logging.

Constants follow the ``evolution.<subject>.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

# ── Trigger events ───────────────────────────────────────────────

EVOLUTION_TRIGGER_REQUESTED: Final[str] = "evolution.trigger.requested"
EVOLUTION_TRIGGER_SKIPPED: Final[str] = "evolution.trigger.skipped"
EVOLUTION_TRIGGER_FAILED: Final[str] = "evolution.trigger.failed"
EVOLUTION_TRIGGER_RUN_RECORDED: Final[str] = "evolution.trigger.run_recorded"

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
EVOLUTION_REVIEW_GATE_APPROVED: Final[str] = "evolution.review_gate.approved"
EVOLUTION_REVIEW_GATE_REJECTED: Final[str] = "evolution.review_gate.rejected"

# ── Adaptation events ───────────────────────────────────────────

EVOLUTION_ADAPTED: Final[str] = "evolution.adaptation.applied"
EVOLUTION_ADAPTATION_FAILED: Final[str] = "evolution.adaptation.failed"

# ── Rollback events ─────────────────────────────────────────────

EVOLUTION_ROLLBACK_TRIGGERED: Final[str] = "evolution.rollback.triggered"
EVOLUTION_ROLLBACK_FAILED: Final[str] = "evolution.rollback.failed"

# ── Rate limiting ───────────────────────────────────────────────

EVOLUTION_RATE_LIMITED: Final[str] = "evolution.rate_limit.exceeded"

# ── Service-level events ────────────────────────────────────────

EVOLUTION_SERVICE_STARTED: Final[str] = "evolution.service.started"
EVOLUTION_SERVICE_COMPLETE: Final[str] = "evolution.service.complete"
EVOLUTION_CONTEXT_BUILD_FAILED: Final[str] = "evolution.context.build_failed"
EVOLUTION_CONTEXT_SNAPSHOT_FAILED: Final[str] = "evolution.context.snapshot_failed"
EVOLUTION_CONTEXT_MEMORY_FAILED: Final[str] = "evolution.context.memory_failed"

# ── Factory/config errors ──────────────────────────────────────

EVOLUTION_INVALID_STORE_TYPE: Final[str] = "evolution.store.invalid_type"
