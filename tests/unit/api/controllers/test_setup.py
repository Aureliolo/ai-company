"""Tests for the first-run setup controller.

Covers template listing, company creation, setup completion,
and the template department extraction helpers.
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hsettings
from hypothesis import strategies as st
from litestar.testing import TestClient

from synthorg.providers.base import BaseCompletionProvider
from synthorg.providers.registry import ProviderRegistry
from tests.unit.api.conftest import make_auth_headers


@pytest.mark.unit
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
            assert "tags" in template
            assert isinstance(template["tags"], list)
            assert "skill_patterns" in template
            assert isinstance(template["skill_patterns"], list)
            assert "variables" in template
            assert isinstance(template["variables"], list)
            assert "agent_count" in template
            assert isinstance(template["agent_count"], int)
            assert template["agent_count"] >= 0
            assert "department_count" in template
            assert isinstance(template["department_count"], int)
            assert template["department_count"] >= 0
            assert "autonomy_level" in template
            assert template["autonomy_level"] in (
                "full",
                "semi",
                "supervised",
                "locked",
            )
            assert "workflow" in template
            assert isinstance(template["workflow"], str)

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

    def test_complete_rejects_without_db_company(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Completion rejects when company_name is only in YAML defaults."""
        repo = test_client.app.state.app_state.persistence._settings_repo
        key = ("company", "company_name")
        original = repo._store.get(key)
        repo._store.pop(key, None)
        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 422
            assert "company" in resp.json()["error"].lower()
        finally:
            if original is not None:
                repo._store[key] = original

    def test_complete_allows_without_agents(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Completion succeeds without agents (Quick Setup mode)."""
        app_state = test_client.app.state.app_state
        repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()
        repo._store[("company", "company_name")] = ("Test Corp", now)
        # Ensure at least one provider is registered.
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
            repo._store.pop(("company", "company_name"), None)
            repo._store.pop(("company", "agents"), None)
            repo._store.pop(("api", "setup_complete"), None)

    def test_complete_rejects_without_providers(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Completion rejects when company and agents exist but no providers."""
        repo = test_client.app.state.app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()
        repo._store[("company", "company_name")] = ("Test Corp", now)
        agents = json.dumps([{"name": "agent-001", "role": "CEO"}])
        repo._store[("company", "agents")] = (agents, now)
        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 422
            assert "provider" in resp.json()["error"].lower()
        finally:
            repo._store.pop(("company", "company_name"), None)
            repo._store.pop(("company", "agents"), None)

    def test_complete_succeeds_with_all_prerequisites(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Completion succeeds when company, agents, and providers exist."""
        app_state = test_client.app.state.app_state
        repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()
        repo._store[("company", "company_name")] = ("Test Corp", now)
        agents = json.dumps([{"name": "agent-001", "role": "CEO"}])
        repo._store[("company", "agents")] = (agents, now)
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
            repo._store.pop(("company", "company_name"), None)
            repo._store.pop(("company", "agents"), None)
            repo._store.pop(("api", "setup_complete"), None)

    def test_complete_bootstraps_agents_into_registry(
        self,
        test_client: TestClient[Any],
    ) -> None:
        """Setup completion registers agents in the runtime registry."""
        app_state = test_client.app.state.app_state
        repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()
        repo._store[("company", "company_name")] = ("Test Corp", now)
        agents = json.dumps(
            [
                {
                    "name": "alice",
                    "role": "developer",
                    "department": "engineering",
                    "model": {
                        "provider": "test-provider",
                        "model_id": "test-small-001",
                    },
                },
            ]
        )
        repo._store[("company", "agents")] = (agents, now)
        stub = MagicMock(spec=BaseCompletionProvider)
        original_registry = app_state._provider_registry
        app_state._provider_registry = ProviderRegistry(
            {"test-provider": stub},
        )
        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 201
            assert resp.json()["data"]["setup_complete"] is True
            # Agent should now be in the runtime registry.
            loop = asyncio.new_event_loop()
            try:
                agent_count = loop.run_until_complete(
                    app_state.agent_registry.agent_count(),
                )
            finally:
                loop.close()
            assert agent_count >= 1
        finally:
            app_state._provider_registry = original_registry
            repo._store.pop(("company", "company_name"), None)
            repo._store.pop(("company", "agents"), None)
            repo._store.pop(("api", "setup_complete"), None)

    def test_complete_succeeds_even_if_bootstrap_fails(
        self,
        test_client: TestClient[Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Setup completion returns 201 even if agent bootstrap raises."""
        app_state = test_client.app.state.app_state
        repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()
        repo._store[("company", "company_name")] = ("Test Corp", now)
        agents = json.dumps([{"name": "agent-001", "role": "CEO"}])
        repo._store[("company", "agents")] = (agents, now)
        stub = MagicMock(spec=BaseCompletionProvider)
        original_registry = app_state._provider_registry
        app_state._provider_registry = ProviderRegistry(
            {"test-provider": stub},
        )

        # Make bootstrap_agents raise to simulate failure.
        failing_bootstrap = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(
            "synthorg.api.bootstrap.bootstrap_agents",
            failing_bootstrap,
        )

        try:
            resp = test_client.post("/api/v1/setup/complete")
            # Must succeed despite bootstrap failure (non-fatal).
            assert resp.status_code == 201
            assert resp.json()["data"]["setup_complete"] is True
            failing_bootstrap.assert_awaited_once()
        finally:
            app_state._provider_registry = original_registry
            repo._store.pop(("company", "company_name"), None)
            repo._store.pop(("company", "agents"), None)
            repo._store.pop(("api", "setup_complete"), None)

    def test_complete_reloads_provider_registry(
        self,
        test_client: TestClient[Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Setup completion reloads the provider registry from config."""
        app_state = test_client.app.state.app_state
        repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()
        repo._store[("company", "company_name")] = ("Test Corp", now)
        agents = json.dumps(
            [
                {
                    "name": "alice",
                    "role": "developer",
                    "department": "engineering",
                    "model": {
                        "provider": "test-provider",
                        "model_id": "test-small-001",
                    },
                },
            ]
        )
        repo._store[("company", "agents")] = (agents, now)
        stub = MagicMock(spec=BaseCompletionProvider)
        original_registry = app_state._provider_registry
        app_state._provider_registry = ProviderRegistry(
            {"test-provider": stub},
        )

        # Replace _post_setup_reinit with a wrapper that swaps the
        # provider registry and records the call, simulating the real
        # reload without needing stored provider configs or a real
        # ProviderRegistry.from_config invocation.
        fresh_registry = ProviderRegistry({"reloaded-provider": stub})
        reinit_called = False

        async def _fake_reinit(state: object) -> None:
            nonlocal reinit_called
            reinit_called = True
            app_state.swap_provider_registry(fresh_registry)

        monkeypatch.setattr(
            "synthorg.api.controllers.setup._post_setup_reinit",
            _fake_reinit,
        )

        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 201
            assert resp.json()["data"]["setup_complete"] is True
            # _post_setup_reinit was invoked by complete_setup.
            assert reinit_called
            # The provider registry should have been swapped.
            assert app_state._provider_registry is fresh_registry
        finally:
            app_state._provider_registry = original_registry
            repo._store.pop(("company", "company_name"), None)
            repo._store.pop(("company", "agents"), None)
            repo._store.pop(("api", "setup_complete"), None)

    def test_complete_bootstraps_even_when_provider_reload_fails(
        self,
        test_client: TestClient[Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Agent bootstrap runs even when provider reload raises."""
        app_state = test_client.app.state.app_state
        repo = app_state.persistence._settings_repo
        now = datetime.now(UTC).isoformat()
        repo._store[("company", "company_name")] = ("Test Corp", now)
        agents = json.dumps(
            [
                {
                    "name": "alice",
                    "role": "developer",
                    "department": "engineering",
                    "model": {
                        "provider": "test-provider",
                        "model_id": "test-small-001",
                    },
                },
            ]
        )
        repo._store[("company", "agents")] = (agents, now)
        stub = MagicMock(spec=BaseCompletionProvider)
        original_registry = app_state._provider_registry
        app_state._provider_registry = ProviderRegistry(
            {"test-provider": stub},
        )

        # Make provider config loading raise to simulate reload failure.
        monkeypatch.setattr(
            "synthorg.providers.registry.ProviderRegistry.from_config",
            MagicMock(side_effect=RuntimeError("provider config broken")),
        )

        try:
            resp = test_client.post("/api/v1/setup/complete")
            assert resp.status_code == 201
            assert resp.json()["data"]["setup_complete"] is True
            # Agent bootstrap should still have run despite provider
            # reload failure -- the two operations are independent.
            loop = asyncio.new_event_loop()
            try:
                agent_count = loop.run_until_complete(
                    app_state.agent_registry.agent_count(),
                )
            finally:
                loop.close()
            assert agent_count >= 1
        finally:
            app_state._provider_registry = original_registry
            repo._store.pop(("company", "company_name"), None)
            repo._store.pop(("company", "agents"), None)
            repo._store.pop(("api", "setup_complete"), None)


@pytest.mark.unit
class TestExtractTemplateDepartments:
    """Unit tests for the _load_template_safe + _departments_to_json helpers."""

    def test_valid_template(self) -> None:
        from synthorg.api.controllers.setup_agents import departments_to_json
        from synthorg.api.controllers.setup_helpers import (
            load_template_safe as _load_template_safe,
        )

        loaded = _load_template_safe("solo_founder")
        result = departments_to_json(loaded.template.departments)
        assert result != ""
        departments = json.loads(result)
        assert len(departments) >= 1
        assert departments[0]["name"] in {"executive", "engineering"}

    def test_invalid_template(self) -> None:
        from synthorg.api.controllers.setup_helpers import (
            load_template_safe as _load_template_safe,
        )
        from synthorg.api.errors import NotFoundError

        with pytest.raises(NotFoundError):
            _load_template_safe("nonexistent_template")
