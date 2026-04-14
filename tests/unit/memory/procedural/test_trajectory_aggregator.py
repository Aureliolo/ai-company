"""Tests for trajectory aggregation across agents."""

from datetime import UTC, datetime

import pytest

from synthorg.memory.procedural.trajectory_aggregator import (
    AggregatedTrajectory,
    TrajectoryAggregator,
)


def _make_trajectory(**overrides: object) -> AggregatedTrajectory:
    defaults: dict[str, object] = {
        "agent_id": "agent-1",
        "task_id": "task-1",
        "outcome": "failure",
        "error_category": "timeout",
        "tool_calls": ("http_request", "parse_json"),
        "turn_count": 5,
        "recorded_at": datetime(2026, 4, 14, tzinfo=UTC),
    }
    defaults.update(overrides)
    return AggregatedTrajectory(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestAggregatedTrajectory:
    def test_construction(self) -> None:
        t = _make_trajectory()
        assert t.agent_id == "agent-1"
        assert t.outcome == "failure"
        assert t.error_category == "timeout"

    def test_success_trajectory(self) -> None:
        t = _make_trajectory(outcome="success", error_category=None)
        assert t.outcome == "success"
        assert t.error_category is None


@pytest.mark.unit
class TestTrajectoryAggregator:
    def test_empty_input(self) -> None:
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate(())
        assert patterns == ()

    def test_single_agent_below_threshold(self) -> None:
        """One agent with many failures doesn't form a pattern."""
        trajectories = tuple(
            _make_trajectory(
                agent_id="agent-1",
                task_id=f"task-{i}",
                error_category="timeout",
            )
            for i in range(5)
        )
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate(trajectories)
        assert len(patterns) == 0

    def test_cross_agent_failure_pattern(self) -> None:
        """Same error category across 3+ agents forms a pattern."""
        trajectories = tuple(
            _make_trajectory(
                agent_id=f"agent-{i}",
                task_id=f"task-{i}",
                error_category="timeout",
            )
            for i in range(4)
        )
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate(trajectories)
        assert len(patterns) == 1
        assert patterns[0].occurrence_count == 4
        assert len(patterns[0].agent_ids) == 4

    def test_two_distinct_patterns(self) -> None:
        """Two different error categories, each across 3+ agents."""
        timeout_trajs = tuple(
            _make_trajectory(
                agent_id=f"agent-{i}",
                task_id=f"t-timeout-{i}",
                error_category="timeout",
            )
            for i in range(3)
        )
        oom_trajs = tuple(
            _make_trajectory(
                agent_id=f"agent-{i + 10}",
                task_id=f"t-oom-{i}",
                error_category="out_of_memory",
            )
            for i in range(3)
        )
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate((*timeout_trajs, *oom_trajs))
        assert len(patterns) == 2

    def test_pattern_below_threshold_excluded(self) -> None:
        """Pattern with only 2 agents excluded when threshold is 3."""
        trajectories = (
            _make_trajectory(agent_id="a-1", error_category="rare"),
            _make_trajectory(agent_id="a-2", error_category="rare"),
        )
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate(trajectories)
        assert len(patterns) == 0

    def test_sorted_by_occurrence_descending(self) -> None:
        """Patterns sorted by occurrence count descending."""
        small = tuple(
            _make_trajectory(
                agent_id=f"a-{i}",
                task_id=f"small-{i}",
                error_category="small_error",
            )
            for i in range(3)
        )
        big = tuple(
            _make_trajectory(
                agent_id=f"a-{i}",
                task_id=f"big-{i}",
                error_category="big_error",
            )
            for i in range(5)
        )
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate((*small, *big))
        assert len(patterns) == 2
        assert patterns[0].occurrence_count >= patterns[1].occurrence_count

    def test_success_trajectories_grouped(self) -> None:
        """Success trajectories grouped by tool call pattern."""
        trajectories = tuple(
            _make_trajectory(
                agent_id=f"a-{i}",
                task_id=f"t-{i}",
                outcome="success",
                error_category=None,
                tool_calls=("search", "summarize"),
            )
            for i in range(3)
        )
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate(trajectories)
        assert len(patterns) >= 1

    def test_failure_rate_computed(self) -> None:
        """Pattern failure rate computed correctly."""
        trajectories = tuple(
            _make_trajectory(
                agent_id=f"a-{i}",
                task_id=f"t-{i}",
                error_category="timeout",
            )
            for i in range(3)
        )
        agg = TrajectoryAggregator(min_agents_for_pattern=3)
        patterns = agg.aggregate(trajectories)
        assert len(patterns) == 1
        assert patterns[0].failure_rate == 1.0
