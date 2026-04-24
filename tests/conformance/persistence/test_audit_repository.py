"""Parametrized conformance tests for ``AuditRepository``.

These run against both SQLite and Postgres via the ``backend`` fixture
so SQLite-vs-Postgres divergence is caught on every commit. The tests
assert the contract of the shared helpers in
``synthorg.persistence._shared.audit`` -- serialisation round-trip,
duplicate-id classification, and UTC timestamp normalisation.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from synthorg.core.enums import ApprovalRiskLevel, ToolCategory
from synthorg.persistence.errors import DuplicateRecordError
from synthorg.persistence.protocol import PersistenceBackend
from synthorg.security.models import AuditEntry


def _entry(
    *,
    entry_id: str | None = None,
    matched_rules: tuple[str, ...] = (),
    timestamp: datetime | None = None,
    agent_id: str | None = "agent-x",
) -> AuditEntry:
    return AuditEntry(
        id=entry_id or str(uuid4()),
        timestamp=timestamp or datetime(2026, 4, 24, 12, 0, tzinfo=UTC),
        agent_id=agent_id,
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


@pytest.mark.integration
class TestAuditRepositoryConformance:
    async def test_save_and_query_round_trip(
        self,
        backend: PersistenceBackend,
    ) -> None:
        entry = _entry(matched_rules=("rule-a", "rule-b"))
        await backend.audit_entries.save(entry)

        results = await backend.audit_entries.query()

        assert len(results) == 1
        loaded = results[0]
        assert loaded.id == entry.id
        assert loaded.matched_rules == entry.matched_rules
        assert loaded.timestamp == entry.timestamp

    async def test_duplicate_id_raises_duplicate_record_error(
        self,
        backend: PersistenceBackend,
    ) -> None:
        entry = _entry()
        await backend.audit_entries.save(entry)

        # Same id again. Repos are append-only; save must reject.
        with pytest.raises(DuplicateRecordError):
            await backend.audit_entries.save(entry)

    async def test_non_utc_timestamp_normalised_on_round_trip(
        self,
        backend: PersistenceBackend,
    ) -> None:
        offset_tz = timezone(timedelta(hours=5))
        entry = _entry(
            timestamp=datetime(2026, 4, 24, 17, 0, tzinfo=offset_tz),
        )
        await backend.audit_entries.save(entry)

        results = await backend.audit_entries.query()

        assert len(results) == 1
        # After UTC normalisation the instant is preserved but tzinfo is UTC.
        expected = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
        assert results[0].timestamp == expected
        assert results[0].timestamp.tzinfo == UTC

    async def test_matched_rules_order_preserved(
        self,
        backend: PersistenceBackend,
    ) -> None:
        rules = ("rule-one", "rule-two", "rule-three")
        entry = _entry(matched_rules=rules)
        await backend.audit_entries.save(entry)
        results = await backend.audit_entries.query()
        assert results[0].matched_rules == rules

    async def test_query_filter_by_agent_id(
        self,
        backend: PersistenceBackend,
    ) -> None:
        a = _entry(agent_id="alice")
        b = _entry(agent_id="bob")
        await backend.audit_entries.save(a)
        await backend.audit_entries.save(b)

        only_alice = await backend.audit_entries.query(agent_id="alice")
        assert {r.id for r in only_alice} == {a.id}

    async def test_query_limit_respected(
        self,
        backend: PersistenceBackend,
    ) -> None:
        for i in range(5):
            await backend.audit_entries.save(
                _entry(
                    timestamp=datetime(2026, 4, 24, 12, i, tzinfo=UTC),
                ),
            )
        limited = await backend.audit_entries.query(limit=3)
        assert len(limited) == 3
