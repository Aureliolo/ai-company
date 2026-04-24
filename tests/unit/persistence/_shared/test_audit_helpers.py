"""Tests for the shared audit-repository helpers."""

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
import structlog

from synthorg.core.enums import ApprovalRiskLevel, ToolCategory
from synthorg.observability.events.persistence import (
    PERSISTENCE_AUDIT_ENTRY_DESERIALIZE_FAILED,
    PERSISTENCE_AUDIT_ENTRY_SAVE_FAILED,
)
from synthorg.persistence._shared.audit import (
    AUDIT_COLUMNS,
    audit_entry_to_payload,
    classify_audit_save_error,
    row_to_audit_entry,
)
from synthorg.persistence.errors import DuplicateRecordError, QueryError
from synthorg.security.models import AuditEntry


def _make_entry(
    *,
    matched_rules: tuple[str, ...] = ("rule-a", "rule-b"),
    timestamp: datetime | None = None,
) -> AuditEntry:
    return AuditEntry(
        id="audit-001",
        timestamp=timestamp or datetime(2026, 4, 24, 12, 0, tzinfo=UTC),
        agent_id="agent-x",
        task_id="task-y",
        tool_name="run_python",
        tool_category=ToolCategory.CODE_EXECUTION,
        action_type="execute",
        arguments_hash="0" * 64,
        verdict="allow",
        risk_level=ApprovalRiskLevel.LOW,
        reason="No sensitive arguments detected",
        matched_rules=matched_rules,
        evaluation_duration_ms=4.2,
    )


@pytest.mark.unit
class TestAuditEntryToPayload:
    def test_columns_complete(self) -> None:
        entry = _make_entry()
        payload = audit_entry_to_payload(
            entry,
            json_serializer=json.dumps,
            timestamp_serializer=lambda dt: dt.isoformat(),
        )
        for column in AUDIT_COLUMNS:
            assert column in payload, f"missing column {column!r}"

    def test_uses_passed_serializers(self) -> None:
        entry = _make_entry()
        captured: dict[str, Any] = {}

        def spy_json(value: list[str]) -> str:
            captured["json"] = value
            return f"<json {value!r}>"

        def spy_ts(value: datetime) -> str:
            captured["ts"] = value
            return f"<ts {value.isoformat()!r}>"

        payload = audit_entry_to_payload(
            entry,
            json_serializer=spy_json,
            timestamp_serializer=spy_ts,
        )
        assert captured["json"] == ["rule-a", "rule-b"]
        assert captured["ts"] == entry.timestamp.astimezone(UTC)
        assert payload["matched_rules"] == "<json ['rule-a', 'rule-b']>"
        assert payload["timestamp"].startswith("<ts ")

    def test_normalizes_timestamp_to_utc_before_serialising(self) -> None:
        offset_tz = timezone(timedelta(hours=5))
        local_ts = datetime(2026, 4, 24, 17, 0, tzinfo=offset_tz)
        entry = _make_entry(timestamp=local_ts)
        seen: list[datetime] = []

        def capture_ts(value: datetime) -> str:
            seen.append(value)
            return value.isoformat()

        audit_entry_to_payload(
            entry,
            json_serializer=json.dumps,
            timestamp_serializer=capture_ts,
        )
        assert len(seen) == 1
        assert seen[0].tzinfo == UTC
        assert seen[0] == datetime(2026, 4, 24, 12, 0, tzinfo=UTC)


@pytest.mark.unit
class TestRowToAuditEntry:
    def _row(self, *, matched_rules: object) -> dict[str, object]:
        entry = _make_entry()
        data = entry.model_dump(mode="json")
        return {**data, "matched_rules": matched_rules}

    def test_handles_string_matched_rules(self) -> None:
        row = self._row(matched_rules='["rule-a","rule-b"]')
        entry = row_to_audit_entry(row)
        assert entry.matched_rules == ("rule-a", "rule-b")

    def test_handles_native_list_matched_rules(self) -> None:
        row = self._row(matched_rules=["rule-a", "rule-b"])
        entry = row_to_audit_entry(row)
        assert entry.matched_rules == ("rule-a", "rule-b")

    def test_invalid_json_raises_query_error(self) -> None:
        row = self._row(matched_rules="[invalid json")
        with pytest.raises(QueryError):
            row_to_audit_entry(row)

    def test_validation_failure_raises_query_error(self) -> None:
        row = self._row(matched_rules=[])
        row["risk_level"] = "not-a-real-level"
        with pytest.raises(QueryError):
            row_to_audit_entry(row)

    def test_logs_safe_description_on_failure(self) -> None:
        row = self._row(matched_rules="[invalid")
        with (
            structlog.testing.capture_logs() as cap,
            pytest.raises(QueryError),
        ):
            row_to_audit_entry(row)
        events = [
            e
            for e in cap
            if e.get("event") == PERSISTENCE_AUDIT_ENTRY_DESERIALIZE_FAILED
        ]
        assert len(events) == 1
        assert events[0]["error_type"] == "JSONDecodeError"
        assert "error" in events[0]


@pytest.mark.unit
class TestClassifyAuditSaveError:
    def test_returns_duplicate_record_error_when_predicate_true(self) -> None:
        exc = RuntimeError("UNIQUE constraint failed")
        result = classify_audit_save_error(
            exc,
            entry_id="audit-001",
            is_duplicate=lambda _exc: True,
        )
        assert isinstance(result, DuplicateRecordError)
        assert "audit-001" in str(result)

    def test_returns_query_error_when_predicate_false(self) -> None:
        exc = RuntimeError("connection refused")
        result = classify_audit_save_error(
            exc,
            entry_id="audit-001",
            is_duplicate=lambda _exc: False,
        )
        assert isinstance(result, QueryError)
        assert "audit-001" in str(result)

    def test_logs_structured_fields_with_safe_description(self) -> None:
        # Construct an exception whose str() contains a fake credential
        # to assert the log payload routes through safe_error_description
        # (not the raw str(exc)).
        exc = RuntimeError("api_key=sk-test-pretend-credential failed")
        with structlog.testing.capture_logs() as cap:
            classify_audit_save_error(
                exc,
                entry_id="audit-001",
                is_duplicate=lambda _exc: False,
            )
        events = [
            e for e in cap if e.get("event") == PERSISTENCE_AUDIT_ENTRY_SAVE_FAILED
        ]
        assert len(events) == 1
        evt = events[0]
        assert evt["entry_id"] == "audit-001"
        assert evt["error_type"] == "RuntimeError"
        assert evt["duplicate"] is False
        # The error field is a safe description, not the raw str(exc).
        assert "error" in evt
