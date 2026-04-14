"""Tests for A2A gateway configuration."""

import pytest

from synthorg.a2a.config import (
    A2AAgentCardVerificationConfig,
    A2AAuthConfig,
    A2AConfig,
    A2APushConfig,
)


class TestA2AConfig:
    """A2AConfig validation and defaults."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        """Default config has gateway disabled with safe values."""
        cfg = A2AConfig()
        assert cfg.enabled is False
        assert cfg.allowed_peers == ()
        assert cfg.rate_limit_per_peer_rpm == 100
        assert cfg.sse_idle_timeout_seconds == 300
        assert cfg.max_request_body_bytes == 1_048_576
        assert cfg.agent_card_cache_ttl_seconds == 60

    @pytest.mark.unit
    def test_enabled_with_peers(self) -> None:
        """Can enable with an explicit peer allowlist."""
        cfg = A2AConfig(enabled=True, allowed_peers=("peer-a", "peer-b"))
        assert cfg.enabled is True
        assert cfg.allowed_peers == ("peer-a", "peer-b")

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """Config is immutable."""
        cfg = A2AConfig()
        with pytest.raises(Exception):  # noqa: B017, PT011
            cfg.enabled = True  # type: ignore[misc]

    @pytest.mark.unit
    def test_rate_limit_min(self) -> None:
        """Rate limit must be at least 1."""
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            A2AConfig(rate_limit_per_peer_rpm=0)

    @pytest.mark.unit
    def test_sse_timeout_min(self) -> None:
        """SSE timeout must be at least 30 seconds."""
        with pytest.raises(ValueError, match="greater than or equal to 30"):
            A2AConfig(sse_idle_timeout_seconds=10)

    @pytest.mark.unit
    def test_max_body_min(self) -> None:
        """Max body size must be at least 1024 bytes."""
        with pytest.raises(ValueError, match="greater than or equal to 1024"):
            A2AConfig(max_request_body_bytes=100)

    @pytest.mark.unit
    def test_cache_ttl_zero_disables(self) -> None:
        """TTL of 0 is valid (disables caching)."""
        cfg = A2AConfig(agent_card_cache_ttl_seconds=0)
        assert cfg.agent_card_cache_ttl_seconds == 0

    @pytest.mark.unit
    def test_allowed_peers_rejects_blank(self) -> None:
        """Blank peer names are rejected by NotBlankStr."""
        with pytest.raises(ValueError, match="whitespace"):
            A2AConfig(allowed_peers=("  ",))

    @pytest.mark.unit
    def test_serialization_round_trip(self) -> None:
        """Config survives JSON serialization round-trip."""
        cfg = A2AConfig(
            enabled=True,
            allowed_peers=("peer-a",),
            rate_limit_per_peer_rpm=50,
        )
        data = cfg.model_dump()
        restored = A2AConfig.model_validate(data)
        assert restored == cfg


class TestA2AAuthConfig:
    """A2AAuthConfig defaults and validation."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        """Auth config defaults to api_key inbound, bearer outbound."""
        cfg = A2AAuthConfig()
        assert cfg.inbound_scheme == "api_key"
        assert cfg.outbound_scheme == "bearer"

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """Auth config is immutable."""
        cfg = A2AAuthConfig()
        with pytest.raises(Exception):  # noqa: B017, PT011
            cfg.inbound_scheme = "oauth2"  # type: ignore[misc]


class TestA2APushConfig:
    """A2APushConfig defaults and validation."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        """Push config defaults to disabled with safe values."""
        cfg = A2APushConfig()
        assert cfg.enabled is False
        assert cfg.signature_algorithm == "hmac-sha256"
        assert cfg.clock_skew_seconds == 300
        assert cfg.replay_window_seconds == 60

    @pytest.mark.unit
    def test_clock_skew_zero(self) -> None:
        """Clock skew of 0 is valid (strict timestamp check)."""
        cfg = A2APushConfig(clock_skew_seconds=0)
        assert cfg.clock_skew_seconds == 0


class TestA2AAgentCardVerificationConfig:
    """Agent card verification config."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        """Verification defaults to disabled."""
        cfg = A2AAgentCardVerificationConfig()
        assert cfg.enabled is False
        assert cfg.require_signatures is False
        assert cfg.trusted_jwks_urls == ()
        assert cfg.trusted_public_keys == ()


class TestRootConfigA2AField:
    """A2AConfig integration with RootConfig."""

    @pytest.mark.unit
    def test_root_config_has_a2a(self) -> None:
        """RootConfig includes an a2a field with defaults."""
        from synthorg.config.schema import RootConfig

        cfg = RootConfig(company_name="test-co")
        assert cfg.a2a.enabled is False

    @pytest.mark.unit
    def test_root_config_a2a_enabled(self) -> None:
        """RootConfig can enable A2A via nested config."""
        from synthorg.config.schema import RootConfig

        cfg = RootConfig(
            company_name="test-co",
            a2a=A2AConfig(enabled=True, allowed_peers=("external-co",)),
        )
        assert cfg.a2a.enabled is True
        assert cfg.a2a.allowed_peers == ("external-co",)


class TestA2APeerAuthenticator:
    """A2A peer connection authenticator (scheme-aware)."""

    @pytest.mark.unit
    def test_api_key_valid(self) -> None:
        """Valid api_key credentials pass."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )

        auth = A2APeerAuthenticator()
        auth.validate_credentials({"api_key": "secret"})

    @pytest.mark.unit
    def test_api_key_missing(self) -> None:
        """Missing api_key raises."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )
        from synthorg.integrations.errors import InvalidConnectionAuthError

        auth = A2APeerAuthenticator()
        with pytest.raises(InvalidConnectionAuthError):
            auth.validate_credentials({})

    @pytest.mark.unit
    def test_api_key_blank(self) -> None:
        """Blank api_key raises."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )
        from synthorg.integrations.errors import InvalidConnectionAuthError

        auth = A2APeerAuthenticator()
        with pytest.raises(InvalidConnectionAuthError):
            auth.validate_credentials({"api_key": "  "})

    @pytest.mark.unit
    def test_bearer_scheme(self) -> None:
        """Bearer scheme requires access_token."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )

        auth = A2APeerAuthenticator()
        auth.validate_credentials(
            {
                "auth_scheme": "bearer",
                "access_token": "tok",
            }
        )

    @pytest.mark.unit
    def test_bearer_missing_token(self) -> None:
        """Bearer scheme without token raises."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )
        from synthorg.integrations.errors import InvalidConnectionAuthError

        auth = A2APeerAuthenticator()
        with pytest.raises(InvalidConnectionAuthError):
            auth.validate_credentials({"auth_scheme": "bearer"})

    @pytest.mark.unit
    def test_oauth2_scheme(self) -> None:
        """OAuth2 scheme requires client_id and client_secret."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )

        auth = A2APeerAuthenticator()
        auth.validate_credentials(
            {
                "auth_scheme": "oauth2",
                "client_id": "id",
                "client_secret": "secret",
            }
        )

    @pytest.mark.unit
    def test_oauth2_missing_secret(self) -> None:
        """OAuth2 scheme without client_secret raises."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )
        from synthorg.integrations.errors import InvalidConnectionAuthError

        auth = A2APeerAuthenticator()
        with pytest.raises(InvalidConnectionAuthError):
            auth.validate_credentials(
                {
                    "auth_scheme": "oauth2",
                    "client_id": "id",
                }
            )

    @pytest.mark.unit
    def test_mtls_scheme(self) -> None:
        """mTLS scheme requires cert_path and key_path."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )

        auth = A2APeerAuthenticator()
        auth.validate_credentials(
            {
                "auth_scheme": "mtls",
                "cert_path": "/certs/peer.crt",
                "key_path": "/certs/peer.key",
            }
        )

    @pytest.mark.unit
    def test_none_scheme(self) -> None:
        """None scheme requires no credentials."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )

        auth = A2APeerAuthenticator()
        auth.validate_credentials({"auth_scheme": "none"})

    @pytest.mark.unit
    def test_required_fields_default(self) -> None:
        """Default required_fields returns api_key."""
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )

        auth = A2APeerAuthenticator()
        assert auth.required_fields() == ("api_key",)

    @pytest.mark.unit
    def test_connection_type(self) -> None:
        """Authenticator handles A2A_PEER type."""
        from synthorg.integrations.connections.models import ConnectionType
        from synthorg.integrations.connections.types.a2a_peer import (
            A2APeerAuthenticator,
        )

        auth = A2APeerAuthenticator()
        assert auth.connection_type == ConnectionType.A2A_PEER
