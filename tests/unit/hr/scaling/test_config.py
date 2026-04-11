"""Tests for scaling configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.hr.scaling.config import (
    BudgetCapConfig,
    ScalingConfig,
    SkillGapConfig,
    WorkloadScalingConfig,
)


@pytest.mark.unit
class TestWorkloadScalingConfig:
    """WorkloadScalingConfig validation."""

    def test_defaults(self) -> None:
        config = WorkloadScalingConfig()
        assert config.enabled is True
        assert config.hire_threshold == 0.85
        assert config.prune_threshold == 0.30

    def test_prune_above_hire_rejected(self) -> None:
        with pytest.raises(ValidationError, match="prune_threshold"):
            WorkloadScalingConfig(
                hire_threshold=0.50,
                prune_threshold=0.60,
            )

    def test_frozen(self) -> None:
        config = WorkloadScalingConfig()
        with pytest.raises(ValidationError):
            config.enabled = False  # type: ignore[misc]


@pytest.mark.unit
class TestBudgetCapConfig:
    """BudgetCapConfig validation."""

    def test_defaults(self) -> None:
        config = BudgetCapConfig()
        assert config.safety_margin == 0.90
        assert config.headroom_fraction == 0.60

    def test_headroom_above_margin_rejected(self) -> None:
        with pytest.raises(ValidationError, match="headroom_fraction"):
            BudgetCapConfig(
                safety_margin=0.50,
                headroom_fraction=0.60,
            )


@pytest.mark.unit
class TestSkillGapConfig:
    """SkillGapConfig defaults."""

    def test_disabled_by_default(self) -> None:
        config = SkillGapConfig()
        assert config.enabled is False


@pytest.mark.unit
class TestScalingConfig:
    """Master ScalingConfig defaults and structure."""

    def test_defaults(self) -> None:
        config = ScalingConfig()
        assert config.enabled is True
        assert config.workload.enabled is True
        assert config.budget_cap.enabled is True
        assert config.skill_gap.enabled is False
        assert config.performance_pruning.enabled is True
        assert len(config.priority_order) == 4
        assert config.priority_order[0] == "budget_cap"

    def test_frozen(self) -> None:
        config = ScalingConfig()
        with pytest.raises(ValidationError):
            config.enabled = False  # type: ignore[misc]

    def test_custom_priority_order(self) -> None:
        from synthorg.hr.scaling.enums import ScalingStrategyName

        config = ScalingConfig(
            priority_order=(
                ScalingStrategyName.WORKLOAD,
                ScalingStrategyName.BUDGET_CAP,
                ScalingStrategyName.PERFORMANCE_PRUNING,
                ScalingStrategyName.SKILL_GAP,
            ),
        )
        assert config.priority_order[0] == ScalingStrategyName.WORKLOAD

    def test_priority_order_rejects_duplicates(self) -> None:
        from synthorg.hr.scaling.enums import ScalingStrategyName

        with pytest.raises(ValidationError, match="duplicates"):
            ScalingConfig(
                priority_order=(
                    ScalingStrategyName.BUDGET_CAP,
                    ScalingStrategyName.BUDGET_CAP,
                    ScalingStrategyName.SKILL_GAP,
                    ScalingStrategyName.WORKLOAD,
                ),
            )
