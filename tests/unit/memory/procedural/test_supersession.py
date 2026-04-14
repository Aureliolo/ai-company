"""Tests for supersession rule classification."""

import pytest
from pydantic import ValidationError

from synthorg.memory.procedural.models import ProceduralMemoryProposal
from synthorg.memory.procedural.supersession import (
    SupersessionResult,
    SupersessionVerdict,
    evaluate_supersession,
)


def _make_proposal(**overrides: object) -> ProceduralMemoryProposal:
    defaults: dict[str, object] = {
        "discovery": "Discovery text for retrieval ranking",
        "condition": "When a task fails due to timeout errors",
        "action": "Increase timeout and add retry logic",
        "rationale": "Timeouts cause cascading failures",
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return ProceduralMemoryProposal(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestSupersessionVerdict:
    def test_all_values(self) -> None:
        values = {v.value for v in SupersessionVerdict}
        assert values == {"full", "partial", "conflict"}


@pytest.mark.unit
class TestSupersessionResult:
    def test_construction(self) -> None:
        r = SupersessionResult(
            verdict=SupersessionVerdict.FULL,
            candidate_id="new-1",
            existing_id="old-1",
            reason="Broader condition with higher confidence",
        )
        assert r.verdict == SupersessionVerdict.FULL
        assert r.candidate_id == "new-1"

    def test_frozen(self) -> None:
        r = SupersessionResult(
            verdict=SupersessionVerdict.PARTIAL,
            candidate_id="c",
            existing_id="e",
            reason="Overlap",
        )
        with pytest.raises(ValidationError):
            r.verdict = SupersessionVerdict.FULL  # type: ignore[misc]


@pytest.mark.unit
class TestEvaluateSupersession:
    def test_full_supersession(self) -> None:
        """Candidate has broader condition + higher confidence."""
        existing = _make_proposal(
            condition="When timeout errors occur",
            confidence=0.7,
        )
        candidate = _make_proposal(
            condition=(
                "When timeout errors occur during API calls or database queries"
            ),
            confidence=0.9,
        )
        result = evaluate_supersession(
            candidate=candidate,
            existing=existing,
            candidate_id="new-1",
            existing_id="old-1",
        )
        assert result.verdict == SupersessionVerdict.FULL

    def test_partial_overlap(self) -> None:
        """Conditions overlap but neither is a superset."""
        existing = _make_proposal(
            condition="When database connections fail due to timeouts",
        )
        candidate = _make_proposal(
            condition="When database connections fail intermittently under load",
        )
        result = evaluate_supersession(
            candidate=candidate,
            existing=existing,
            candidate_id="new-1",
            existing_id="old-1",
        )
        assert result.verdict == SupersessionVerdict.PARTIAL

    def test_conflict_same_condition_different_action(self) -> None:
        """Same condition but contradictory actions."""
        existing = _make_proposal(
            condition="When memory usage exceeds threshold",
            action="Restart the service immediately",
        )
        candidate = _make_proposal(
            condition="When memory usage exceeds threshold",
            action="Scale horizontally by adding instances",
        )
        result = evaluate_supersession(
            candidate=candidate,
            existing=existing,
            candidate_id="new-1",
            existing_id="old-1",
        )
        assert result.verdict == SupersessionVerdict.CONFLICT

    def test_equal_confidence_not_full(self) -> None:
        """Equal confidence should not produce FULL supersession."""
        existing = _make_proposal(
            condition="When timeout errors occur",
            confidence=0.8,
        )
        candidate = _make_proposal(
            condition=("When timeout errors occur in all components"),
            confidence=0.8,
        )
        result = evaluate_supersession(
            candidate=candidate,
            existing=existing,
            candidate_id="new-1",
            existing_id="old-1",
        )
        assert result.verdict != SupersessionVerdict.FULL

    def test_disjoint_conditions(self) -> None:
        """Completely different conditions -> PARTIAL."""
        existing = _make_proposal(
            condition="When authentication tokens expire",
        )
        candidate = _make_proposal(
            condition="When disk space runs low on production",
        )
        result = evaluate_supersession(
            candidate=candidate,
            existing=existing,
            candidate_id="new-1",
            existing_id="old-1",
        )
        assert result.verdict == SupersessionVerdict.PARTIAL

    def test_result_ids_correct(self) -> None:
        existing = _make_proposal()
        candidate = _make_proposal()
        result = evaluate_supersession(
            candidate=candidate,
            existing=existing,
            candidate_id="c-1",
            existing_id="e-1",
        )
        assert result.candidate_id == "c-1"
        assert result.existing_id == "e-1"

    def test_reason_is_not_blank(self) -> None:
        existing = _make_proposal()
        candidate = _make_proposal()
        result = evaluate_supersession(
            candidate=candidate,
            existing=existing,
            candidate_id="c",
            existing_id="e",
        )
        assert len(result.reason) > 0
