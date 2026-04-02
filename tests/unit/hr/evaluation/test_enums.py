"""Tests for evaluation framework enumerations."""

import pytest

from synthorg.hr.evaluation.enums import EvaluationPillar


class TestEvaluationPillar:
    """EvaluationPillar enum tests."""

    def test_has_five_members(self) -> None:
        assert len(EvaluationPillar) == 5

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (EvaluationPillar.INTELLIGENCE, "intelligence"),
            (EvaluationPillar.EFFICIENCY, "efficiency"),
            (EvaluationPillar.RESILIENCE, "resilience"),
            (EvaluationPillar.GOVERNANCE, "governance"),
            (EvaluationPillar.EXPERIENCE, "experience"),
        ],
    )
    def test_member_values(
        self,
        member: EvaluationPillar,
        value: str,
    ) -> None:
        assert member.value == value

    def test_is_strenum(self) -> None:
        assert isinstance(EvaluationPillar.INTELLIGENCE, str)

    def test_lookup_by_value(self) -> None:
        assert EvaluationPillar("intelligence") is EvaluationPillar.INTELLIGENCE

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError, match="not_a_pillar"):
            EvaluationPillar("not_a_pillar")
