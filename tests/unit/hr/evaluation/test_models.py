"""Tests for evaluation framework domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.core.types import NotBlankStr
from synthorg.hr.evaluation.config import EvaluationConfig
from synthorg.hr.evaluation.enums import EvaluationPillar
from synthorg.hr.evaluation.models import (
    EvaluationReport,
    InteractionFeedback,
    PillarScore,
    ResilienceMetrics,
    redistribute_weights,
)
from tests.unit.hr.evaluation.conftest import make_pillar_score, make_snapshot

pytestmark = pytest.mark.unit

# ── redistribute_weights ─────────────────────────────────────


class TestRedistributeWeights:
    """Tests for the redistribute_weights utility function."""

    def test_all_enabled_preserves_proportions(self) -> None:
        items = [("a", 0.4, True), ("b", 0.3, True), ("c", 0.3, True)]
        result = redistribute_weights(items)
        assert result == {"a": 0.4, "b": 0.3, "c": 0.3}

    def test_one_disabled_redistributes(self) -> None:
        items = [("a", 0.4, True), ("b", 0.3, False), ("c", 0.3, True)]
        result = redistribute_weights(items)
        total = result["a"] + result["c"]
        assert abs(total - 1.0) < 1e-9
        # a had 0.4 and c had 0.3, so proportions should be 4:3.
        assert abs(result["a"] - 0.4 / 0.7) < 1e-9
        assert abs(result["c"] - 0.3 / 0.7) < 1e-9

    def test_all_disabled_raises(self) -> None:
        items = [("a", 0.5, False), ("b", 0.5, False)]
        with pytest.raises(ValueError, match="At least one item must be enabled"):
            redistribute_weights(items)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one item must be enabled"):
            redistribute_weights([])

    def test_zero_weight_enabled_equal_distribution(self) -> None:
        items = [("a", 0.0, True), ("b", 0.0, True), ("c", 0.0, True)]
        result = redistribute_weights(items)
        expected = 1.0 / 3
        for v in result.values():
            assert abs(v - expected) < 1e-9

    def test_single_enabled_gets_full_weight(self) -> None:
        items = [("a", 0.2, True), ("b", 0.3, False), ("c", 0.5, False)]
        result = redistribute_weights(items)
        assert result == {"a": 1.0}

    def test_result_sums_to_one(self) -> None:
        items = [
            ("a", 0.1, True),
            ("b", 0.2, False),
            ("c", 0.3, True),
            ("d", 0.15, True),
            ("e", 0.25, False),
        ]
        result = redistribute_weights(items)
        assert abs(sum(result.values()) - 1.0) < 1e-9


# ── InteractionFeedback ─────────────────────────────────────


class TestInteractionFeedback:
    """InteractionFeedback model tests."""

    def test_create_with_all_ratings(self) -> None:
        fb = InteractionFeedback(
            agent_id=NotBlankStr("agent-001"),
            recorded_at=datetime.now(UTC),
            clarity_rating=0.8,
            tone_rating=0.7,
            helpfulness_rating=0.9,
            trust_rating=0.85,
            satisfaction_rating=0.8,
            source=NotBlankStr("human"),
        )
        assert fb.clarity_rating == 0.8
        assert fb.source == "human"

    def test_create_with_partial_ratings(self) -> None:
        fb = InteractionFeedback(
            agent_id=NotBlankStr("agent-001"),
            recorded_at=datetime.now(UTC),
            clarity_rating=0.8,
            source=NotBlankStr("automated"),
        )
        assert fb.clarity_rating == 0.8
        assert fb.tone_rating is None
        assert fb.helpfulness_rating is None

    def test_frozen(self) -> None:
        fb = InteractionFeedback(
            agent_id=NotBlankStr("agent-001"),
            recorded_at=datetime.now(UTC),
            source=NotBlankStr("human"),
        )
        with pytest.raises(ValidationError):
            fb.clarity_rating = 0.5  # type: ignore[misc]

    @pytest.mark.parametrize(
        "field",
        [
            "clarity_rating",
            "tone_rating",
            "helpfulness_rating",
            "trust_rating",
            "satisfaction_rating",
        ],
    )
    def test_rating_lower_bound(self, field: str) -> None:
        kwargs: dict[str, object] = {field: -0.1}
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            InteractionFeedback(
                agent_id=NotBlankStr("agent-001"),
                recorded_at=datetime.now(UTC),
                source=NotBlankStr("human"),
                **kwargs,  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        "field",
        [
            "clarity_rating",
            "tone_rating",
            "helpfulness_rating",
            "trust_rating",
            "satisfaction_rating",
        ],
    )
    def test_rating_upper_bound(self, field: str) -> None:
        kwargs: dict[str, object] = {field: 1.1}
        with pytest.raises(ValueError, match="less than or equal to 1"):
            InteractionFeedback(
                agent_id=NotBlankStr("agent-001"),
                recorded_at=datetime.now(UTC),
                source=NotBlankStr("human"),
                **kwargs,  # type: ignore[arg-type]
            )

    def test_free_text_max_length(self) -> None:
        with pytest.raises(ValueError, match="4096"):
            InteractionFeedback(
                agent_id=NotBlankStr("agent-001"),
                recorded_at=datetime.now(UTC),
                source=NotBlankStr("human"),
                free_text="x" * 4097,
            )

    def test_auto_generates_id(self) -> None:
        fb1 = InteractionFeedback(
            agent_id=NotBlankStr("agent-001"),
            recorded_at=datetime.now(UTC),
            source=NotBlankStr("human"),
        )
        fb2 = InteractionFeedback(
            agent_id=NotBlankStr("agent-001"),
            recorded_at=datetime.now(UTC),
            source=NotBlankStr("human"),
        )
        assert fb1.id != fb2.id


# ── ResilienceMetrics ─────────────────────────────────────


class TestResilienceMetrics:
    """ResilienceMetrics model tests."""

    def test_create_valid(self) -> None:
        rm = ResilienceMetrics(
            total_tasks=20,
            failed_tasks=3,
            recovered_tasks=2,
            current_success_streak=5,
            longest_success_streak=10,
            quality_score_stddev=1.2,
        )
        assert rm.total_tasks == 20
        assert rm.recovered_tasks == 2

    def test_zero_tasks(self) -> None:
        rm = ResilienceMetrics(
            total_tasks=0,
            failed_tasks=0,
            recovered_tasks=0,
            current_success_streak=0,
            longest_success_streak=0,
        )
        assert rm.total_tasks == 0

    def test_failed_exceeds_total_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed total_tasks"):
            ResilienceMetrics(
                total_tasks=5,
                failed_tasks=6,
                recovered_tasks=0,
                current_success_streak=0,
                longest_success_streak=0,
            )

    def test_recovered_exceeds_failed_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed failed_tasks"):
            ResilienceMetrics(
                total_tasks=10,
                failed_tasks=3,
                recovered_tasks=4,
                current_success_streak=0,
                longest_success_streak=0,
            )

    def test_current_streak_exceeds_longest_raises(self) -> None:
        with pytest.raises(
            ValueError,
            match="cannot be less than current_success_streak",
        ):
            ResilienceMetrics(
                total_tasks=10,
                failed_tasks=2,
                recovered_tasks=1,
                current_success_streak=8,
                longest_success_streak=5,
            )

    def test_frozen(self) -> None:
        rm = ResilienceMetrics(
            total_tasks=10,
            failed_tasks=2,
            recovered_tasks=1,
            current_success_streak=3,
            longest_success_streak=5,
        )
        with pytest.raises(ValidationError):
            rm.total_tasks = 20  # type: ignore[misc]


# ── PillarScore ─────────────────────────────────────


class TestPillarScore:
    """PillarScore model tests."""

    def test_create_valid(self) -> None:
        ps = make_pillar_score()
        assert ps.pillar == EvaluationPillar.INTELLIGENCE
        assert ps.score == 7.5
        assert ps.confidence == 0.8

    def test_score_bounds(self) -> None:
        make_pillar_score(score=0.0)
        make_pillar_score(score=10.0)
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            make_pillar_score(score=-0.1)
        with pytest.raises(ValueError, match="less than or equal to 10"):
            make_pillar_score(score=10.1)

    def test_confidence_bounds(self) -> None:
        make_pillar_score(confidence=0.0)
        make_pillar_score(confidence=1.0)
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            make_pillar_score(confidence=-0.1)
        with pytest.raises(ValueError, match="less than or equal to 1"):
            make_pillar_score(confidence=1.1)

    def test_breakdown_tuple(self) -> None:
        ps = PillarScore(
            pillar=EvaluationPillar.RESILIENCE,
            score=8.0,
            confidence=0.9,
            strategy_name=NotBlankStr("test"),
            breakdown=(
                (NotBlankStr("success_rate"), 9.0),
                (NotBlankStr("recovery"), 7.0),
            ),
            data_point_count=15,
            evaluated_at=datetime.now(UTC),
        )
        assert len(ps.breakdown) == 2
        assert ps.breakdown[0][0] == "success_rate"

    def test_frozen(self) -> None:
        ps = make_pillar_score()
        with pytest.raises(ValidationError):
            ps.score = 5.0  # type: ignore[misc]


# ── EvaluationContext ─────────────────────────────────────


class TestEvaluationContext:
    """EvaluationContext model tests."""

    def test_agent_id_mismatch_raises(self) -> None:
        """Mismatched agent_id between context and snapshot must raise."""
        from synthorg.hr.evaluation.models import EvaluationContext

        with pytest.raises(ValueError, match="does not match"):
            EvaluationContext(
                agent_id=NotBlankStr("agent-001"),
                now=datetime.now(UTC),
                config=EvaluationConfig(),
                snapshot=make_snapshot(agent_id="agent-999"),
            )


# ── EvaluationReport ─────────────────────────────────────


class TestEvaluationReport:
    """EvaluationReport model tests."""

    def test_create_valid(self) -> None:
        now = datetime.now(UTC)
        snapshot = make_snapshot()
        scores = (
            make_pillar_score(pillar=EvaluationPillar.INTELLIGENCE),
            make_pillar_score(pillar=EvaluationPillar.EFFICIENCY),
        )
        report = EvaluationReport(
            agent_id=NotBlankStr("agent-001"),
            computed_at=now,
            snapshot=snapshot,
            pillar_scores=scores,
            overall_score=7.5,
            overall_confidence=0.8,
            pillar_weights=(
                (NotBlankStr("intelligence"), 0.5),
                (NotBlankStr("efficiency"), 0.5),
            ),
        )
        assert report.agent_id == "agent-001"
        assert len(report.pillar_scores) == 2

    def test_duplicate_pillars_raises(self) -> None:
        now = datetime.now(UTC)
        snapshot = make_snapshot()
        scores = (
            make_pillar_score(pillar=EvaluationPillar.INTELLIGENCE),
            make_pillar_score(pillar=EvaluationPillar.INTELLIGENCE),
        )
        with pytest.raises(ValueError, match="Duplicate pillar scores"):
            EvaluationReport(
                agent_id=NotBlankStr("agent-001"),
                computed_at=now,
                snapshot=snapshot,
                pillar_scores=scores,
                overall_score=7.5,
                overall_confidence=0.8,
                pillar_weights=(
                    (NotBlankStr("intelligence"), 0.5),
                    (NotBlankStr("intelligence"), 0.5),
                ),
            )

    def test_auto_generates_id(self) -> None:
        now = datetime.now(UTC)
        snapshot = make_snapshot()
        r1 = EvaluationReport(
            agent_id=NotBlankStr("agent-001"),
            computed_at=now,
            snapshot=snapshot,
            pillar_scores=(),
            overall_score=0.0,
            overall_confidence=0.0,
            pillar_weights=(),
        )
        r2 = EvaluationReport(
            agent_id=NotBlankStr("agent-001"),
            computed_at=now,
            snapshot=snapshot,
            pillar_scores=(),
            overall_score=0.0,
            overall_confidence=0.0,
            pillar_weights=(),
        )
        assert r1.id != r2.id

    def test_overall_score_bounds(self) -> None:
        now = datetime.now(UTC)
        snapshot = make_snapshot()
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            EvaluationReport(
                agent_id=NotBlankStr("agent-001"),
                computed_at=now,
                snapshot=snapshot,
                pillar_scores=(),
                overall_score=-0.1,
                overall_confidence=0.0,
                pillar_weights=(),
            )
        with pytest.raises(ValueError, match="less than or equal to 10"):
            EvaluationReport(
                agent_id=NotBlankStr("agent-001"),
                computed_at=now,
                snapshot=snapshot,
                pillar_scores=(),
                overall_score=10.1,
                overall_confidence=0.0,
                pillar_weights=(),
            )

    def test_frozen(self) -> None:
        now = datetime.now(UTC)
        snapshot = make_snapshot()
        report = EvaluationReport(
            agent_id=NotBlankStr("agent-001"),
            computed_at=now,
            snapshot=snapshot,
            pillar_scores=(),
            overall_score=5.0,
            overall_confidence=0.5,
            pillar_weights=(),
        )
        with pytest.raises(ValidationError):
            report.overall_score = 8.0  # type: ignore[misc]

    def test_agent_id_mismatch_raises(self) -> None:
        """Report agent_id must match snapshot agent_id."""
        now = datetime.now(UTC)
        snapshot = make_snapshot(agent_id="agent-999")
        with pytest.raises(ValueError, match="does not match"):
            EvaluationReport(
                agent_id=NotBlankStr("agent-001"),
                computed_at=now,
                snapshot=snapshot,
                pillar_scores=(),
                overall_score=0.0,
                overall_confidence=0.0,
                pillar_weights=(),
            )

    def test_weights_scores_mismatch_raises(self) -> None:
        """Pillar weight names must match pillar score names."""
        now = datetime.now(UTC)
        snapshot = make_snapshot()
        scores = (make_pillar_score(pillar=EvaluationPillar.INTELLIGENCE),)
        with pytest.raises(ValueError, match="do not match"):
            EvaluationReport(
                agent_id=NotBlankStr("agent-001"),
                computed_at=now,
                snapshot=snapshot,
                pillar_scores=scores,
                overall_score=7.5,
                overall_confidence=0.8,
                pillar_weights=((NotBlankStr("efficiency"), 1.0),),
            )
