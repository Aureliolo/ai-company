"""Unit tests for the cross-deployment pattern aggregator."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.meta.telemetry.aggregator import aggregate_patterns
from synthorg.meta.telemetry.models import AnonymizedOutcomeEvent

pytestmark = pytest.mark.unit


def _make_event(  # noqa: PLR0913
    *,
    deployment_id: str = "deploy-aaa",
    event_type: str = "proposal_decision",
    altitude: str = "config_tuning",
    source_rule: str = "coordination_overhead",
    decision: str | None = "approved",
    confidence: float | None = 0.7,
    rollout_outcome: str | None = None,
    regression_verdict: str | None = None,
    observation_hours: float | None = None,
    industry_tag: str | None = "technology",
) -> AnonymizedOutcomeEvent:
    return AnonymizedOutcomeEvent(
        deployment_id=NotBlankStr(deployment_id),
        event_type=event_type,  # type: ignore[arg-type]
        timestamp=NotBlankStr("2026-04-16"),
        altitude=NotBlankStr(altitude),
        source_rule=NotBlankStr(source_rule) if source_rule else None,
        decision=decision,  # type: ignore[arg-type]
        confidence=confidence,
        rollout_outcome=NotBlankStr(rollout_outcome) if rollout_outcome else None,
        regression_verdict=(
            NotBlankStr(regression_verdict) if regression_verdict else None
        ),
        observation_hours=observation_hours,
        enabled_altitudes=(NotBlankStr("config_tuning"),),
        industry_tag=NotBlankStr(industry_tag) if industry_tag else None,
        sdk_version=NotBlankStr("0.6.8"),
    )


class TestAggregatePatterns:
    """Tests for aggregate_patterns()."""

    def test_empty_events_returns_empty(self) -> None:
        assert aggregate_patterns(()) == ()

    def test_below_min_deployments_filtered_out(self) -> None:
        events = tuple(_make_event(deployment_id=f"deploy-{i}") for i in range(2))
        result = aggregate_patterns(events, min_deployments=3)
        assert result == ()

    def test_meets_min_deployments_included(self) -> None:
        events = tuple(_make_event(deployment_id=f"deploy-{i}") for i in range(3))
        result = aggregate_patterns(events, min_deployments=3)
        assert len(result) == 1
        assert result[0].deployment_count == 3
        assert result[0].source_rule == "coordination_overhead"
        assert result[0].altitude == "config_tuning"

    def test_approval_rate_computed(self) -> None:
        events = (
            _make_event(deployment_id="a", decision="approved"),
            _make_event(deployment_id="b", decision="approved"),
            _make_event(deployment_id="c", decision="rejected"),
        )
        result = aggregate_patterns(events, min_deployments=3)
        assert len(result) == 1
        assert abs(result[0].approval_rate - 2 / 3) < 0.01

    def test_success_rate_from_rollout_events(self) -> None:
        events = (
            _make_event(
                deployment_id="a",
                event_type="rollout_result",
                decision=None,
                confidence=None,
                rollout_outcome="success",
                observation_hours=48.0,
            ),
            _make_event(
                deployment_id="b",
                event_type="rollout_result",
                decision=None,
                confidence=None,
                rollout_outcome="regressed",
                observation_hours=24.0,
            ),
            _make_event(
                deployment_id="c",
                event_type="rollout_result",
                decision=None,
                confidence=None,
                rollout_outcome="success",
                observation_hours=48.0,
            ),
        )
        result = aggregate_patterns(events, min_deployments=3)
        assert len(result) == 1
        assert abs(result[0].success_rate - 2 / 3) < 0.01

    def test_avg_observation_hours(self) -> None:
        events = (
            _make_event(
                deployment_id="a",
                event_type="rollout_result",
                decision=None,
                confidence=None,
                rollout_outcome="success",
                observation_hours=48.0,
            ),
            _make_event(
                deployment_id="b",
                event_type="rollout_result",
                decision=None,
                confidence=None,
                rollout_outcome="success",
                observation_hours=24.0,
            ),
            _make_event(
                deployment_id="c",
                event_type="rollout_result",
                decision=None,
                confidence=None,
                rollout_outcome="success",
                observation_hours=72.0,
            ),
        )
        result = aggregate_patterns(events, min_deployments=3)
        assert result[0].avg_observation_hours == 48.0

    def test_avg_observation_hours_none_without_rollouts(self) -> None:
        events = tuple(_make_event(deployment_id=f"deploy-{i}") for i in range(3))
        result = aggregate_patterns(events, min_deployments=3)
        assert result[0].avg_observation_hours is None

    def test_industry_breakdown(self) -> None:
        events = (
            _make_event(deployment_id="a", industry_tag="technology"),
            _make_event(deployment_id="b", industry_tag="technology"),
            _make_event(deployment_id="c", industry_tag="healthcare"),
        )
        result = aggregate_patterns(events, min_deployments=3)
        breakdown = dict(result[0].industry_breakdown)
        assert breakdown["technology"] == 2
        assert breakdown["healthcare"] == 1

    def test_multiple_rule_altitude_groups(self) -> None:
        events = (
            # Group 1: coordination_overhead / config_tuning.
            _make_event(deployment_id="a", source_rule="coordination_overhead"),
            _make_event(deployment_id="b", source_rule="coordination_overhead"),
            _make_event(deployment_id="c", source_rule="coordination_overhead"),
            # Group 2: quality_declining / config_tuning.
            _make_event(deployment_id="a", source_rule="quality_declining"),
            _make_event(deployment_id="b", source_rule="quality_declining"),
            _make_event(deployment_id="c", source_rule="quality_declining"),
        )
        result = aggregate_patterns(events, min_deployments=3)
        assert len(result) == 2

    def test_sorted_by_deployment_count_descending(self) -> None:
        events = (
            # 4 deployments for coordination_overhead.
            *[
                _make_event(
                    deployment_id=f"d-{i}",
                    source_rule="coordination_overhead",
                )
                for i in range(4)
            ],
            # 3 deployments for quality_declining.
            *[
                _make_event(
                    deployment_id=f"d-{i}",
                    source_rule="quality_declining",
                )
                for i in range(3)
            ],
        )
        result = aggregate_patterns(events, min_deployments=3)
        assert result[0].source_rule == "coordination_overhead"
        assert result[1].source_rule == "quality_declining"

    def test_mixed_decision_and_rollout_events(self) -> None:
        events = (
            _make_event(deployment_id="a", decision="approved"),
            _make_event(
                deployment_id="b",
                event_type="rollout_result",
                decision=None,
                confidence=None,
                rollout_outcome="success",
                observation_hours=48.0,
            ),
            _make_event(deployment_id="c", decision="rejected"),
        )
        result = aggregate_patterns(events, min_deployments=3)
        assert len(result) == 1
        assert result[0].total_events == 3
        # 1 approved out of 2 decisions.
        assert abs(result[0].approval_rate - 0.5) < 0.01
        # 1 success out of 1 rollout.
        assert result[0].success_rate == 1.0
