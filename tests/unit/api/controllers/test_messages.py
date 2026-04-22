"""Tests for message controller."""

from typing import Any

import pytest
from litestar.testing import TestClient


@pytest.mark.unit
class TestMessageController:
    def test_list_messages_no_channel(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_list_channels(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/messages/channels")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        # Paginated envelope: ``pagination`` is always present and the
        # consistency validator keeps ``has_more`` and ``next_cursor``
        # in lockstep (empty bus -> both falsy).
        assert "pagination" in body
        assert body["pagination"]["has_more"] is False
        assert body["pagination"]["next_cursor"] is None
