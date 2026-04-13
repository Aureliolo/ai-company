"""Tests for ProceduralMemoryScope enum and extended proposal fields."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.memory.procedural.models import (
    ProceduralMemoryProposal,
    ProceduralMemoryScope,
)


@pytest.mark.unit
class TestProceduralMemoryScope:
    def test_all_values(self) -> None:
        values = {s.value for s in ProceduralMemoryScope}
        assert values == {"agent", "role", "department", "org"}

    def test_agent_is_default(self) -> None:
        assert ProceduralMemoryScope.AGENT.value == "agent"

    def test_org_value(self) -> None:
        assert ProceduralMemoryScope.ORG.value == "org"


def _make_proposal(**overrides: object) -> ProceduralMemoryProposal:
    defaults: dict[str, object] = {
        "discovery": "Short discovery text for retrieval",
        "condition": "When a task fails due to timeout",
        "action": "Increase the timeout and add retry logic",
        "rationale": "Timeouts cause cascading failures",
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return ProceduralMemoryProposal(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestProposalScopeField:
    def test_default_scope_is_agent(self) -> None:
        p = _make_proposal()
        assert p.scope == ProceduralMemoryScope.AGENT

    def test_explicit_org_scope(self) -> None:
        p = _make_proposal(scope=ProceduralMemoryScope.ORG)
        assert p.scope == ProceduralMemoryScope.ORG

    def test_scope_from_string(self) -> None:
        p = _make_proposal(scope="department")
        assert p.scope == ProceduralMemoryScope.DEPARTMENT


@pytest.mark.unit
class TestProposalSupersessionFields:
    def test_default_supersedes_empty(self) -> None:
        p = _make_proposal()
        assert p.supersedes == ()

    def test_default_superseded_by_none(self) -> None:
        p = _make_proposal()
        assert p.superseded_by is None

    def test_with_supersedes(self) -> None:
        p = _make_proposal(supersedes=("old-1", "old-2"))
        assert p.supersedes == ("old-1", "old-2")

    def test_with_superseded_by(self) -> None:
        p = _make_proposal(superseded_by="newer-1")
        assert p.superseded_by == "newer-1"

    def test_self_referential_rejected(self) -> None:
        """Cannot both supersede and be superseded by same ID."""
        with pytest.raises(ValidationError, match="Cannot both supersede"):
            _make_proposal(
                supersedes=("entry-1",),
                superseded_by="entry-1",
            )

    def test_disjoint_supersession_allowed(self) -> None:
        p = _make_proposal(
            supersedes=("old-1",),
            superseded_by="newer-1",
        )
        assert p.supersedes == ("old-1",)
        assert p.superseded_by == "newer-1"


@pytest.mark.unit
class TestProposalApplicationFields:
    def test_default_application_count_zero(self) -> None:
        p = _make_proposal()
        assert p.application_count == 0

    def test_default_last_applied_at_none(self) -> None:
        p = _make_proposal()
        assert p.last_applied_at is None

    def test_with_application_count(self) -> None:
        p = _make_proposal(application_count=5)
        assert p.application_count == 5

    def test_negative_application_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_proposal(application_count=-1)

    def test_with_last_applied_at(self) -> None:
        ts = datetime(2026, 4, 14, tzinfo=UTC)
        p = _make_proposal(last_applied_at=ts)
        assert p.last_applied_at == ts


@pytest.mark.unit
class TestProposalBackwardCompatibility:
    def test_existing_fields_still_work(self) -> None:
        """Ensure old-style proposal without new fields still works."""
        p = ProceduralMemoryProposal(
            discovery="Discovery text for retrieval",
            condition="When X happens",
            action="Do Y",
            rationale="Because Z",
            confidence=0.7,
            tags=("retry", "timeout"),
        )
        assert p.confidence == 0.7
        assert p.tags == ("retry", "timeout")
        # New fields have defaults
        assert p.scope == ProceduralMemoryScope.AGENT
        assert p.supersedes == ()
        assert p.superseded_by is None
        assert p.application_count == 0
        assert p.last_applied_at is None
