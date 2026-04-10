"""HR event constants for structured logging.

Constants follow the ``hr.<subject>.<action>`` naming convention
and are passed as the first argument to structured log calls.
"""

from typing import Final

# ── Hiring ────────────────────────────────────────────────────────

HR_HIRING_REQUEST_CREATED: Final[str] = "hr.hiring.request_created"
HR_HIRING_CANDIDATE_GENERATED: Final[str] = "hr.hiring.candidate_generated"
HR_HIRING_APPROVAL_SUBMITTED: Final[str] = "hr.hiring.approval_submitted"
HR_HIRING_APPROVED: Final[str] = "hr.hiring.approved"
HR_HIRING_REJECTED: Final[str] = "hr.hiring.rejected"
HR_HIRING_INSTANTIATED: Final[str] = "hr.hiring.instantiated"

# ── Firing ────────────────────────────────────────────────────────

HR_FIRING_INITIATED: Final[str] = "hr.firing.initiated"
HR_FIRING_TASKS_REASSIGNED: Final[str] = "hr.firing.tasks_reassigned"
HR_FIRING_MEMORY_ARCHIVED: Final[str] = "hr.firing.memory_archived"
HR_FIRING_TEAM_NOTIFIED: Final[str] = "hr.firing.team_notified"
HR_FIRING_COMPLETE: Final[str] = "hr.firing.complete"

# ── Onboarding ───────────────────────────────────────────────────

HR_ONBOARDING_STARTED: Final[str] = "hr.onboarding.started"
HR_ONBOARDING_STEP_COMPLETE: Final[str] = "hr.onboarding.step_complete"
HR_ONBOARDING_COMPLETE: Final[str] = "hr.onboarding.complete"

# ── Registry ─────────────────────────────────────────────────────

HR_REGISTRY_AGENT_REGISTERED: Final[str] = "hr.registry.agent_registered"
HR_REGISTRY_AGENT_REMOVED: Final[str] = "hr.registry.agent_removed"
HR_REGISTRY_STATUS_UPDATED: Final[str] = "hr.registry.status_updated"
HR_REGISTRY_IDENTITY_UPDATED: Final[str] = "hr.registry.identity_updated"
HR_REGISTRY_IDENTITY_EVOLVED: Final[str] = "hr.registry.identity_evolved"

# ── Error-path events ───────────────────────────────────────────

HR_HIRING_INSTANTIATION_FAILED: Final[str] = "hr.hiring.instantiation_failed"
HR_FIRING_REASSIGNMENT_FAILED: Final[str] = "hr.firing.reassignment_failed"
HR_FIRING_ARCHIVAL_FAILED: Final[str] = "hr.firing.archival_failed"
HR_FIRING_NOTIFICATION_FAILED: Final[str] = "hr.firing.notification_failed"
HR_ARCHIVAL_ENTRY_FAILED: Final[str] = "hr.archival.entry_failed"

# ── Activity timeline ──────────────────────────────────────────

HR_ACTIVITY_REDACTION_MISMATCH: Final[str] = "hr.activity.redaction_pattern_mismatch"

# ── Pruning ────────────────────────────────────────────────────

HR_PRUNING_CYCLE_STARTED: Final[str] = "hr.pruning.cycle_started"
HR_PRUNING_EVALUATION_COMPLETE: Final[str] = "hr.pruning.evaluation_complete"
HR_PRUNING_AGENT_ELIGIBLE: Final[str] = "hr.pruning.agent_eligible"
HR_PRUNING_APPROVAL_SUBMITTED: Final[str] = "hr.pruning.approval_submitted"
HR_PRUNING_APPROVAL_DEDUP_SKIP: Final[str] = "hr.pruning.approval_dedup_skip"
HR_PRUNING_APPROVED: Final[str] = "hr.pruning.approved"
HR_PRUNING_REJECTED: Final[str] = "hr.pruning.rejected"
HR_PRUNING_OFFBOARDED: Final[str] = "hr.pruning.offboarded"
HR_PRUNING_CYCLE_COMPLETE: Final[str] = "hr.pruning.cycle_complete"
HR_PRUNING_POLICY_ERROR: Final[str] = "hr.pruning.policy_error"
HR_PRUNING_SCHEDULER_STARTED: Final[str] = "hr.pruning.scheduler_started"
HR_PRUNING_SCHEDULER_STOPPED: Final[str] = "hr.pruning.scheduler_stopped"
