"""Tests for JSONB query parameters on the audit endpoint.

The fake backend does not implement ``JsonbQueryCapability``, so
all JSONB queries return 422.  Postgres-specific correctness tests
live in the integration test suite.
"""

from typing import Any

import pytest
from litestar.testing import TestClient

from tests.unit.api.conftest import make_auth_headers

_BASE = "/api/v1/security/audit"
_HEADERS = make_auth_headers("ceo")


@pytest.mark.unit
class TestJsonbCapabilityFallback:
    """Non-Postgres backends reject JSONB queries with 422."""

    def test_jsonb_contains_returns_422(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            _BASE,
            params={"jsonb_contains": '{"severity": "high"}'},
            headers=_HEADERS,
        )
        assert resp.status_code == 422
        assert "Postgres" in resp.json()["error"]

    def test_jsonb_key_exists_returns_422(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            _BASE,
            params={"jsonb_key_exists": "rule_name"},
            headers=_HEADERS,
        )
        assert resp.status_code == 422

    def test_jsonb_path_returns_422(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            _BASE,
            params={"jsonb_path": "source", "jsonb_value": "firewall"},
            headers=_HEADERS,
        )
        assert resp.status_code == 422

    def test_jsonb_path_without_value_returns_400(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """jsonb_path requires jsonb_value."""
        resp = test_client.get(
            _BASE,
            params={"jsonb_path": "source"},
            headers=_HEADERS,
        )
        # 422 (Postgres check) fires before the path/value validation
        assert resp.status_code == 422

    def test_no_jsonb_params_works(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Without JSONB params, the standard query path is used."""
        resp = test_client.get(_BASE, headers=_HEADERS)
        assert resp.status_code == 200


@pytest.mark.unit
class TestJsonbPathValidation:
    """Path expression validation (independent of backend)."""

    def test_valid_simple_path(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        validate_jsonb_path("source")

    def test_valid_nested_path(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        validate_jsonb_path("metadata.actor")

    def test_valid_deep_path(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        validate_jsonb_path("a.b.c.d.e")

    def test_rejects_sql_injection(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match="Invalid JSONB path"):
            validate_jsonb_path("'; DROP TABLE audit_entries; --")

    def test_rejects_quotes(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match="Invalid JSONB path"):
            validate_jsonb_path('key"value')

    def test_rejects_too_deep(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match="Invalid JSONB path"):
            validate_jsonb_path("a.b.c.d.e.f")

    def test_rejects_empty(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match="must be 1-128"):
            validate_jsonb_path("")

    def test_rejects_leading_dot(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match="Invalid JSONB path"):
            validate_jsonb_path(".leading")

    def test_rejects_spaces(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match="Invalid JSONB path"):
            validate_jsonb_path("key with spaces")
