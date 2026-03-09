"""Tests for approvals controller."""

from typing import Any

import pytest
from litestar.testing import TestClient  # noqa: TC002


@pytest.mark.unit
class TestApprovalsController:
    def test_list_approvals_stub(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/approvals")
        assert resp.status_code == 501
        body = resp.json()
        assert body["success"] is False
        assert "not implemented" in body["error"].lower()
