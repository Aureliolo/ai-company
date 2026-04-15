"""Unit tests for the custom rules API controller."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from synthorg.api.controllers.custom_rules import (
    CreateCustomRuleRequest,
    CustomRuleController,
    PreviewRuleRequest,
    UpdateCustomRuleRequest,
    _build_preview_snapshot,
    _metric_to_dict,
    _rule_to_dict,
)
from synthorg.meta.models import ProposalAltitude, RuleSeverity
from synthorg.meta.rules.custom import (
    METRIC_REGISTRY,
    Comparator,
    CustomRuleDefinition,
    DeclarativeRule,
    resolve_metric,
)

pytestmark = pytest.mark.unit


# ── Controller routes ─────────────────────────────────────────────


class TestCustomRuleControllerRoutes:
    """Verify CustomRuleController route definitions."""

    def test_controller_path(self) -> None:
        assert CustomRuleController.path == "/api/meta/custom-rules"

    def test_has_list_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "list_rules" in methods

    def test_has_get_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "get_rule" in methods

    def test_has_create_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "create_rule" in methods

    def test_has_update_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "update_rule" in methods

    def test_has_delete_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "delete_rule" in methods

    def test_has_toggle_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "toggle_rule" in methods

    def test_has_metrics_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "list_metrics" in methods

    def test_has_preview_endpoint(self) -> None:
        methods = [
            name for name in dir(CustomRuleController) if not name.startswith("_")
        ]
        assert "preview_rule" in methods


# ── Request DTOs ──────────────────────────────────────────────────


class TestCreateCustomRuleRequest:
    """Validate CreateCustomRuleRequest DTO."""

    def test_valid(self) -> None:
        req = CreateCustomRuleRequest(
            name="my-rule",
            description="Fires when quality drops",
            metric_path="performance.avg_quality_score",
            comparator=Comparator.LT,
            threshold=5.0,
            severity=RuleSeverity.WARNING,
            target_altitudes=(ProposalAltitude.CONFIG_TUNING,),
        )
        assert req.name == "my-rule"
        assert req.comparator == Comparator.LT

    def test_requires_at_least_one_altitude(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            CreateCustomRuleRequest(
                name="bad-rule",
                description="No altitudes",
                metric_path="performance.avg_quality_score",
                comparator=Comparator.LT,
                threshold=5.0,
                severity=RuleSeverity.WARNING,
                target_altitudes=(),
            )


class TestUpdateCustomRuleRequest:
    """Validate UpdateCustomRuleRequest DTO."""

    def test_all_optional(self) -> None:
        req = UpdateCustomRuleRequest()
        assert req.name is None
        assert req.threshold is None

    def test_partial_update(self) -> None:
        req = UpdateCustomRuleRequest(
            threshold=9.0,
            severity=RuleSeverity.CRITICAL,
        )
        assert req.threshold == 9.0
        assert req.severity == RuleSeverity.CRITICAL
        assert req.name is None


class TestPreviewRuleRequest:
    """Validate PreviewRuleRequest DTO."""

    def test_valid(self) -> None:
        req = PreviewRuleRequest(
            metric_path="performance.avg_quality_score",
            comparator=Comparator.LT,
            threshold=5.0,
            sample_value=3.0,
        )
        assert req.sample_value == 3.0


# ── Serialization helpers ─────────────────────────────────────────


class TestSerializationHelpers:
    """Test _rule_to_dict and _metric_to_dict."""

    def test_rule_to_dict(self) -> None:
        now = datetime.now(UTC)
        defn = CustomRuleDefinition(
            id=uuid4(),
            name="test",
            description="Test rule",
            metric_path="performance.avg_quality_score",
            comparator=Comparator.GT,
            threshold=8.0,
            severity=RuleSeverity.INFO,
            target_altitudes=(
                ProposalAltitude.CONFIG_TUNING,
                ProposalAltitude.ARCHITECTURE,
            ),
            created_at=now,
            updated_at=now,
        )
        d = _rule_to_dict(defn)
        assert d["name"] == "test"
        assert d["comparator"] == "gt"
        assert d["severity"] == "info"
        assert d["target_altitudes"] == [
            "config_tuning",
            "architecture",
        ]
        assert d["enabled"] is True

    def test_metric_to_dict(self) -> None:
        metric = METRIC_REGISTRY[0]
        d = _metric_to_dict(metric)
        assert d["path"] == metric.path
        assert d["label"] == metric.label
        assert d["domain"] == metric.domain
        assert "value_type" in d
        assert "nullable" in d


# ── Preview snapshot builder ──────────────────────────────────────


class TestBuildPreviewSnapshot:
    """Test _build_preview_snapshot utility."""

    def test_performance_metric(self) -> None:
        snap = _build_preview_snapshot(
            "performance.avg_quality_score",
            3.5,
        )
        val = resolve_metric(snap, "performance.avg_quality_score")
        assert val == 3.5

    def test_budget_integer_metric(self) -> None:
        snap = _build_preview_snapshot(
            "budget.days_until_exhausted",
            7.0,
        )
        val = resolve_metric(snap, "budget.days_until_exhausted")
        assert val == 7
        assert isinstance(val, int)

    def test_coordination_nullable_metric(self) -> None:
        snap = _build_preview_snapshot(
            "coordination.coordination_overhead_pct",
            45.0,
        )
        val = resolve_metric(
            snap,
            "coordination.coordination_overhead_pct",
        )
        assert val == 45.0

    def test_errors_metric(self) -> None:
        snap = _build_preview_snapshot("errors.total_findings", 15.0)
        val = resolve_metric(snap, "errors.total_findings")
        assert val == 15
        assert isinstance(val, int)

    def test_telemetry_metric(self) -> None:
        snap = _build_preview_snapshot("telemetry.event_count", 200.0)
        val = resolve_metric(snap, "telemetry.event_count")
        assert val == 200

    @pytest.mark.parametrize(
        "metric_path",
        [m.path for m in METRIC_REGISTRY],
    )
    def test_all_registry_metrics_buildable(
        self,
        metric_path: str,
    ) -> None:
        """Every registered metric can produce a valid snapshot."""
        snap = _build_preview_snapshot(metric_path, 1.0)
        val = resolve_metric(snap, metric_path)
        assert val is not None


# ── Preview rule evaluation ───────────────────────────────────────


class TestPreviewEvaluation:
    """Test that preview evaluation works end-to-end."""

    def test_preview_fires(self) -> None:
        now = datetime.now(UTC)
        defn = CustomRuleDefinition(
            name="preview",
            description="Preview rule",
            metric_path="performance.avg_quality_score",
            comparator=Comparator.LT,
            threshold=5.0,
            severity=RuleSeverity.INFO,
            target_altitudes=(ProposalAltitude.CONFIG_TUNING,),
            created_at=now,
            updated_at=now,
        )
        rule = DeclarativeRule(defn)
        snap = _build_preview_snapshot(
            "performance.avg_quality_score",
            3.0,
        )
        match = rule.evaluate(snap)
        assert match is not None
        assert match.signal_context["metric_value"] == 3.0

    def test_preview_does_not_fire(self) -> None:
        now = datetime.now(UTC)
        defn = CustomRuleDefinition(
            name="preview",
            description="Preview rule",
            metric_path="performance.avg_quality_score",
            comparator=Comparator.LT,
            threshold=5.0,
            severity=RuleSeverity.INFO,
            target_altitudes=(ProposalAltitude.CONFIG_TUNING,),
            created_at=now,
            updated_at=now,
        )
        rule = DeclarativeRule(defn)
        snap = _build_preview_snapshot(
            "performance.avg_quality_score",
            7.0,
        )
        match = rule.evaluate(snap)
        assert match is None
