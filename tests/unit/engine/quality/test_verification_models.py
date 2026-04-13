"""Tests for verification stage data models."""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from synthorg.engine.quality.verification import (
    FRONTEND_DESIGN_RUBRIC,
    AtomicProbe,
    CalibrationExample,
    GradeType,
    RubricCriterion,
    VerificationResult,
    VerificationRubric,
    VerificationVerdict,
)

# ── VerificationVerdict ─────────────────────────────────────────


@pytest.mark.unit
class TestVerificationVerdict:
    def test_has_3_members(self) -> None:
        assert len(VerificationVerdict) == 3

    def test_values(self) -> None:
        assert VerificationVerdict.PASS.value == "pass"
        assert VerificationVerdict.FAIL.value == "fail"
        assert VerificationVerdict.REFER.value == "refer"

    def test_is_strenum(self) -> None:
        assert isinstance(VerificationVerdict.PASS, str)


# ── RubricCriterion ─────────────────────────────────────────────


@pytest.mark.unit
class TestRubricCriterion:
    def test_valid_criterion(self) -> None:
        c = RubricCriterion(
            name="design",
            description="Visual quality",
            weight=0.5,
            grade_type=GradeType.SCORE,
        )
        assert c.name == "design"
        assert c.weight == 0.5

    def test_frozen(self) -> None:
        c = RubricCriterion(
            name="x", description="y", weight=0.5, grade_type=GradeType.BINARY
        )
        with pytest.raises(ValidationError, match="frozen"):
            c.name = "z"  # type: ignore[misc]

    def test_rejects_nan_weight(self) -> None:
        with pytest.raises(ValidationError):
            RubricCriterion(
                name="x",
                description="y",
                weight=float("nan"),
                grade_type=GradeType.BINARY,
            )

    def test_rejects_inf_weight(self) -> None:
        with pytest.raises(ValidationError):
            RubricCriterion(
                name="x",
                description="y",
                weight=float("inf"),
                grade_type=GradeType.BINARY,
            )

    def test_rejects_negative_weight(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            RubricCriterion(
                name="x", description="y", weight=-0.1, grade_type=GradeType.BINARY
            )

    def test_rejects_weight_above_one(self) -> None:
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            RubricCriterion(
                name="x", description="y", weight=1.1, grade_type=GradeType.BINARY
            )

    def test_rejects_blank_name(self) -> None:
        with pytest.raises(ValidationError):
            RubricCriterion(
                name="", description="y", weight=0.5, grade_type=GradeType.BINARY
            )

    def test_rejects_blank_description(self) -> None:
        with pytest.raises(ValidationError):
            RubricCriterion(
                name="x", description="", weight=0.5, grade_type=GradeType.BINARY
            )

    @pytest.mark.parametrize("grade_type", ["binary", "ternary", "score"])
    def test_valid_grade_types(self, grade_type: str) -> None:
        c = RubricCriterion.model_validate(
            {"name": "x", "description": "y", "weight": 0.5, "grade_type": grade_type}
        )
        assert c.grade_type == grade_type

    def test_rejects_invalid_grade_type(self) -> None:
        with pytest.raises(ValidationError):
            RubricCriterion.model_validate(
                {
                    "name": "x",
                    "description": "y",
                    "weight": 0.5,
                    "grade_type": "percentile",
                }
            )


# ── CalibrationExample ──────────────────────────────────────────


@pytest.mark.unit
class TestCalibrationExample:
    def test_valid_example(self) -> None:
        ex = CalibrationExample(
            artifact_summary="A well-designed page",
            expected_verdict=VerificationVerdict.PASS,
            rationale="Meets all criteria",
        )
        assert ex.expected_verdict == VerificationVerdict.PASS
        assert ex.expected_grades is None

    def test_with_expected_grades(self) -> None:
        ex = CalibrationExample(
            artifact_summary="Partial impl",
            expected_verdict=VerificationVerdict.FAIL,
            rationale="Missing functionality",
            expected_grades={"design": 0.8, "functionality": 0.2},
        )
        assert ex.expected_grades is not None
        assert ex.expected_grades["functionality"] == 0.2

    def test_frozen(self) -> None:
        ex = CalibrationExample(
            artifact_summary="x",
            expected_verdict=VerificationVerdict.PASS,
            rationale="y",
        )
        with pytest.raises(ValidationError, match="frozen"):
            ex.rationale = "z"  # type: ignore[misc]


# ── VerificationRubric ──────────────────────────────────────────


def _criterion(name: str, weight: float) -> RubricCriterion:
    return RubricCriterion(
        name=name, description=f"Test {name}", weight=weight, grade_type=GradeType.SCORE
    )


@pytest.mark.unit
class TestVerificationRubric:
    def test_valid_rubric(self) -> None:
        rubric = VerificationRubric(
            name="test-rubric",
            criteria=(_criterion("a", 0.5), _criterion("b", 0.5)),
        )
        assert rubric.name == "test-rubric"
        assert len(rubric.criteria) == 2
        assert rubric.min_confidence == 0.7

    def test_rejects_empty_criteria(self) -> None:
        with pytest.raises(ValidationError, match="at least one criterion"):
            VerificationRubric(name="empty", criteria=())

    def test_rejects_weights_not_summing_to_one(self) -> None:
        with pytest.raises(ValidationError, match=r"sum to 1\.0"):
            VerificationRubric(
                name="bad",
                criteria=(_criterion("a", 0.3), _criterion("b", 0.3)),
            )

    def test_rejects_duplicate_criterion_names(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate criterion"):
            VerificationRubric(
                name="dup",
                criteria=(_criterion("a", 0.5), _criterion("a", 0.5)),
            )

    def test_frozen(self) -> None:
        rubric = VerificationRubric(name="r", criteria=(_criterion("x", 1.0),))
        with pytest.raises(ValidationError, match="frozen"):
            rubric.name = "changed"  # type: ignore[misc]

    @given(
        w1=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=50)
    def test_weights_not_summing_to_one_rejected_property(self, w1: float) -> None:
        w2 = 1.0 - w1
        if w2 < 0.0 or w2 > 1.0:
            return
        rubric = VerificationRubric(
            name="prop",
            criteria=(_criterion("a", w1), _criterion("b", w2)),
        )
        assert rubric is not None


# ── AtomicProbe ─────────────────────────────────────────────────


@pytest.mark.unit
class TestAtomicProbe:
    def test_valid_probe(self) -> None:
        probe = AtomicProbe(
            id="probe-1",
            probe_text="Is the button visible?",
            source_criterion="Button must be visible",
        )
        assert probe.id == "probe-1"

    def test_frozen(self) -> None:
        probe = AtomicProbe(id="p", probe_text="q?", source_criterion="q")
        with pytest.raises(ValidationError, match="frozen"):
            probe.id = "changed"  # type: ignore[misc]

    def test_rejects_blank_id(self) -> None:
        with pytest.raises(ValidationError):
            AtomicProbe(id="", probe_text="q?", source_criterion="q")

    def test_rejects_blank_probe_text(self) -> None:
        with pytest.raises(ValidationError):
            AtomicProbe(id="p", probe_text="", source_criterion="q")


# ── VerificationResult ──────────────────────────────────────────


def _ts() -> datetime:
    return datetime.now(UTC)


@pytest.mark.unit
class TestVerificationResult:
    def test_valid_result(self) -> None:
        r = VerificationResult(
            verdict=VerificationVerdict.PASS,
            confidence=0.9,
            per_criterion_grades={"design": 0.8, "craft": 0.7},
            findings=("Good layout",),
            evaluator_agent_id="eval-agent",
            generator_agent_id="gen-agent",
            rubric_name="test-rubric",
            timestamp=_ts(),
        )
        assert r.passed is True
        assert r.verdict == VerificationVerdict.PASS

    def test_passed_computed_field_false_on_fail(self) -> None:
        r = VerificationResult(
            verdict=VerificationVerdict.FAIL,
            confidence=0.8,
            per_criterion_grades={"x": 0.2},
            evaluator_agent_id="eval",
            generator_agent_id="gen",
            rubric_name="r",
            timestamp=_ts(),
        )
        assert r.passed is False

    def test_passed_computed_field_false_on_refer(self) -> None:
        r = VerificationResult(
            verdict=VerificationVerdict.REFER,
            confidence=0.4,
            per_criterion_grades={"x": 0.5},
            evaluator_agent_id="eval",
            generator_agent_id="gen",
            rubric_name="r",
            timestamp=_ts(),
        )
        assert r.passed is False

    def test_rejects_self_evaluation(self) -> None:
        with pytest.raises(ValidationError, match="Self-evaluation rejected"):
            VerificationResult(
                verdict=VerificationVerdict.PASS,
                confidence=0.9,
                per_criterion_grades={"x": 1.0},
                evaluator_agent_id="same-agent",
                generator_agent_id="same-agent",
                rubric_name="r",
                timestamp=_ts(),
            )

    def test_frozen(self) -> None:
        r = VerificationResult(
            verdict=VerificationVerdict.PASS,
            confidence=0.9,
            per_criterion_grades={"x": 1.0},
            evaluator_agent_id="eval",
            generator_agent_id="gen",
            rubric_name="r",
            timestamp=_ts(),
        )
        with pytest.raises(ValidationError, match="frozen"):
            r.verdict = VerificationVerdict.FAIL  # type: ignore[misc]

    def test_rejects_nan_confidence(self) -> None:
        with pytest.raises(ValidationError):
            VerificationResult(
                verdict=VerificationVerdict.PASS,
                confidence=float("nan"),
                per_criterion_grades={},
                evaluator_agent_id="eval",
                generator_agent_id="gen",
                rubric_name="r",
                timestamp=_ts(),
            )

    def test_json_roundtrip(self) -> None:
        r = VerificationResult(
            verdict=VerificationVerdict.PASS,
            confidence=0.85,
            per_criterion_grades={"design": 0.9},
            findings=("Looks great",),
            evaluator_agent_id="eval",
            generator_agent_id="gen",
            rubric_name="test",
            timestamp=_ts(),
        )
        restored = VerificationResult.model_validate_json(r.model_dump_json())
        assert restored.verdict == r.verdict
        assert restored.confidence == r.confidence
        assert restored.passed == r.passed

    @given(
        agent_name=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
    )
    @settings(max_examples=50)
    def test_self_eval_always_rejected_property(self, agent_name: str) -> None:
        with pytest.raises(ValidationError, match="Self-evaluation"):
            VerificationResult(
                verdict=VerificationVerdict.PASS,
                confidence=0.9,
                per_criterion_grades={"x": 1.0},
                evaluator_agent_id=agent_name,
                generator_agent_id=agent_name,
                rubric_name="r",
                timestamp=_ts(),
            )


# ── FRONTEND_DESIGN_RUBRIC ──────────────────────────────────────


@pytest.mark.unit
class TestFrontendDesignRubric:
    def test_has_four_criteria(self) -> None:
        assert len(FRONTEND_DESIGN_RUBRIC.criteria) == 4

    def test_weights_sum_to_one(self) -> None:
        total = sum(c.weight for c in FRONTEND_DESIGN_RUBRIC.criteria)
        assert abs(total - 1.0) < 1e-9

    def test_criterion_names(self) -> None:
        names = {c.name for c in FRONTEND_DESIGN_RUBRIC.criteria}
        assert names == {"design", "originality", "craft", "functionality"}

    def test_rubric_name(self) -> None:
        assert FRONTEND_DESIGN_RUBRIC.name == "frontend-design"
