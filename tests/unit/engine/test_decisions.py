"""Unit tests for DecisionRecord model."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.core.enums import DecisionOutcome
from synthorg.engine.decisions import DecisionRecord


def _make_record(**overrides: object) -> DecisionRecord:
    """Build a DecisionRecord with sensible defaults."""
    defaults: dict[str, object] = {
        "id": "decision-001",
        "task_id": "task-1",
        "executing_agent_id": "alice",
        "reviewer_agent_id": "bob",
        "decision": DecisionOutcome.APPROVED,
        "recorded_at": datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
        "version": 1,
        "metadata": {},
    }
    defaults.update(overrides)
    return DecisionRecord(**defaults)


@pytest.mark.unit
class TestDecisionRecordConstruction:
    """Tests for DecisionRecord construction and validation."""

    def test_minimal_construction(self) -> None:
        """All required fields produce a valid record."""
        record = _make_record()
        assert record.id == "decision-001"
        assert record.task_id == "task-1"
        assert record.executing_agent_id == "alice"
        assert record.reviewer_agent_id == "bob"
        assert record.decision is DecisionOutcome.APPROVED
        assert record.version == 1
        assert record.metadata == {}

    def test_defaults(self) -> None:
        """Optional fields have expected defaults."""
        record = _make_record()
        assert record.approval_id is None
        assert record.reason is None
        assert record.criteria_snapshot == ()

    def test_frozen(self) -> None:
        """Attempting to mutate raises ValidationError."""
        record = _make_record()
        with pytest.raises(ValidationError):
            record.decision = DecisionOutcome.REJECTED  # type: ignore[misc]

    def test_metadata_deep_copied(self) -> None:
        """Mutating the source dict does not affect the record."""
        nested: dict[str, int] = {"a": 1}
        original: dict[str, object] = {"key": "value", "nested": nested}
        record = _make_record(metadata=original)
        original["key"] = "mutated"
        nested["a"] = 999
        assert record.metadata["key"] == "value"
        nested_copy = record.metadata["nested"]
        assert isinstance(nested_copy, dict)
        assert nested_copy["a"] == 1

    def test_metadata_required(self) -> None:
        """metadata is required -- omitting it raises ValidationError."""
        with pytest.raises(ValidationError, match="metadata"):
            DecisionRecord(
                id="decision-001",
                task_id="task-1",
                executing_agent_id="alice",
                reviewer_agent_id="bob",
                decision=DecisionOutcome.APPROVED,
                recorded_at=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
                version=1,
            )

    def test_version_must_be_at_least_one(self) -> None:
        """version < 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            _make_record(version=0)

    def test_empty_id_rejected(self) -> None:
        """Blank id raises ValidationError."""
        with pytest.raises(ValidationError):
            _make_record(id="")

    def test_empty_task_id_rejected(self) -> None:
        """Blank task_id raises ValidationError."""
        with pytest.raises(ValidationError):
            _make_record(task_id="")

    def test_empty_executing_agent_id_rejected(self) -> None:
        """Blank executing_agent_id raises ValidationError."""
        with pytest.raises(ValidationError):
            _make_record(executing_agent_id="")

    def test_empty_reviewer_agent_id_rejected(self) -> None:
        """Blank reviewer_agent_id raises ValidationError."""
        with pytest.raises(ValidationError):
            _make_record(reviewer_agent_id="")

    def test_all_fields_populated(self) -> None:
        """All optional fields can be set."""
        record = _make_record(
            approval_id="approval-42",
            reason="Code meets quality standards",
            criteria_snapshot=("JWT login", "Tests pass"),
            metadata={"context": "sprint-5"},
        )
        assert record.approval_id == "approval-42"
        assert record.reason == "Code meets quality standards"
        assert record.criteria_snapshot == ("JWT login", "Tests pass")
        assert record.metadata == {"context": "sprint-5"}

    def test_decision_rejected(self) -> None:
        """REJECTED decision is valid."""
        record = _make_record(decision=DecisionOutcome.REJECTED)
        assert record.decision is DecisionOutcome.REJECTED
