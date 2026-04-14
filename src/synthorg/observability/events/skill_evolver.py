"""Skill evolver event constants."""

from typing import Final

SKILL_EVOLVER_CYCLE_START: Final[str] = "skill_evolver.cycle.start"
SKILL_EVOLVER_CYCLE_COMPLETE: Final[str] = "skill_evolver.cycle.complete"
SKILL_EVOLVER_CYCLE_FAILED: Final[str] = "skill_evolver.cycle.failed"
SKILL_EVOLVER_PROPOSAL_EMITTED: Final[str] = "skill_evolver.proposal.emitted"
SKILL_EVOLVER_CONFLICT_DETECTED: Final[str] = "skill_evolver.conflict.detected"
ORG_SKILL_SUPERSEDED: Final[str] = "skill_evolver.org_skill.superseded"
SKILL_EVOLVER_DISABLED: Final[str] = "skill_evolver.disabled"

# Supersession evaluation
SUPERSESSION_CONFLICT: Final[str] = "supersession.conflict"
SUPERSESSION_FULL: Final[str] = "supersession.full"
SUPERSESSION_PARTIAL: Final[str] = "supersession.partial"

# Trajectory aggregation
TRAJECTORY_AGGREGATE_EMPTY: Final[str] = "trajectory.aggregate.empty_input"
TRAJECTORY_AGGREGATE_COMPLETE: Final[str] = "trajectory.aggregate.complete"
