"""Unit tests for settings API controller."""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """CEO-role auth headers."""
    return make_auth_headers("ceo")


@pytest.fixture
def observer_headers() -> dict[str, str]:
    """Observer-role auth headers."""
    return make_auth_headers("observer")


@pytest.mark.unit
class TestSettingsController:
    """Tests for settings REST endpoints."""

    def test_list_all_settings(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.get("/api/v1/settings", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        assert len(body["data"]) > 0

    def test_get_namespace_settings(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.get("/api/v1/settings/budget", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        for entry in body["data"]:
            assert entry["definition"]["namespace"] == "budget"

    def test_get_single_setting(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.get(
            "/api/v1/settings/budget/total_monthly",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["definition"]["key"] == "total_monthly"

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/v1/settings/budget/nonexistent",
            "/api/v1/settings/nonexistent_ns",
            "/api/v1/settings/_schema/nonexistent_ns",
        ],
    )
    def test_unknown_resource_returns_404(
        self,
        test_client: TestClient[Any],
        auth_headers: dict[str, str],
        endpoint: str,
    ) -> None:
        resp = test_client.get(endpoint, headers=auth_headers)
        assert resp.status_code == 404

    def test_update_setting(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.put(
            "/api/v1/settings/budget/total_monthly",
            json={"value": "200.0"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["value"] == "200.0"
        assert body["data"]["source"] == "db"

    def test_update_validates_value(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.put(
            "/api/v1/settings/budget/total_monthly",
            json={"value": "not-a-number"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_update_unknown_setting_returns_404(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.put(
            "/api/v1/settings/budget/nonexistent",
            json={"value": "100"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_delete_setting(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        test_client.put(
            "/api/v1/settings/budget/total_monthly",
            json={"value": "200.0"},
            headers=auth_headers,
        )
        resp = test_client.delete(
            "/api/v1/settings/budget/total_monthly",
            headers=auth_headers,
        )
        assert resp.status_code == 204
        assert resp.content == b""

    def test_delete_unknown_setting_returns_404(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.delete(
            "/api/v1/settings/budget/nonexistent",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_get_full_schema(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.get(
            "/api/v1/settings/_schema",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) > 0

    def test_get_namespace_schema(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        resp = test_client.get(
            "/api/v1/settings/_schema/budget",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        for defn in body["data"]:
            assert defn["namespace"] == "budget"

    def test_observer_can_read(
        self, test_client: TestClient[Any], observer_headers: dict[str, str]
    ) -> None:
        resp = test_client.get(
            "/api/v1/settings",
            headers=observer_headers,
        )
        assert resp.status_code == 200

    def test_observer_cannot_write(
        self, test_client: TestClient[Any], observer_headers: dict[str, str]
    ) -> None:
        resp = test_client.put(
            "/api/v1/settings/budget/total_monthly",
            json={"value": "200.0"},
            headers=observer_headers,
        )
        assert resp.status_code == 403

    def test_observer_cannot_delete(
        self, test_client: TestClient[Any], observer_headers: dict[str, str]
    ) -> None:
        resp = test_client.delete(
            "/api/v1/settings/budget/total_monthly",
            headers=observer_headers,
        )
        assert resp.status_code == 403

    def test_oversized_namespace_rejected(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        long_ns = "x" * 65
        resp = test_client.get(
            f"/api/v1/settings/{long_ns}",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_oversized_key_rejected(
        self, test_client: TestClient[Any], auth_headers: dict[str, str]
    ) -> None:
        long_key = "x" * 129
        resp = test_client.get(
            f"/api/v1/settings/budget/{long_key}",
            headers=auth_headers,
        )
        assert resp.status_code == 400
