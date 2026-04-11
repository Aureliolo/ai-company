"""Tests for scaling factory."""

import pytest

from synthorg.hr.scaling.config import (
    BudgetCapConfig,
    PerformancePruningConfig,
    ScalingConfig,
    SkillGapConfig,
    WorkloadScalingConfig,
)
from synthorg.hr.scaling.factory import (
    create_scaling_context_builder,
    create_scaling_guards,
    create_scaling_strategies,
    create_scaling_trigger,
)


@pytest.mark.unit
class TestCreateScalingStrategies:
    """Strategy creation from config."""

    @pytest.mark.parametrize(
        ("config_tuple", "expected_count"),
        [
            ((False, True, True, True), 2),
            ((True, True, True, True), 3),
            ((False, False, False, False), 0),
        ],
        ids=[
            "default-config-creates-two-strategies",
            "all-enabled",
            "all-disabled",
        ],
    )
    def test_strategy_creation(
        self,
        config_tuple,
        expected_count,
    ) -> None:
        skill_gap_enabled, workload_enabled, budget_enabled, perf_enabled = config_tuple
        config = ScalingConfig(
            skill_gap=SkillGapConfig(enabled=skill_gap_enabled),
            workload=WorkloadScalingConfig(enabled=workload_enabled),
            budget_cap=BudgetCapConfig(enabled=budget_enabled),
            performance_pruning=PerformancePruningConfig(enabled=perf_enabled),
        )
        strategies = create_scaling_strategies(config)
        assert len(strategies) == expected_count


@pytest.mark.unit
class TestCreateScalingGuards:
    """Guard chain creation from config."""

    @pytest.mark.parametrize(
        "approval_store",
        [
            None,
            "approval_store",
        ],
        ids=[
            "creates-composite-without-approval",
            "creates-composite-with-approval",
        ],
    )
    def test_guard_creation(self, approval_store) -> None:
        from synthorg.api.approval_store import ApprovalStore

        config = ScalingConfig()
        if approval_store is not None:
            store = ApprovalStore()
            guard = create_scaling_guards(config, approval_store=store)
        else:
            guard = create_scaling_guards(config)
        assert guard.name == "composite"


@pytest.mark.unit
class TestCreateScalingTrigger:
    """Trigger creation from config."""

    def test_creates_batched_trigger(self) -> None:
        config = ScalingConfig()
        trigger = create_scaling_trigger(config)
        assert trigger.name == "batched"


@pytest.mark.unit
class TestCreateScalingContextBuilder:
    """Context builder creation from config."""

    def test_creates_builder(self) -> None:
        config = ScalingConfig()
        builder = create_scaling_context_builder(config)
        assert builder is not None
