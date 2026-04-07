"""Trajectory scoring event constants."""

from typing import Final

TRAJECTORY_SCORING_START: Final[str] = "execution.trajectory.scoring_start"
TRAJECTORY_CANDIDATE_SCORED: Final[str] = "execution.trajectory.candidate_scored"
TRAJECTORY_BEST_SELECTED: Final[str] = "execution.trajectory.best_selected"
TRAJECTORY_BUDGET_GUARD_BLOCKED: Final[str] = (
    "execution.trajectory.budget_guard_blocked"
)
TRAJECTORY_CONSISTENCY_FILTERED: Final[str] = (
    "execution.trajectory.consistency_filtered"
)
