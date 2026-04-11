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

    @pytest.mark.parametrize(
        "path",
        ["source", "metadata.actor", "a.b.c.d.e"],
        ids=["simple", "nested", "max-depth"],
    )
    def test_valid_paths(self, path: str) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        validate_jsonb_path(path)

    @pytest.mark.parametrize(
        ("path", "match"),
        [
            ("'; DROP TABLE audit_entries; --", "Invalid JSONB path"),
            ('key"value', "Invalid JSONB path"),
            ("a.b.c.d.e.f", "Invalid JSONB path"),
            (".leading", "Invalid JSONB path"),
            ("key with spaces", "Invalid JSONB path"),
        ],
        ids=["sql-injection", "quotes", "too-deep", "leading-dot", "spaces"],
    )
    def test_rejects_invalid_paths(self, path: str, match: str) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match=match):
            validate_jsonb_path(path)

    def test_rejects_empty(self) -> None:
        from synthorg.persistence.jsonb_capability import validate_jsonb_path

        with pytest.raises(ValueError, match="must be 1-128"):
            validate_jsonb_path("")
