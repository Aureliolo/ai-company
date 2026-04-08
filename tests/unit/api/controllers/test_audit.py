"""Tests for audit log query controller."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.core.enums import ApprovalRiskLevel, ToolCategory
from synthorg.security.audit import AuditLog
from synthorg.security.models import AuditEntry, AuditVerdictStr
from tests.unit.api.conftest import make_auth_headers

_HEADERS = make_auth_headers("ceo")
_DUMMY_HASH = "a" * 64


def _make_entry(  # noqa: PLR0913
    *,
    entry_id: str = "e-1",
    agent_id: str | None = "agent-a",
    tool_name: str = "code_write",
    action_type: str = "code:write",
    verdict: AuditVerdictStr = "allow",
    timestamp: datetime | None = None,
) -> AuditEntry:
    return AuditEntry(
        id=entry_id,
        timestamp=timestamp or datetime(2026, 4, 1, tzinfo=UTC),
        agent_id=agent_id,
        tool_name=tool_name,
        tool_category=ToolCategory.CODE_EXECUTION,
        action_type=action_type,
        arguments_hash=_DUMMY_HASH,
        verdict=verdict,
        risk_level=ApprovalRiskLevel.LOW,
        reason="test-reason",
        evaluation_duration_ms=1.0,
    )


@pytest.mark.unit
class TestAuditController:
    def test_empty_audit_log(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/security/audit",
            headers=_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    def test_returns_entries_paginated(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        for i in range(3):
            audit_log.record(_make_entry(entry_id=f"e-{i}"))
        resp = test_client.get(
            "/api/v1/security/audit",
            headers=_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 3
        assert len(body["data"]) == 3

    def test_filter_by_agent_id(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        audit_log.record(_make_entry(entry_id="e-1", agent_id="alice"))
        audit_log.record(_make_entry(entry_id="e-2", agent_id="bob"))
        resp = test_client.get(
            "/api/v1/security/audit",
            params={"agent_id": "alice"},
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["agent_id"] == "alice"

    def test_filter_by_verdict(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        audit_log.record(_make_entry(entry_id="e-1", verdict="allow"))
        audit_log.record(_make_entry(entry_id="e-2", verdict="deny"))
        resp = test_client.get(
            "/api/v1/security/audit",
            params={"verdict": "deny"},
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["verdict"] == "deny"

    def test_filter_by_action_type(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        audit_log.record(
            _make_entry(entry_id="e-1", action_type="code:write"),
        )
        audit_log.record(
            _make_entry(entry_id="e-2", action_type="deploy:production"),
        )
        resp = test_client.get(
            "/api/v1/security/audit",
            params={"action_type": "deploy:production"},
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["action_type"] == "deploy:production"

    def test_filter_by_tool_name(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        audit_log.record(
            _make_entry(entry_id="e-1", tool_name="code_write"),
        )
        audit_log.record(
            _make_entry(entry_id="e-2", tool_name="file_read"),
        )
        resp = test_client.get(
            "/api/v1/security/audit",
            params={"tool_name": "file_read"},
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["pagination"]["total"] == 1

    def test_filter_by_since_until(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        t1 = datetime(2026, 4, 1, tzinfo=UTC)
        t2 = t1 + timedelta(hours=1)
        t3 = t1 + timedelta(hours=2)
        audit_log.record(_make_entry(entry_id="e-1", timestamp=t1))
        audit_log.record(_make_entry(entry_id="e-2", timestamp=t2))
        audit_log.record(_make_entry(entry_id="e-3", timestamp=t3))
        resp = test_client.get(
            "/api/v1/security/audit",
            params={
                "since": t1.isoformat(),
                "until": t2.isoformat(),
            },
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["pagination"]["total"] == 2

    def test_pagination_offset_limit(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        for i in range(5):
            audit_log.record(_make_entry(entry_id=f"e-{i}"))
        resp = test_client.get(
            "/api/v1/security/audit",
            params={"offset": 2, "limit": 2},
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["pagination"]["total"] == 5
        assert body["pagination"]["offset"] == 2
        assert body["pagination"]["limit"] == 2
        assert len(body["data"]) == 2

    def test_rejects_inverted_time_window(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """since > until returns 400."""
        t1 = datetime(2026, 4, 1, tzinfo=UTC)
        t2 = t1 - timedelta(hours=1)
        resp = test_client.get(
            "/api/v1/security/audit",
            params={"since": t1.isoformat(), "until": t2.isoformat()},
            headers=_HEADERS,
        )
        assert resp.status_code == 400

    def test_combined_filters_and(
        self,
        test_client: TestClient[Any],
        audit_log: AuditLog,
    ) -> None:
        """Multiple filters are AND-combined."""
        audit_log.record(
            _make_entry(
                entry_id="e-1",
                agent_id="alice",
                verdict="allow",
            ),
        )
        audit_log.record(
            _make_entry(
                entry_id="e-2",
                agent_id="alice",
                verdict="deny",
            ),
        )
        audit_log.record(
            _make_entry(
                entry_id="e-3",
                agent_id="bob",
                verdict="allow",
            ),
        )
        resp = test_client.get(
            "/api/v1/security/audit",
            params={"agent_id": "alice", "verdict": "deny"},
            headers=_HEADERS,
        )
        body = resp.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["id"] == "e-2"
