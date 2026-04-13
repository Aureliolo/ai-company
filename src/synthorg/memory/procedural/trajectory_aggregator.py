"""Trajectory aggregation for cross-agent pattern identification.

Collects execution trajectories and identifies patterns that appear
across multiple distinct agents, enabling org-scope skill proposals.
"""

from collections import defaultdict
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger

logger = get_logger(__name__)


class AggregatedTrajectory(BaseModel):
    """A single execution trajectory for analysis.

    Attributes:
        agent_id: Agent that executed this trajectory.
        task_id: Task identifier.
        outcome: Whether the execution succeeded or failed.
        error_category: Error category (for failures).
        tool_calls: Tool names invoked during execution.
        turn_count: Number of LLM turns.
        recorded_at: When this trajectory was recorded.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr = Field(description="Executing agent")
    task_id: NotBlankStr = Field(description="Task identifier")
    outcome: Literal["success", "failure"] = Field(
        description="Execution outcome",
    )
    error_category: NotBlankStr | None = Field(
        default=None,
        description="Error category for failures",
    )
    tool_calls: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Tool names invoked",
    )
    turn_count: int = Field(ge=0, description="LLM turns completed")
    recorded_at: AwareDatetime = Field(
        description="When trajectory was recorded",
    )


class TrajectoryPattern(BaseModel):
    """A pattern identified across multiple trajectories.

    Attributes:
        pattern_id: Unique pattern identifier.
        description: Human-readable pattern description.
        agent_ids: Distinct agents that hit this pattern.
        occurrence_count: Total trajectory count.
        failure_rate: Fraction of trajectories that failed.
        representative_trajectory: Example trajectory for context.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    pattern_id: NotBlankStr = Field(description="Unique identifier")
    description: NotBlankStr = Field(description="Pattern description")
    agent_ids: frozenset[NotBlankStr] = Field(
        description="Distinct agents",
    )
    occurrence_count: int = Field(ge=1, description="Total occurrences")
    failure_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction that failed",
    )
    representative_trajectory: AggregatedTrajectory = Field(
        description="Example trajectory",
    )


def _group_key(trajectory: AggregatedTrajectory) -> str:
    """Compute a grouping key for a trajectory.

    Failures group by error_category; successes group by
    tool call sequence.
    """
    if trajectory.outcome == "failure" and trajectory.error_category:
        return f"failure:{trajectory.error_category}"
    return f"success:{','.join(trajectory.tool_calls)}"


class TrajectoryAggregator:
    """Identifies cross-agent patterns from execution trajectories.

    Stateless service: receives trajectories, returns patterns.

    Args:
        min_agents_for_pattern: Minimum distinct agents required
            to form a pattern (default 3).
    """

    __slots__ = ("_min_agents",)

    def __init__(self, *, min_agents_for_pattern: int = 3) -> None:
        self._min_agents = min_agents_for_pattern

    def aggregate(
        self,
        trajectories: tuple[AggregatedTrajectory, ...],
    ) -> tuple[TrajectoryPattern, ...]:
        """Group trajectories by pattern and filter by threshold.

        Args:
            trajectories: All trajectories to analyze.

        Returns:
            Patterns seen by >= ``min_agents_for_pattern`` distinct
            agents, sorted by occurrence count descending.
        """
        if not trajectories:
            return ()

        groups: dict[str, list[AggregatedTrajectory]] = defaultdict(list)
        for t in trajectories:
            groups[_group_key(t)].append(t)

        patterns: list[TrajectoryPattern] = []
        for key, trajs in groups.items():
            agent_ids = frozenset(t.agent_id for t in trajs)
            if len(agent_ids) < self._min_agents:
                continue

            failure_count = sum(1 for t in trajs if t.outcome == "failure")
            failure_rate = failure_count / len(trajs) if trajs else 0.0

            patterns.append(
                TrajectoryPattern(
                    pattern_id=str(uuid4()),
                    description=f"Pattern: {key} "
                    f"({len(trajs)} occurrences, "
                    f"{len(agent_ids)} agents)",
                    agent_ids=agent_ids,
                    occurrence_count=len(trajs),
                    failure_rate=failure_rate,
                    representative_trajectory=trajs[0],
                ),
            )

        patterns.sort(key=lambda p: p.occurrence_count, reverse=True)
        return tuple(patterns)
