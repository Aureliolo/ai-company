"""Tests for ceremony scheduling policy configuration and resolution."""

import pytest

from synthorg.engine.workflow.ceremony_policy import (
    CeremonyPolicyConfig,
    CeremonyStrategyType,
    ResolvedCeremonyPolicy,
    resolve_ceremony_policy,
)
from synthorg.engine.workflow.velocity_types import VelocityCalcType


class TestCeremonyStrategyType:
    """CeremonyStrategyType enum tests."""

    @pytest.mark.unit
    def test_has_all_eight_members(self) -> None:
        assert len(CeremonyStrategyType) == 8

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "member",
        [
            "task_driven",
            "calendar",
            "hybrid",
            "event_driven",
            "budget_driven",
            "throughput_adaptive",
            "external_trigger",
            "milestone_driven",
        ],
    )
    def test_member_values(self, member: str) -> None:
        assert member in [m.value for m in CeremonyStrategyType]

    @pytest.mark.unit
    def test_is_str_enum(self) -> None:
        assert isinstance(CeremonyStrategyType.TASK_DRIVEN, str)


class TestCeremonyPolicyConfig:
    """CeremonyPolicyConfig model tests."""

    @pytest.mark.unit
    def test_all_none_defaults(self) -> None:
        policy = CeremonyPolicyConfig()
        assert policy.strategy is None
        assert policy.strategy_config is None
        assert policy.velocity_calculator is None
        assert policy.auto_transition is None
        assert policy.transition_threshold is None

    @pytest.mark.unit
    def test_with_all_fields(self) -> None:
        policy = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.HYBRID,
            strategy_config={"standup_every_n": 10},
            velocity_calculator=VelocityCalcType.MULTI_DIMENSIONAL,
            auto_transition=True,
            transition_threshold=0.8,
        )
        assert policy.strategy is CeremonyStrategyType.HYBRID
        assert policy.strategy_config == {"standup_every_n": 10}
        assert policy.velocity_calculator is VelocityCalcType.MULTI_DIMENSIONAL
        assert policy.auto_transition is True
        assert policy.transition_threshold == 0.8

    @pytest.mark.unit
    def test_frozen(self) -> None:
        policy = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.CALENDAR,
        )
        with pytest.raises(Exception, match="frozen"):
            policy.strategy = CeremonyStrategyType.HYBRID  # type: ignore[misc]

    @pytest.mark.unit
    def test_transition_threshold_bounds(self) -> None:
        with pytest.raises(ValueError, match="greater than 0"):
            CeremonyPolicyConfig(transition_threshold=0.0)
        with pytest.raises(ValueError, match="less than or equal to 1"):
            CeremonyPolicyConfig(transition_threshold=1.1)

    @pytest.mark.unit
    def test_transition_threshold_valid_bounds(self) -> None:
        low = CeremonyPolicyConfig(transition_threshold=0.01)
        assert low.transition_threshold == 0.01
        high = CeremonyPolicyConfig(transition_threshold=1.0)
        assert high.transition_threshold == 1.0


class TestResolvedCeremonyPolicy:
    """ResolvedCeremonyPolicy model tests."""

    @pytest.mark.unit
    def test_all_fields_required(self) -> None:
        resolved = ResolvedCeremonyPolicy(
            strategy=CeremonyStrategyType.TASK_DRIVEN,
            strategy_config={},
            velocity_calculator=VelocityCalcType.TASK_DRIVEN,
            auto_transition=True,
            transition_threshold=1.0,
        )
        assert resolved.strategy is CeremonyStrategyType.TASK_DRIVEN

    @pytest.mark.unit
    def test_frozen(self) -> None:
        resolved = ResolvedCeremonyPolicy(
            strategy=CeremonyStrategyType.TASK_DRIVEN,
            strategy_config={},
            velocity_calculator=VelocityCalcType.TASK_DRIVEN,
            auto_transition=True,
            transition_threshold=1.0,
        )
        with pytest.raises(Exception, match="frozen"):
            resolved.strategy = CeremonyStrategyType.CALENDAR  # type: ignore[misc]


class TestResolveCeremonyPolicy:
    """resolve_ceremony_policy() tests."""

    @pytest.mark.unit
    def test_project_only_with_all_fields(self) -> None:
        project = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.HYBRID,
            strategy_config={"key": "value"},
            velocity_calculator=VelocityCalcType.CALENDAR,
            auto_transition=False,
            transition_threshold=0.9,
        )
        resolved = resolve_ceremony_policy(project)
        assert resolved.strategy is CeremonyStrategyType.HYBRID
        assert resolved.strategy_config == {"key": "value"}
        assert resolved.velocity_calculator is VelocityCalcType.CALENDAR
        assert resolved.auto_transition is False
        assert resolved.transition_threshold == 0.9

    @pytest.mark.unit
    def test_project_with_none_fields_uses_defaults(self) -> None:
        project = CeremonyPolicyConfig()
        resolved = resolve_ceremony_policy(project)
        assert resolved.strategy is CeremonyStrategyType.TASK_DRIVEN
        assert resolved.strategy_config == {}
        assert resolved.velocity_calculator is VelocityCalcType.TASK_DRIVEN
        assert resolved.auto_transition is True
        assert resolved.transition_threshold == 1.0

    @pytest.mark.unit
    def test_department_overrides_project(self) -> None:
        project = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.TASK_DRIVEN,
            auto_transition=True,
        )
        department = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.CALENDAR,
        )
        resolved = resolve_ceremony_policy(project, department)
        assert resolved.strategy is CeremonyStrategyType.CALENDAR
        # auto_transition not overridden by department -> project value
        assert resolved.auto_transition is True

    @pytest.mark.unit
    def test_ceremony_overrides_department(self) -> None:
        project = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.TASK_DRIVEN,
        )
        department = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.CALENDAR,
        )
        ceremony = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.EVENT_DRIVEN,
        )
        resolved = resolve_ceremony_policy(project, department, ceremony)
        assert resolved.strategy is CeremonyStrategyType.EVENT_DRIVEN

    @pytest.mark.unit
    def test_field_by_field_resolution(self) -> None:
        """Each field resolves independently from the most specific level."""
        project = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.TASK_DRIVEN,
            auto_transition=True,
            transition_threshold=1.0,
        )
        department = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.CALENDAR,
            # auto_transition not set -- inherits from project
        )
        ceremony = CeremonyPolicyConfig(
            transition_threshold=0.8,
            # strategy not set -- inherits from department
        )
        resolved = resolve_ceremony_policy(project, department, ceremony)
        assert resolved.strategy is CeremonyStrategyType.CALENDAR
        assert resolved.auto_transition is True
        assert resolved.transition_threshold == 0.8

    @pytest.mark.unit
    def test_none_department_skipped(self) -> None:
        project = CeremonyPolicyConfig(
            strategy=CeremonyStrategyType.HYBRID,
        )
        ceremony = CeremonyPolicyConfig(
            transition_threshold=0.5,
        )
        resolved = resolve_ceremony_policy(project, None, ceremony)
        assert resolved.strategy is CeremonyStrategyType.HYBRID
        assert resolved.transition_threshold == 0.5

    @pytest.mark.unit
    def test_all_levels_none_uses_framework_defaults(self) -> None:
        resolved = resolve_ceremony_policy(
            CeremonyPolicyConfig(),
            CeremonyPolicyConfig(),
            CeremonyPolicyConfig(),
        )
        assert resolved.strategy is CeremonyStrategyType.TASK_DRIVEN
        assert resolved.velocity_calculator is VelocityCalcType.TASK_DRIVEN
        assert resolved.auto_transition is True
        assert resolved.transition_threshold == 1.0

    @pytest.mark.unit
    def test_strategy_config_override(self) -> None:
        project = CeremonyPolicyConfig(
            strategy_config={"a": 1},
        )
        department = CeremonyPolicyConfig(
            strategy_config={"b": 2},
        )
        resolved = resolve_ceremony_policy(project, department)
        # Department fully overrides (not merged)
        assert resolved.strategy_config == {"b": 2}
