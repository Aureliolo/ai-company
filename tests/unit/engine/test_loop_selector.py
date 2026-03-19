"""Unit tests for execution loop auto-selection."""

import pytest
import structlog.testing
from pydantic import ValidationError

from synthorg.core.enums import Complexity
from synthorg.engine.loop_selector import (
    DEFAULT_AUTO_LOOP_RULES,
    AutoLoopConfig,
    AutoLoopRule,
    build_execution_loop,
    select_loop_type,
)
from synthorg.engine.plan_execute_loop import PlanExecuteLoop
from synthorg.engine.react_loop import ReactLoop
from synthorg.observability.events.execution import (
    EXECUTION_LOOP_BUDGET_DOWNGRADE,
    EXECUTION_LOOP_HYBRID_FALLBACK,
    EXECUTION_LOOP_NO_RULE_MATCH,
)

pytestmark = pytest.mark.timeout(30)


# ── select_loop_type: default rules ─────────────────────────


@pytest.mark.unit
class TestSelectLoopType:
    """Default rules: SIMPLE->react, MEDIUM->plan_execute, COMPLEX/EPIC->hybrid."""

    @pytest.mark.parametrize(
        ("complexity", "expected"),
        [
            (Complexity.SIMPLE, "react"),
            (Complexity.MEDIUM, "plan_execute"),
            (Complexity.COMPLEX, "hybrid"),
            (Complexity.EPIC, "hybrid"),
        ],
    )
    def test_default_rules_select_expected_type(
        self,
        complexity: Complexity,
        expected: str,
    ) -> None:
        result = select_loop_type(
            complexity=complexity,
            rules=DEFAULT_AUTO_LOOP_RULES,
            # Disable hybrid fallback to see raw selection
            hybrid_fallback=None,
        )
        assert result == expected

    def test_no_matching_rule_falls_back_to_react(self) -> None:
        """Empty rules tuple => fallback to react."""
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=(),
        )
        assert result == "react"

    def test_no_matching_rule_logs_warning(self) -> None:
        """Fallback to default emits a warning log."""
        with structlog.testing.capture_logs() as logs:
            select_loop_type(
                complexity=Complexity.COMPLEX,
                rules=(),
            )
        events = [e for e in logs if e["event"] == EXECUTION_LOOP_NO_RULE_MATCH]
        assert len(events) == 1
        assert events[0]["complexity"] == "complex"
        assert events[0]["fallback"] == "react"

    def test_rule_mapping_to_react_does_not_warn(self) -> None:
        """When a rule explicitly maps to react, no NO_RULE_MATCH warning."""
        rules = (AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="react"),)
        with structlog.testing.capture_logs() as logs:
            result = select_loop_type(
                complexity=Complexity.SIMPLE,
                rules=rules,
            )
        assert result == "react"
        no_match_events = [
            e for e in logs if e["event"] == EXECUTION_LOOP_NO_RULE_MATCH
        ]
        assert len(no_match_events) == 0

    def test_custom_default_loop_type(self) -> None:
        """Empty rules with custom default_loop_type."""
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=(),
            default_loop_type="plan_execute",
        )
        assert result == "plan_execute"


# ── Budget-aware downgrade ───────────────────────────────────


@pytest.mark.unit
class TestBudgetAwareDowngrade:
    """Budget >= threshold downgrades hybrid -> plan_execute."""

    def test_hybrid_downgraded_when_budget_tight(self) -> None:
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            budget_utilization_pct=85.0,
            budget_tight_threshold=80,
            hybrid_fallback=None,
        )
        assert result == "plan_execute"

    def test_hybrid_not_downgraded_when_budget_ok(self) -> None:
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            budget_utilization_pct=50.0,
            budget_tight_threshold=80,
            hybrid_fallback=None,
        )
        assert result == "hybrid"

    def test_no_downgrade_when_budget_unknown(self) -> None:
        """budget_utilization_pct=None => no downgrade."""
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            budget_utilization_pct=None,
            hybrid_fallback=None,
        )
        assert result == "hybrid"

    def test_no_downgrade_for_non_hybrid_loops(self) -> None:
        """Budget-aware downgrade only applies to hybrid."""
        result = select_loop_type(
            complexity=Complexity.SIMPLE,
            rules=DEFAULT_AUTO_LOOP_RULES,
            budget_utilization_pct=99.0,
            budget_tight_threshold=80,
        )
        assert result == "react"

    def test_exact_threshold_triggers_downgrade(self) -> None:
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            budget_utilization_pct=80.0,
            budget_tight_threshold=80,
            hybrid_fallback=None,
        )
        assert result == "plan_execute"


# ── Hybrid fallback ──────────────────────────────────────────


@pytest.mark.unit
class TestHybridFallback:
    """Hybrid loop not yet implemented -> fall back."""

    def test_default_fallback_is_plan_execute(self) -> None:
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
        )
        assert result == "plan_execute"

    def test_custom_fallback_value(self) -> None:
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            hybrid_fallback="react",
        )
        assert result == "react"

    def test_none_fallback_preserves_hybrid(self) -> None:
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            hybrid_fallback=None,
        )
        assert result == "hybrid"


# ── Budget downgrade + hybrid fallback interaction ───────────


@pytest.mark.unit
class TestBudgetAndHybridInteraction:
    """Budget downgrade takes priority -- hybrid never reaches fallback."""

    def test_budget_downgrade_skips_hybrid_fallback(self) -> None:
        """When budget is tight, hybrid -> plan_execute via budget, not fallback."""
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            budget_utilization_pct=90.0,
            budget_tight_threshold=80,
            hybrid_fallback="react",
        )
        # Budget downgrade to plan_execute, not the react fallback
        assert result == "plan_execute"

    def test_budget_ok_falls_through_to_hybrid_fallback(self) -> None:
        """Budget OK -> hybrid selected -> then hybrid fallback applies."""
        result = select_loop_type(
            complexity=Complexity.COMPLEX,
            rules=DEFAULT_AUTO_LOOP_RULES,
            budget_utilization_pct=50.0,
            budget_tight_threshold=80,
            hybrid_fallback="react",
        )
        assert result == "react"


# ── AutoLoopConfig model ─────────────────────────────────────


@pytest.mark.unit
class TestAutoLoopConfig:
    """Frozen Pydantic config model."""

    def test_defaults(self) -> None:
        config = AutoLoopConfig()
        assert config.rules == DEFAULT_AUTO_LOOP_RULES
        assert config.budget_tight_threshold == 80
        assert config.hybrid_fallback == "plan_execute"

    def test_frozen(self) -> None:
        config = AutoLoopConfig()
        with pytest.raises(ValidationError):
            config.budget_tight_threshold = 50  # type: ignore[misc]

    def test_custom_rules(self) -> None:
        rules = (
            AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="plan_execute"),
            AutoLoopRule(complexity=Complexity.MEDIUM, loop_type="react"),
        )
        config = AutoLoopConfig(rules=rules)
        assert config.rules == rules

    def test_duplicate_complexity_rejected(self) -> None:
        """Rules with duplicate complexity values are invalid."""
        with pytest.raises(ValidationError, match="Duplicate complexity"):
            AutoLoopConfig(
                rules=(
                    AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="react"),
                    AutoLoopRule(
                        complexity=Complexity.SIMPLE, loop_type="plan_execute"
                    ),
                ),
            )

    @pytest.mark.parametrize("value", [-1, 101])
    def test_budget_tight_threshold_out_of_range(self, value: int) -> None:
        """budget_tight_threshold must be 0-100."""
        with pytest.raises(ValidationError):
            AutoLoopConfig(budget_tight_threshold=value)

    def test_blank_hybrid_fallback_rejected(self) -> None:
        """Empty/whitespace hybrid_fallback is invalid (NotBlankStr)."""
        with pytest.raises(ValidationError):
            AutoLoopConfig(hybrid_fallback="   ")

    def test_unknown_loop_type_in_rules_rejected(self) -> None:
        """Rules with unknown loop types are invalid."""
        with pytest.raises(ValidationError, match="Unknown loop_type"):
            AutoLoopConfig(
                rules=(
                    AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="nonexistent"),
                ),
            )

    def test_extra_fields_rejected(self) -> None:
        """Unknown config keys raise instead of being silently dropped."""
        with pytest.raises(ValidationError, match="extra"):
            AutoLoopConfig(nonexistent_key="value")  # type: ignore[call-arg]

    def test_unknown_hybrid_fallback_rejected(self) -> None:
        """hybrid_fallback must be a known loop type."""
        with pytest.raises(ValidationError, match="Unknown hybrid_fallback"):
            AutoLoopConfig(hybrid_fallback="nonexistent")

    def test_unknown_default_loop_type_rejected(self) -> None:
        """default_loop_type must be a known loop type."""
        with pytest.raises(ValidationError, match="Unknown default_loop_type"):
            AutoLoopConfig(default_loop_type="nonexistent")

    def test_default_loop_type_defaults_to_react(self) -> None:
        config = AutoLoopConfig()
        assert config.default_loop_type == "react"

    def test_custom_default_loop_type(self) -> None:
        config = AutoLoopConfig(default_loop_type="plan_execute")
        assert config.default_loop_type == "plan_execute"

    def test_hybrid_fallback_none_with_hybrid_rules_rejected(self) -> None:
        """hybrid_fallback=None is invalid when rules map to hybrid."""
        with pytest.raises(ValidationError, match="hybrid_fallback must not be None"):
            AutoLoopConfig(hybrid_fallback=None)

    def test_hybrid_fallback_none_without_hybrid_rules_accepted(self) -> None:
        """hybrid_fallback=None is valid when no rules map to hybrid."""
        config = AutoLoopConfig(
            rules=(
                AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="react"),
                AutoLoopRule(complexity=Complexity.MEDIUM, loop_type="plan_execute"),
            ),
            hybrid_fallback=None,
        )
        assert config.hybrid_fallback is None

    def test_unbuildable_default_loop_type_rejected_without_fallback(self) -> None:
        """default_loop_type=hybrid is rejected when fallback is None."""
        with pytest.raises(ValidationError, match="not buildable"):
            AutoLoopConfig(
                rules=(AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="react"),),
                default_loop_type="hybrid",
                hybrid_fallback=None,
            )

    def test_unbuildable_default_loop_type_accepted_with_fallback(self) -> None:
        """default_loop_type=hybrid is valid when hybrid_fallback redirects."""
        config = AutoLoopConfig(
            rules=(AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="react"),),
            default_loop_type="hybrid",
            hybrid_fallback="plan_execute",
        )
        assert config.default_loop_type == "hybrid"
        assert config.hybrid_fallback == "plan_execute"

    def test_unbuildable_hybrid_fallback_rejected(self) -> None:
        """hybrid_fallback cannot be an unbuildable type."""
        with pytest.raises(ValidationError, match="not buildable"):
            AutoLoopConfig(hybrid_fallback="hybrid")


# ── AutoLoopRule model ───────────────────────────────────────


@pytest.mark.unit
class TestAutoLoopRule:
    """Frozen Pydantic rule model."""

    def test_create(self) -> None:
        rule = AutoLoopRule(
            complexity=Complexity.SIMPLE,
            loop_type="react",
        )
        assert rule.complexity == Complexity.SIMPLE
        assert rule.loop_type == "react"

    def test_frozen(self) -> None:
        rule = AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="react")
        with pytest.raises(ValidationError):
            rule.loop_type = "plan_execute"  # type: ignore[misc]

    def test_blank_loop_type_rejected(self) -> None:
        """Empty/whitespace loop_type is invalid (NotBlankStr)."""
        with pytest.raises(ValidationError):
            AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="")

    def test_unknown_loop_type_rejected(self) -> None:
        """Unknown loop_type is rejected at rule construction."""
        with pytest.raises(ValidationError, match="Unknown loop_type"):
            AutoLoopRule(complexity=Complexity.SIMPLE, loop_type="typo")

    def test_extra_fields_rejected(self) -> None:
        """Unknown fields raise instead of being silently dropped."""
        with pytest.raises(ValidationError, match="extra"):
            AutoLoopRule(
                complexity=Complexity.SIMPLE,
                loop_type="react",
                typo="value",  # type: ignore[call-arg]
            )


# ── build_execution_loop factory ─────────────────────────────


@pytest.mark.unit
class TestBuildExecutionLoop:
    """Factory creates correct loop instances."""

    def test_build_react(self) -> None:
        loop = build_execution_loop("react")
        assert isinstance(loop, ReactLoop)
        assert loop.get_loop_type() == "react"

    def test_build_plan_execute(self) -> None:
        loop = build_execution_loop("plan_execute")
        assert isinstance(loop, PlanExecuteLoop)
        assert loop.get_loop_type() == "plan_execute"

    def test_build_react_with_gates(self) -> None:
        from unittest.mock import MagicMock

        gate = MagicMock()
        detector = MagicMock()
        loop = build_execution_loop(
            "react",
            approval_gate=gate,
            stagnation_detector=detector,
        )
        assert isinstance(loop, ReactLoop)
        assert loop.approval_gate is gate
        assert loop.stagnation_detector is detector

    def test_build_plan_execute_with_config(self) -> None:
        from synthorg.engine.plan_models import PlanExecuteConfig

        config = PlanExecuteConfig(max_replans=5)
        loop = build_execution_loop(
            "plan_execute",
            plan_execute_config=config,
        )
        assert isinstance(loop, PlanExecuteLoop)
        assert loop.config.max_replans == 5

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown loop type"):
            build_execution_loop("nonexistent")


# ── Logging ──────────────────────────────────────────────────


@pytest.mark.unit
class TestSelectLoopTypeLogging:
    """Structured log events emitted during selection."""

    def test_budget_downgrade_logged(self) -> None:
        with structlog.testing.capture_logs() as logs:
            select_loop_type(
                complexity=Complexity.COMPLEX,
                rules=DEFAULT_AUTO_LOOP_RULES,
                budget_utilization_pct=90.0,
                budget_tight_threshold=80,
                hybrid_fallback=None,
            )
        events = [e for e in logs if e["event"] == EXECUTION_LOOP_BUDGET_DOWNGRADE]
        assert len(events) == 1
        assert events[0]["original"] == "hybrid"
        assert events[0]["downgraded_to"] == "plan_execute"

    def test_hybrid_fallback_logged(self) -> None:
        with structlog.testing.capture_logs() as logs:
            select_loop_type(
                complexity=Complexity.COMPLEX,
                rules=DEFAULT_AUTO_LOOP_RULES,
                budget_utilization_pct=None,
                hybrid_fallback="plan_execute",
            )
        events = [e for e in logs if e["event"] == EXECUTION_LOOP_HYBRID_FALLBACK]
        assert len(events) == 1
        assert events[0]["fallback_to"] == "plan_execute"

    def test_no_fallback_log_when_not_hybrid(self) -> None:
        with structlog.testing.capture_logs() as logs:
            select_loop_type(
                complexity=Complexity.SIMPLE,
                rules=DEFAULT_AUTO_LOOP_RULES,
            )
        fallback_events = [
            e
            for e in logs
            if e["event"]
            in (EXECUTION_LOOP_BUDGET_DOWNGRADE, EXECUTION_LOOP_HYBRID_FALLBACK)
        ]
        assert len(fallback_events) == 0
