"""Tests for artifact controller."""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
class TestArtifactController:
    def test_list_artifacts_empty(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/artifacts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    def test_get_artifact_stub(self, test_client: TestClient[Any]) -> None:
        resp = test_client.get("/api/v1/artifacts/any-id")
        assert resp.status_code == 501
        body = resp.json()
        assert body["success"] is False
        assert "not implemented" in body["error"].lower()

    def test_oversized_artifact_id_rejected(self, test_client: TestClient[Any]) -> None:
        long_id = "x" * 129
        resp = test_client.get(
            f"/api/v1/artifacts/{long_id}",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 400
