"""Tests for EventStreamController."""

from datetime import UTC, datetime
from typing import Any

import pytest
from litestar.testing import TestClient

from synthorg.communication.event_stream.interrupt import (
    Interrupt,
    InterruptStore,
    InterruptType,
)
from tests.unit.api.conftest import make_auth_headers

_WRITE_HEADERS = make_auth_headers("ceo")
_READ_HEADERS = make_auth_headers("observer")


@pytest.mark.unit
class TestEventStreamSSE:
    def test_stream_requires_session_id(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            "/api/v1/events/stream",
            headers=_READ_HEADERS,
        )
        # Missing required session_id query param -> 400
        assert resp.status_code == 400


@pytest.mark.unit
class TestEventStreamResume:
    async def test_resume_nonexistent_interrupt_404(
        self,
        test_client: TestClient[Any],
        interrupt_store: InterruptStore,
    ) -> None:
        resp = test_client.post(
            "/api/v1/events/resume/nonexistent",
            json={"decision": "approve"},
            headers=_WRITE_HEADERS,
        )
        assert resp.status_code == 404

    async def test_resume_existing_interrupt(
        self,
        test_client: TestClient[Any],
        interrupt_store: InterruptStore,
    ) -> None:
        interrupt = Interrupt(
            id="int-resume-001",
            type=InterruptType.TOOL_APPROVAL,
            session_id="s1",
            agent_id="agent-001",
            created_at=datetime(2026, 4, 13, tzinfo=UTC),
            timeout_seconds=300.0,
            tool_name="deploy",
        )
        await interrupt_store.create(interrupt)

        resp = test_client.post(
            "/api/v1/events/resume/int-resume-001",
            json={"decision": "approve"},
            headers=_WRITE_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "resumed"
