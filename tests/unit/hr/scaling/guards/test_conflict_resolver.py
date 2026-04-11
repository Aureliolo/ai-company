"""Tests for conflict resolver guard."""

import pytest

from synthorg.hr.scaling.enums import ScalingActionType, ScalingStrategyName
from synthorg.hr.scaling.guards.conflict_resolver import ConflictResolver

from .conftest import make_decision


@pytest.mark.unit
class TestConflictResolver:
    """ConflictResolver priority enforcement and HOLD blocking."""

    async def test_passes_non_conflicting_decisions(self) -> None:
        resolver = ConflictResolver()
        decisions = (
            make_decision(
                action_type=ScalingActionType.HIRE,
                source_strategy=ScalingStrategyName.WORKLOAD,
            ),
            make_decision(
                action_type=ScalingActionType.PRUNE,
                source_strategy=ScalingStrategyName.PERFORMANCE_PRUNING,
                target_agent_id="agent-001",
                target_role=None,
            ),
        )
        result = await resolver.filter(decisions)
        assert len(result) == 2

    async def test_hold_blocks_lower_priority_hires(self) -> None:
        resolver = ConflictResolver()
        decisions = (
            make_decision(
                action_type=ScalingActionType.HOLD,
                source_strategy=ScalingStrategyName.BUDGET_CAP,
                target_role=None,
            ),
            make_decision(
                action_type=ScalingActionType.HIRE,
                source_strategy=ScalingStrategyName.WORKLOAD,
            ),
        )
        result = await resolver.filter(decisions)
        # HOLD is removed, HIRE blocked = empty
        assert len(result) == 0

    async def test_hold_does_not_block_prune(self) -> None:
        resolver = ConflictResolver()
        decisions = (
            make_decision(
                action_type=ScalingActionType.HOLD,
                source_strategy=ScalingStrategyName.BUDGET_CAP,
                target_role=None,
            ),
            make_decision(
                action_type=ScalingActionType.PRUNE,
                source_strategy=ScalingStrategyName.PERFORMANCE_PRUNING,
                target_agent_id="agent-001",
                target_role=None,
            ),
        )
        result = await resolver.filter(decisions)
        assert len(result) == 1
        assert result[0].action_type == ScalingActionType.PRUNE

    async def test_empty_input_returns_empty(self) -> None:
        resolver = ConflictResolver()
        result = await resolver.filter(())
        assert result == ()

    async def test_deduplicates_same_agent_by_priority(self) -> None:
        resolver = ConflictResolver()
        decisions = (
            make_decision(
                action_type=ScalingActionType.PRUNE,
                source_strategy=ScalingStrategyName.WORKLOAD,
                target_agent_id="agent-001",
                target_role=None,
            ),
            make_decision(
                action_type=ScalingActionType.PRUNE,
                source_strategy=ScalingStrategyName.PERFORMANCE_PRUNING,
                target_agent_id="agent-001",
                target_role=None,
            ),
        )
        result = await resolver.filter(decisions)
        assert len(result) == 1
        # Performance pruning has higher priority (1) than workload (3).
        assert result[0].source_strategy == ScalingStrategyName.PERFORMANCE_PRUNING

    async def test_name_property(self) -> None:
        resolver = ConflictResolver()
        assert resolver.name == "conflict_resolver"
