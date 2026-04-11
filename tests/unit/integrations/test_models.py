"""Unit tests for integration domain models."""

import pytest
from pydantic import ValidationError

from synthorg.integrations.config import IntegrationsConfig
from synthorg.integrations.connections.models import (
    AuthMethod,
    Connection,
    ConnectionStatus,
    ConnectionType,
    SecretRef,
)


@pytest.mark.unit
class TestConnectionModel:
    """Tests for the Connection frozen model."""

    def test_default_construction(self) -> None:
        conn = Connection(
            name="test",
            connection_type=ConnectionType.GITHUB,
            auth_method=AuthMethod.BEARER_TOKEN,
        )
        assert conn.name == "test"
        assert conn.connection_type == ConnectionType.GITHUB
        assert conn.health_status == ConnectionStatus.UNKNOWN
        assert conn.secret_refs == ()
        assert conn.metadata == {}

    def test_frozen(self) -> None:
        conn = Connection(
            name="test",
            connection_type=ConnectionType.SLACK,
            auth_method=AuthMethod.OAUTH2,
        )
        with pytest.raises(ValidationError):
            conn.name = "changed"  # type: ignore[misc]

    def test_metadata_deep_copied(self) -> None:
        meta = {"key": "value"}
        conn = Connection(
            name="test",
            connection_type=ConnectionType.GITHUB,
            auth_method=AuthMethod.API_KEY,
            metadata=meta,
        )
        meta["key"] = "modified"
        assert conn.metadata["key"] == "value"


@pytest.mark.unit
class TestSecretRefModel:
    """Tests for the SecretRef model."""

    def test_construction(self) -> None:
        ref = SecretRef(
            secret_id="abc-123",
            backend="encrypted_sqlite",
        )
        assert ref.secret_id == "abc-123"
        assert ref.key_version == 1


@pytest.mark.unit
class TestIntegrationsConfig:
    """Tests for the IntegrationsConfig."""

    def test_default_construction(self) -> None:
        config = IntegrationsConfig()
        assert config.enabled is True
        assert config.webhooks.rate_limit_rpm == 100
        assert config.webhooks.replay_window_seconds == 300
        assert config.health.check_interval_seconds == 300
        assert config.secret_backend.backend_type == "encrypted_sqlite"
        assert config.tunnel.enabled is False
        assert config.mcp_catalog.enabled is True

    def test_frozen(self) -> None:
        config = IntegrationsConfig()
        with pytest.raises(ValidationError):
            config.enabled = False  # type: ignore[misc]
