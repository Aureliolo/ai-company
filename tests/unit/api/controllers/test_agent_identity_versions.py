"""Tests for agent identity version API endpoints."""

from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from litestar.testing import TestClient

from synthorg.core.agent import AgentIdentity, ModelConfig
from synthorg.core.enums import SeniorityLevel
from synthorg.hr.registry import AgentRegistryService
from tests.unit.api.conftest import make_auth_headers
from tests.unit.api.fakes_backend import FakePersistenceBackend


def _make_identity(name: str = "agent-ver") -> AgentIdentity:
    return AgentIdentity(
        id=uuid4(),
        name=name,
        role="developer",
        department="engineering",
        level=SeniorityLevel.MID,
        model=ModelConfig(provider="test-provider", model_id="test-small-001"),
        hiring_date=date(2026, 1, 1),
    )


async def _seed_versions(
    registry: AgentRegistryService,
    *,
    updates: int = 0,
) -> AgentIdentity:
    """Register an agent and issue ``updates`` charter updates.

    Each ``update_identity`` bumps ``level`` so that the content hash
    actually changes (no-op snapshots are suppressed by the service).
    """
    identity = _make_identity()
    await registry.register(identity)
    levels = (
        SeniorityLevel.SENIOR,
        SeniorityLevel.LEAD,
        SeniorityLevel.PRINCIPAL,
    )
    for i in range(updates):
        await registry.update_identity(str(identity.id), level=levels[i])
    return identity


class TestListVersions:
    """``GET /agents/{agent_id}/versions``."""

    @pytest.mark.unit
    async def test_single_version_after_register(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["version"] == 1
        assert body["data"][0]["entity_id"] == str(identity.id)
        assert body["pagination"]["total"] == 1

    @pytest.mark.unit
    async def test_multiple_versions_after_updates(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=2)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        versions = resp.json()["data"]
        assert {v["version"] for v in versions} == {1, 2, 3}

    @pytest.mark.unit
    async def test_empty_for_unknown_agent(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.get(
            f"/api/v1/agents/{uuid4()}/versions",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0
        assert body["pagination"]["offset"] == 0
        assert body["pagination"]["limit"] == 20


class TestGetVersion:
    """``GET /agents/{agent_id}/versions/{version_num}``."""

    @pytest.mark.unit
    async def test_returns_snapshot(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions/1",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["version"] == 1
        assert data["snapshot"]["name"] == identity.name

    @pytest.mark.unit
    async def test_missing_version_returns_404(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions/42",
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["error"].lower()


class TestDiff:
    """``GET /agents/{agent_id}/versions/diff``."""

    @pytest.mark.unit
    async def test_computes_level_diff(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=1)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions/diff",
            params={"from_version": 1, "to_version": 2},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        diff = resp.json()["data"]
        assert diff["from_version"] == 1
        assert diff["to_version"] == 2
        paths = {c["field_path"] for c in diff["field_changes"]}
        assert "level" in paths

    @pytest.mark.unit
    async def test_same_versions_rejected(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=1)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions/diff",
            params={"from_version": 1, "to_version": 1},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 400

    @pytest.mark.unit
    async def test_missing_from_version_returns_404(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=1)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions/diff",
            params={"from_version": 99, "to_version": 100},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_reversed_versions_rejected(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        """``from_version`` must be strictly less than ``to_version``."""
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=1)
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions/diff",
            params={"from_version": 2, "to_version": 1},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 400


class TestRollback:
    """``POST /agents/{agent_id}/versions/rollback``."""

    @pytest.mark.unit
    async def test_rolls_back_level(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=2)
        resp = test_client.post(
            f"/api/v1/agents/{identity.id}/versions/rollback",
            json={"target_version": 1},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["level"] == "mid"
        current = await agent_registry.get(str(identity.id))
        assert current is not None
        assert current.level is SeniorityLevel.MID

    @pytest.mark.unit
    async def test_rollback_creates_new_snapshot(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=1)
        test_client.post(
            f"/api/v1/agents/{identity.id}/versions/rollback",
            json={"target_version": 1},
            headers=make_auth_headers("ceo"),
        )
        resp = test_client.get(
            f"/api/v1/agents/{identity.id}/versions",
            headers=make_auth_headers("ceo"),
        )
        versions = resp.json()["data"]
        assert {v["version"] for v in versions} == {1, 2, 3}

    @pytest.mark.unit
    async def test_rollback_unknown_agent_returns_404(
        self,
        test_client: TestClient[Any],
    ) -> None:
        resp = test_client.post(
            f"/api/v1/agents/{uuid4()}/versions/rollback",
            json={"target_version": 1},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_rollback_missing_target_returns_404(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry)
        resp = test_client.post(
            f"/api/v1/agents/{identity.id}/versions/rollback",
            json={"target_version": 99},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_rollback_with_reason_records_audit_trail(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        """Optional ``reason`` passes through without breaking rollback."""
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        identity = await _seed_versions(agent_registry, updates=1)
        resp = test_client.post(
            f"/api/v1/agents/{identity.id}/versions/rollback",
            json={"target_version": 1, "reason": "undo accidental promotion"},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 200

    @pytest.mark.unit
    async def test_rollback_rejects_cross_entity_snapshot(
        self,
        test_client: TestClient[Any],
        fake_persistence: FakePersistenceBackend,
        agent_registry: AgentRegistryService,
    ) -> None:
        """If a version's snapshot id differs from the URL agent_id, 400."""
        fake_persistence.identity_versions.clear()
        agent_registry.clear()
        # Register two agents, each with one version.
        alice = await _seed_versions(agent_registry)
        bob = await _seed_versions(agent_registry)
        # Forge a cross-wired snapshot: store Alice's identity under Bob's id.
        from synthorg.versioning import VersionSnapshot

        alice_latest = await fake_persistence.identity_versions.get_latest_version(
            str(alice.id)
        )
        assert alice_latest is not None
        forged = VersionSnapshot(
            entity_id=str(bob.id),
            version=99,
            content_hash="f" * 64,
            snapshot=alice_latest.snapshot,  # still has alice.id inside
            saved_by="test-forger",
            saved_at=alice_latest.saved_at,
        )
        await fake_persistence.identity_versions.save_version(forged)
        resp = test_client.post(
            f"/api/v1/agents/{bob.id}/versions/rollback",
            json={"target_version": 99},
            headers=make_auth_headers("ceo"),
        )
        assert resp.status_code == 400
        assert "different agent" in resp.json()["error"].lower()
