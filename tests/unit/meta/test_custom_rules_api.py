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
    rule_to_dict,
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
        assert CustomRuleController.path == "/meta/custom-rules"

    @pytest.mark.parametrize(
        ("method_name", "expected_path", "expected_method"),
        [
            ("list_rules", "/", "GET"),
            ("get_rule", "/{rule_id:str}", "GET"),
            ("create_rule", "/", "POST"),
            ("update_rule", "/{rule_id:str}", "PATCH"),
            ("delete_rule", "/{rule_id:str}", "DELETE"),
            ("toggle_rule", "/{rule_id:str}/toggle", "POST"),
            ("list_metrics", "/metrics", "GET"),
            ("preview_rule", "/preview", "POST"),
        ],
    )
    def test_has_endpoint(
        self,
        method_name: str,
        expected_path: str,
        expected_method: str,
    ) -> None:
        handler = getattr(CustomRuleController, method_name, None)
        assert handler is not None, f"Missing handler: {method_name}"
        assert expected_path in handler.paths, (
            f"{method_name}: expected path {expected_path!r}, got {handler.paths}"
        )
        assert expected_method in handler.http_methods, (
            f"{method_name}: expected method {expected_method!r}, "
            f"got {handler.http_methods}"
        )


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
    """Test rule_to_dict and _metric_to_dict."""

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
        d = rule_to_dict(defn)
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

    @pytest.mark.parametrize(
        ("metric_path", "sample_input", "expected_value", "expected_type"),
        [
            ("performance.avg_quality_score", 3.5, 3.5, None),
            ("budget.days_until_exhausted", 7.0, 7, int),
            ("coordination.coordination_overhead_pct", 45.0, 45.0, None),
            ("errors.total_findings", 15.0, 15, int),
            ("telemetry.event_count", 200.0, 200, int),
        ],
    )
    def test_domain_metric(
        self,
        metric_path: str,
        sample_input: float,
        expected_value: float | int,
        expected_type: type | None,
    ) -> None:
        snap = _build_preview_snapshot(metric_path, sample_input)
        val = resolve_metric(snap, metric_path)
        assert val == expected_value
        if expected_type is not None:
            assert isinstance(val, expected_type)

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

    @pytest.mark.parametrize(
        ("sample_value", "should_fire"),
        [
            (3.0, True),
            (7.0, False),
        ],
    )
    def test_preview_evaluation(
        self,
        sample_value: float,
        *,
        should_fire: bool,
    ) -> None:
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
            sample_value,
        )
        match = rule.evaluate(snap)
        if should_fire:
            assert match is not None
            assert match.signal_context["metric_value"] == sample_value
        else:
            assert match is None
