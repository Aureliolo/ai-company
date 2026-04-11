"""HR domain enumerations."""

from enum import StrEnum


class HiringRequestStatus(StrEnum):
    """Status of a hiring request through the approval pipeline."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    INSTANTIATED = "instantiated"


class FiringReason(StrEnum):
    """Reason for agent termination."""

    MANUAL = "manual"
    PERFORMANCE = "performance"
    BUDGET = "budget"
    PROJECT_COMPLETION = "project_completion"


class OnboardingStep(StrEnum):
    """Steps in the agent onboarding checklist."""

    COMPANY_CONTEXT = "company_context"
    PROJECT_BRIEFING = "project_briefing"
    TEAM_INTRODUCTIONS = "team_introductions"
    LEARNED_FROM_SENIORS = "learned_from_seniors"


class LifecycleEventType(StrEnum):
    """Type of agent lifecycle event."""

    HIRED = "hired"
    ONBOARDED = "onboarded"
    FIRED = "fired"
    OFFBOARDED = "offboarded"
    STATUS_CHANGED = "status_changed"
    PROMOTED = "promoted"
    DEMOTED = "demoted"


class ActivityEventType(StrEnum):
    """Event types produced by the activity feed timeline.

    Superset of ``LifecycleEventType`` plus operational event types
    generated from task metrics, cost records, tool invocations,
    and delegation records.
    """

    HIRED = "hired"
    ONBOARDED = "onboarded"
    FIRED = "fired"
    OFFBOARDED = "offboarded"
    STATUS_CHANGED = "status_changed"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    COST_INCURRED = "cost_incurred"
    TOOL_USED = "tool_used"
    DELEGATION_SENT = "delegation_sent"
    DELEGATION_RECEIVED = "delegation_received"


# Import-time check: ActivityEventType must be a superset of LifecycleEventType.
_lifecycle_values = {e.value for e in LifecycleEventType}
_activity_values = {e.value for e in ActivityEventType}
assert _lifecycle_values <= _activity_values, (  # noqa: S101
    "ActivityEventType must be superset of LifecycleEventType; "
    f"missing: {_lifecycle_values - _activity_values}"
)


class PromotionDirection(StrEnum):
    """Direction of a seniority level change."""

    PROMOTION = "promotion"
    DEMOTION = "demotion"


class TrendDirection(StrEnum):
    """Direction of a performance metric trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"
