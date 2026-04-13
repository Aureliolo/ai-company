"""Trajectory scoring for best-of-K candidate selection.

Provides self-consistency filtering, verbalized confidence scoring,
trace length scoring, and budget-guarded K-candidate sampling.
"""

# Resolve forward reference: TurnRecord.efficiency_delta uses
# "EfficiencyRatios" as a string annotation to avoid circular imports.
from synthorg.engine.loop_protocol import TurnRecord as _TurnRecord
from synthorg.engine.trajectory.budget_guard import (
    check_trajectory_budget,
)
from synthorg.engine.trajectory.efficiency_ratios import EfficiencyRatios
from synthorg.engine.trajectory.models import (
    CandidateResult,
    TrajectoryConfig,
    TrajectoryScore,
)
from synthorg.engine.trajectory.scorer import TrajectoryScorer

_TurnRecord.model_rebuild(_types_namespace={"EfficiencyRatios": EfficiencyRatios})

__all__ = [
    "CandidateResult",
    "EfficiencyRatios",
    "TrajectoryConfig",
    "TrajectoryScore",
    "TrajectoryScorer",
    "check_trajectory_budget",
]
