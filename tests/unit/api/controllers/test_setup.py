"""Tests for the first-run setup controller."""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hsettings
from hypothesis import strategies as st
from litestar.testing import TestClient
from pydantic import ValidationError

from synthorg.api.guards import HumanRole
from synthorg.providers.base import BaseCompletionProvider
from synthorg.providers.registry import ProviderRegistry
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

    def test_needs_admin_true_when_only_non_admin_exists(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """needs_admin is True when only non-CEO users exist."""
        app_state = test_client.app.state.app_state
        users_repo = app_state.persistence._users

        # Remove all CEO users, keep only observers
        removed = {
            uid: users_repo._users.pop(uid)
            for uid in [
                uid for uid, u in users_repo._users.items() if u.role == HumanRole.CEO
            ]
        }
        try:
            resp = test_client.get("/api/v1/setup/status")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["needs_admin"] is True
        finally:
            users_repo._users.update(removed)

    def test_needs_admin_false_when_ceo_exists(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """needs_admin is False when a CEO user exists (default fixture)."""
        resp = test_client.get("/api/v1/setup/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["needs_admin"] is False

    def test_status_includes_min_password_length(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Status response includes min_password_length (falls back to default)."""
        resp = test_client.get("/api/v1/setup/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "min_password_length" in data
        assert isinstance(data["min_password_length"], int)
        assert data["min_password_length"] == 12

    def test_status_returns_configured_min_password_length(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Status response returns non-default min_password_length from settings."""
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()

        settings_repo._store[("api", "min_password_length")] = ("16", now)
        try:
            resp = test_client.get("/api/v1/setup/status")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["min_password_length"] == 16
        finally:
            settings_repo._store.pop(("api", "min_password_length"), None)


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

    def test_observer_can_read_templates(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Observer role has read access to templates."""
        saved_headers = dict(test_client.headers)
        test_client.headers.update(make_auth_headers("observer"))
        try:
            resp = test_client.get("/api/v1/setup/templates")
            assert resp.status_code == 200
        finally:
            test_client.headers.update(saved_headers)


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
        assert data["description"] is None

        # Verify description persisted as "" (absent convention).
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo
        stored = settings_repo._store.get(("company", "description"))
        assert stored is not None
        assert stored[0] == ""

    @pytest.mark.parametrize(
        ("description_input", "expected_response", "expected_stored"),
        [
            (
                "An AI-powered test organization",
                "An AI-powered test organization",
                "An AI-powered test organization",
            ),
            ("  hello world  ", "hello world", "hello world"),
            ("   ", None, ""),
            ("", None, ""),
        ],
        ids=["normal", "stripped", "whitespace-only", "empty"],
    )
    def test_description_normalization(
        self,
        test_client: TestClient[Any],
        description_input: str,
        expected_response: str | None,
        expected_stored: str,
    ) -> None:
        """Description is stripped and blank values normalized to None."""
        resp = test_client.post(
            "/api/v1/setup/company",
            json={
                "company_name": "Test Corp",
                "description": description_input,
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["description"] == expected_response

        # Verify persistence.
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo
        stored = settings_repo._store.get(("company", "description"))
        assert stored is not None
        assert stored[0] == expected_stored

    @given(description=st.text(max_size=1000))
    @hsettings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_description_normalization_invariants(
        self,
        test_client: TestClient[Any],
        description: str,
    ) -> None:
        """Normalization invariant: blank -> None, non-blank -> stripped."""
        resp = test_client.post(
            "/api/v1/setup/company",
            json={
                "company_name": "Test Corp",
                "description": description,
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]

        stripped = description.strip()
        if stripped == "":
            assert data["description"] is None
        else:
            assert data["description"] == stripped

        # Verify persistence matches.
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo
        stored = settings_repo._store.get(("company", "description"))
        assert stored is not None
        expected_stored = stripped or ""
        assert stored[0] == expected_stored

    def test_company_description_too_long(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Description exceeding 1000 characters is rejected."""
        resp = test_client.post(
            "/api/v1/setup/company",
            json={
                "company_name": "Test Corp",
                "description": "x" * 1001,
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["success"] is False
        assert body["error_detail"]["error_category"] == "validation"

    def test_description_at_max_length_accepted(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Description of exactly 1000 characters is accepted."""
        resp = test_client.post(
            "/api/v1/setup/company",
            json={
                "company_name": "Test Corp",
                "description": "x" * 1000,
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["description"] == "x" * 1000

        # Verify persistence.
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo
        stored = settings_repo._store.get(("company", "description"))
        assert stored is not None
        assert stored[0] == "x" * 1000

    def test_description_overwrite_clears_stale(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Re-creating company without description clears previous value."""
        # First create with a description.
        resp = test_client.post(
            "/api/v1/setup/company",
            json={
                "company_name": "Test Corp",
                "description": "Original description",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["description"] == "Original description"

        # Re-create without description -- stale value must be cleared.
        resp = test_client.post(
            "/api/v1/setup/company",
            json={"company_name": "Test Corp v2"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["description"] is None

        # Verify persistence cleared.
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo
        stored = settings_repo._store.get(("company", "description"))
        assert stored is not None
        assert stored[0] == ""

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
        saved_headers = dict(test_client.headers)
        test_client.headers.update(make_auth_headers("observer"))
        try:
            resp = test_client.post(
                "/api/v1/setup/company",
                json={"company_name": "Test Corp"},
            )
            assert resp.status_code == 403
        finally:
            test_client.headers.update(saved_headers)


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupAgent:
    """POST /api/v1/setup/agent -- create agent."""

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
        saved_headers = dict(test_client.headers)
        test_client.headers.update(make_auth_headers("observer"))
        try:
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
        finally:
            test_client.headers.update(saved_headers)

    def test_successful_agent_creation(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Happy path: provider and model exist, agent is created."""
        # Build a mock provider config with a test model.
        mock_model = MagicMock()
        mock_model.id = "test-small-001"
        mock_model.alias = None
        mock_provider_config = MagicMock()
        mock_provider_config.models = [mock_model]

        mock_mgmt = MagicMock()
        mock_mgmt.list_providers = AsyncMock(
            return_value={"test-provider": mock_provider_config},
        )

        app_state = test_client.app.state.app_state
        original_mgmt = app_state._provider_management
        app_state._provider_management = mock_mgmt
        try:
            resp = test_client.post(
                "/api/v1/setup/agent",
                json={
                    "name": "agent-ceo-001",
                    "role": "CEO",
                    "model_provider": "test-provider",
                    "model_id": "test-small-001",
                },
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["success"] is True
            data = body["data"]
            assert data["name"] == "agent-ceo-001"
            assert data["role"] == "CEO"
            assert data["department"] == "engineering"
            assert data["model_provider"] == "test-provider"
            assert data["model_id"] == "test-small-001"
        finally:
            app_state._provider_management = original_mgmt


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestSetupComplete:
    """POST /api/v1/setup/complete -- mark setup as done."""

    def test_requires_write_access(
        self,
        test_client: TestClient[Any],
    ) -> None:
        saved_headers = dict(test_client.headers)
        test_client.headers.update(make_auth_headers("observer"))
        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 403
        finally:
            test_client.headers.update(saved_headers)

    def test_complete_rejects_without_company(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Completion rejects when no company name is set."""
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo

        # Remove company_name from the settings store so the YAML
        # fallback chain also yields nothing.  The fixture's root_config
        # provides company_name, so we need to override at the DB level
        # with an empty string to simulate "not configured".
        now = datetime.now(UTC).isoformat()
        settings_repo._store[("company", "company_name")] = ("", now)
        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 422
            assert "company" in resp.json()["error"].lower()
        finally:
            settings_repo._store.pop(("company", "company_name"), None)

    def test_complete_validates_all_prerequisites(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Completion requires company, agents, and providers.

        The test fixture's root_config provides company_name, so the
        company check passes automatically. This test walks through
        the remaining prerequisite checks: agents, then providers,
        then confirms success once all are satisfied.
        """
        app_state = test_client.app.state.app_state
        settings_repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()

        # 1. No agents -- rejected (company comes from root_config).
        resp = test_client.post("/api/v1/setup/complete")
        assert resp.status_code == 422
        assert "agent" in resp.json()["error"].lower()

        # 2. Agents set, no providers -- rejected.
        agents_key = ("company", "agents")
        original_agents = settings_repo._store.get(agents_key)
        agents_json = json.dumps([{"name": "agent-001", "role": "CEO"}])
        settings_repo._store[agents_key] = (agents_json, now)
        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 422
            assert "provider" in resp.json()["error"].lower()

            # 3. All present -- success.
            stub = MagicMock(spec=BaseCompletionProvider)
            original_registry = app_state._provider_registry
            app_state._provider_registry = ProviderRegistry(
                {"test-provider": stub},
            )
            try:
                resp = test_client.post("/api/v1/setup/complete")
                assert resp.status_code == 201
                body = resp.json()
                assert body["success"] is True
                assert body["data"]["setup_complete"] is True
            finally:
                app_state._provider_registry = original_registry
        finally:
            if original_agents is None:
                settings_repo._store.pop(agents_key, None)
            else:
                settings_repo._store[agents_key] = original_agents


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
        # Validator normalizes to lowercase
        assert req.personality_preset == "visionary_leader"

    def test_setup_agent_request_invalid_preset(self) -> None:
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
        assert req.description is None

    def test_setup_status_response_frozen(self) -> None:
        from synthorg.api.controllers.setup import SetupStatusResponse

        resp = SetupStatusResponse(
            needs_admin=True,
            needs_setup=True,
            has_providers=False,
            min_password_length=12,
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
        departments = json.loads(result)
        assert len(departments) >= 1
        assert departments[0]["name"] in {"executive", "engineering"}

    def test_invalid_template(self) -> None:
        from synthorg.api.controllers.setup import _extract_template_departments
        from synthorg.api.errors import NotFoundError

        with pytest.raises(NotFoundError):
            _extract_template_departments("nonexistent_template")
