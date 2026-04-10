"""Tests for identity store factory."""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from synthorg.engine.identity.store.append_only import AppendOnlyIdentityStore
from synthorg.engine.identity.store.config import IdentityStoreConfig
from synthorg.engine.identity.store.copy_on_write import CopyOnWriteIdentityStore
from synthorg.engine.identity.store.factory import build_identity_store
from synthorg.hr.registry import AgentRegistryService
from synthorg.versioning.service import VersioningService


class TestBuildIdentityStore:
    """build_identity_store dispatches on config type."""

    @pytest.mark.unit
    def test_append_only(self) -> None:
        config = IdentityStoreConfig(type="append_only")
        repo = AsyncMock()
        store = build_identity_store(
            config,
            registry=AgentRegistryService(),
            versioning=VersioningService(repo),
        )
        assert isinstance(store, AppendOnlyIdentityStore)

    @pytest.mark.unit
    def test_copy_on_write(self) -> None:
        config = IdentityStoreConfig(type="copy_on_write")
        repo = AsyncMock()
        store = build_identity_store(
            config,
            registry=AgentRegistryService(),
            versioning=VersioningService(repo),
        )
        assert isinstance(store, CopyOnWriteIdentityStore)

    @pytest.mark.unit
    def test_default_is_append_only(self) -> None:
        config = IdentityStoreConfig()
        repo = AsyncMock()
        store = build_identity_store(
            config,
            registry=AgentRegistryService(),
            versioning=VersioningService(repo),
        )
        assert isinstance(store, AppendOnlyIdentityStore)


class TestIdentityStoreConfig:
    """IdentityStoreConfig validation."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        config = IdentityStoreConfig()
        assert config.type == "append_only"
        assert config.max_versions_per_agent is None

    @pytest.mark.unit
    def test_max_versions_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal"):
            IdentityStoreConfig(max_versions_per_agent=0)

    @pytest.mark.unit
    def test_frozen(self) -> None:
        config = IdentityStoreConfig()
        with pytest.raises(ValidationError):
            config.type = "copy_on_write"  # type: ignore[misc]
