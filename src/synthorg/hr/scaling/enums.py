"""Scaling domain enumerations."""

from enum import StrEnum


class ScalingActionType(StrEnum):
    """Type of scaling action proposed by a strategy.

    - ``HIRE``: Propose hiring a new agent with a target role/skills.
    - ``PRUNE``: Propose removing an underperforming or redundant agent.
    - ``HOLD``: Block actions from lower-priority strategies (budget ceiling).
    - ``NO_OP``: Explicit decision to take no action.
    """

    HIRE = "hire"
    PRUNE = "prune"
    HOLD = "hold"
    NO_OP = "no_op"


class ScalingOutcome(StrEnum):
    """Outcome of executing a scaling decision.

    - ``EXECUTED``: Action completed successfully.
    - ``DEFERRED``: Action awaiting human approval.
    - ``REJECTED``: Action rejected by a guard or human.
    - ``FAILED``: Action attempted but failed during execution.
    """

    EXECUTED = "executed"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    FAILED = "failed"


class ScalingStrategyName(StrEnum):
    """Built-in scaling strategy identifiers."""

    WORKLOAD = "workload"
    BUDGET_CAP = "budget_cap"
    SKILL_GAP = "skill_gap"
    PERFORMANCE_PRUNING = "performance_pruning"
