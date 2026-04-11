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

    def test_default_config_creates_two_strategies(self) -> None:
        config = ScalingConfig()
        strategies = create_scaling_strategies(config)
        # workload + budget_cap (skill_gap disabled by default)
        assert len(strategies) == 2

    def test_all_enabled(self) -> None:
        config = ScalingConfig(
            skill_gap=SkillGapConfig(enabled=True),
        )
        strategies = create_scaling_strategies(config)
        assert len(strategies) == 3

    def test_all_disabled(self) -> None:
        config = ScalingConfig(
            workload=WorkloadScalingConfig(enabled=False),
            budget_cap=BudgetCapConfig(enabled=False),
            skill_gap=SkillGapConfig(enabled=False),
            performance_pruning=PerformancePruningConfig(enabled=False),
        )
        strategies = create_scaling_strategies(config)
        assert len(strategies) == 0


@pytest.mark.unit
class TestCreateScalingGuards:
    """Guard chain creation from config."""

    def test_creates_composite_without_approval(self) -> None:
        config = ScalingConfig()
        guard = create_scaling_guards(config)
        assert guard.name == "composite"

    def test_creates_composite_with_approval(self) -> None:
        from synthorg.api.approval_store import ApprovalStore

        config = ScalingConfig()
        store = ApprovalStore()
        guard = create_scaling_guards(config, approval_store=store)
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
