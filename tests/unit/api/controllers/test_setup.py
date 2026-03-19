"""Tests for the first-run setup controller."""

from typing import Any

import pytest
from litestar.testing import TestClient
from pydantic import ValidationError

from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupStatus:
    """GET /api/v1/setup/status -- unauthenticated status check."""

    def test_returns_status_with_seeded_users(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """With pre-seeded users, needs_admin is False."""
        resp = test_client.get("/api/v1/setup/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["needs_admin"] is False
        assert data["needs_setup"] is True
        assert data["has_providers"] is False

    def test_status_without_auth_header(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Status endpoint works without authentication."""
        saved_headers = dict(test_client.headers)
        test_client.headers.pop("Authorization", None)
        try:
            resp = test_client.get("/api/v1/setup/status")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
        finally:
            test_client.headers.update(saved_headers)

    def test_status_response_fields(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Status response contains all required fields."""
        resp = test_client.get("/api/v1/setup/status")
        data = resp.json()["data"]
        assert "needs_admin" in data
        assert "needs_setup" in data
        assert "has_providers" in data
        assert isinstance(data["needs_admin"], bool)
        assert isinstance(data["needs_setup"], bool)
        assert isinstance(data["has_providers"], bool)


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupTemplates:
    """GET /api/v1/setup/templates -- list available templates."""

    def test_returns_builtin_templates(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get("/api/v1/setup/templates")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        templates = body["data"]
        assert len(templates) >= 7
        names = {t["name"] for t in templates}
        assert "solo_founder" in names
        assert "startup" in names

    def test_template_fields(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get("/api/v1/setup/templates")
        body = resp.json()
        for template in body["data"]:
            assert "name" in template
            assert "display_name" in template
            assert "description" in template
            assert "source" in template

    def test_requires_auth(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.get("/api/v1/setup/templates")
        assert resp.status_code == 200


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupCompany:
    """POST /api/v1/setup/company -- create company config."""

    def test_blank_company(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/setup/company",
            json={"company_name": "Test Corp"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["company_name"] == "Test Corp"
        assert data["template_applied"] is None
        assert data["department_count"] == 0

    def test_company_with_template(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/setup/company",
            json={
                "company_name": "My Startup",
                "template_name": "solo_founder",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["company_name"] == "My Startup"
        assert data["template_applied"] == "solo_founder"
        assert data["department_count"] >= 1

    def test_invalid_template(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/setup/company",
            json={
                "company_name": "Test Corp",
                "template_name": "nonexistent_template",
            },
        )
        assert resp.status_code == 404

    def test_blank_company_name_rejected(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/setup/company",
            json={"company_name": "   "},
        )
        # Pydantic NotBlankStr validation returns 400
        assert resp.status_code == 400

    def test_requires_write_access(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.post(
            "/api/v1/setup/company",
            json={"company_name": "Test Corp"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupAgent:
    """POST /api/v1/setup/agent -- create first agent."""

    def test_nonexistent_provider(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/setup/agent",
            json={
                "name": "Alice Chen",
                "role": "CEO",
                "model_provider": "nonexistent",
                "model_id": "model-001",
            },
        )
        assert resp.status_code == 404

    def test_invalid_personality_preset(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            "/api/v1/setup/agent",
            json={
                "name": "Alice Chen",
                "role": "CEO",
                "personality_preset": "nonexistent_preset",
                "model_provider": "test",
                "model_id": "model-001",
            },
        )
        # Pydantic model_validator returns 400
        assert resp.status_code == 400

    def test_requires_write_access(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.post(
            "/api/v1/setup/agent",
            json={
                "name": "Alice Chen",
                "role": "CEO",
                "model_provider": "test",
                "model_id": "model-001",
            },
        )
        assert resp.status_code == 403


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupComplete:
    """POST /api/v1/setup/complete -- mark setup as done."""

    def test_complete_without_provider_fails(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Completing setup without providers returns 400."""
        resp = test_client.post("/api/v1/setup/complete")
        assert resp.status_code == 422

    def test_requires_write_access(
        self,
        test_client: TestClient[Any],
    ) -> None:
        test_client.headers.update(make_auth_headers("observer"))
        resp = test_client.post("/api/v1/setup/complete")
        assert resp.status_code == 403


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupDTOs:
    """Unit tests for setup DTO validation."""

    def test_setup_agent_request_valid_preset(self) -> None:
        from synthorg.api.controllers.setup import SetupAgentRequest

        req = SetupAgentRequest(
            name="Alice",
            role="CEO",
            personality_preset="visionary_leader",
            model_provider="test-provider",
            model_id="model-001",
        )
        assert req.personality_preset == "visionary_leader"

    def test_setup_agent_request_invalid_preset(self) -> None:
        from pydantic import ValidationError

        from synthorg.api.controllers.setup import SetupAgentRequest

        with pytest.raises(ValidationError, match="personality preset"):
            SetupAgentRequest(
                name="Alice",
                role="CEO",
                personality_preset="nonexistent",
                model_provider="test-provider",
                model_id="model-001",
            )

    def test_setup_company_request_defaults(self) -> None:
        from synthorg.api.controllers.setup import SetupCompanyRequest

        req = SetupCompanyRequest(company_name="Test Corp")
        assert req.template_name is None

    def test_setup_status_response_frozen(self) -> None:
        from synthorg.api.controllers.setup import SetupStatusResponse

        resp = SetupStatusResponse(
            needs_admin=True,
            needs_setup=True,
            has_providers=False,
        )
        with pytest.raises(ValidationError):
            resp.needs_admin = False  # type: ignore[misc]


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestExtractTemplateDepartments:
    """Unit tests for the _extract_template_departments helper."""

    def test_valid_template(self) -> None:
        from synthorg.api.controllers.setup import _extract_template_departments

        result = _extract_template_departments("solo_founder")
        assert result != ""
        import json

        departments = json.loads(result)
        assert len(departments) >= 1
        assert departments[0]["name"] in {"executive", "engineering"}

    def test_invalid_template(self) -> None:
        from synthorg.api.controllers.setup import _extract_template_departments
        from synthorg.api.errors import NotFoundError

        with pytest.raises(NotFoundError):
            _extract_template_departments("nonexistent_template")
