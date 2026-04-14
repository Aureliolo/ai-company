"""Unit tests for meta-loop factory module."""

import pytest

from synthorg.meta.config import SelfImprovementConfig
from synthorg.meta.factory import (
    build_appliers,
    build_guards,
    build_regression_detector,
    build_rollout_strategies,
    build_rule_engine,
    build_strategies,
)
from synthorg.meta.models import ProposalAltitude

pytestmark = pytest.mark.unit


class TestBuildRuleEngine:
    """Rule engine factory tests."""

    def test_all_rules_enabled_by_default(self) -> None:
        cfg = SelfImprovementConfig(enabled=True)
        engine = build_rule_engine(cfg)
        assert engine.rule_count == 9

    def test_disabled_rules_excluded(self) -> None:
        from synthorg.meta.config import RuleConfig

        cfg = SelfImprovementConfig(
            enabled=True,
            rules=RuleConfig(
                disabled_rules=("quality_declining", "budget_overrun"),
            ),
        )
        engine = build_rule_engine(cfg)
        assert engine.rule_count == 7
        assert "quality_declining" not in engine.rule_names
        assert "budget_overrun" not in engine.rule_names

    def test_disable_all_rules(self) -> None:
        from synthorg.meta.config import RuleConfig

        all_names = (
            "quality_declining",
            "success_rate_drop",
            "budget_overrun",
            "coordination_cost_ratio",
            "coordination_overhead",
            "straggler_bottleneck",
            "redundancy",
            "scaling_failure",
            "error_spike",
        )
        cfg = SelfImprovementConfig(
            enabled=True,
            rules=RuleConfig(disabled_rules=all_names),
        )
        engine = build_rule_engine(cfg)
        assert engine.rule_count == 0


class TestBuildStrategies:
    """Strategy factory tests."""

    def test_config_tuning_only(self) -> None:
        cfg = SelfImprovementConfig(
            enabled=True,
            config_tuning_enabled=True,
            architecture_proposals_enabled=False,
            prompt_tuning_enabled=False,
        )
        strategies = build_strategies(cfg)
        assert len(strategies) == 1
        assert strategies[0].altitude == ProposalAltitude.CONFIG_TUNING

    def test_all_strategies_enabled(self) -> None:
        cfg = SelfImprovementConfig(
            enabled=True,
            config_tuning_enabled=True,
            architecture_proposals_enabled=True,
            prompt_tuning_enabled=True,
        )
        strategies = build_strategies(cfg)
        assert len(strategies) == 3
        altitudes = {s.altitude for s in strategies}
        assert altitudes == {
            ProposalAltitude.CONFIG_TUNING,
            ProposalAltitude.ARCHITECTURE,
            ProposalAltitude.PROMPT_TUNING,
        }

    def test_none_enabled(self) -> None:
        cfg = SelfImprovementConfig(
            enabled=True,
            config_tuning_enabled=False,
            architecture_proposals_enabled=False,
            prompt_tuning_enabled=False,
        )
        strategies = build_strategies(cfg)
        assert len(strategies) == 0


class TestBuildGuards:
    """Guard factory tests."""

    def test_builds_4_guards(self) -> None:
        cfg = SelfImprovementConfig(enabled=True)
        guards = build_guards(cfg)
        assert len(guards) == 4

    def test_guard_chain_order(self) -> None:
        cfg = SelfImprovementConfig(enabled=True)
        guards = build_guards(cfg)
        names = [g.name for g in guards]
        assert names == [
            "scope_check",
            "rollback_plan",
            "rate_limit",
            "approval_gate",
        ]


class TestBuildAppliers:
    """Applier factory tests."""

    def test_builds_3_appliers(self) -> None:
        appliers = build_appliers()
        assert len(appliers) == 3
        assert ProposalAltitude.CONFIG_TUNING in appliers
        assert ProposalAltitude.ARCHITECTURE in appliers
        assert ProposalAltitude.PROMPT_TUNING in appliers


class TestBuildRegressionDetector:
    """Regression detector factory tests."""

    def test_builds_tiered_detector(self) -> None:
        detector = build_regression_detector()
        assert detector.name == "tiered"


class TestBuildRolloutStrategies:
    """Rollout strategy factory tests."""

    def test_builds_2_strategies(self) -> None:
        strategies = build_rollout_strategies()
        assert len(strategies) == 2
        assert "before_after" in strategies
        assert "canary" in strategies
