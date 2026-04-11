"""Configuration models for the integrations subsystem.

All models are frozen Pydantic ``BaseModel`` instances following
the codebase convention of ``ConfigDict(frozen=True, allow_inf_nan=False)``.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConnectionsConfig(BaseModel):
    """Connection catalog configuration.

    Attributes:
        max_connections_per_type: Upper bound per connection type.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    max_connections_per_type: int = Field(default=100, ge=1)


class EncryptedSqliteConfig(BaseModel):
    """Config for the encrypted SQLite secret backend.

    Attributes:
        master_key_env: Environment variable holding the base64-encoded
            32-byte master key.  When unset, a random key is generated
            at first startup and written to ``$SYNTHORG_DATA_DIR/.master_key``.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    master_key_env: str = "SYNTHORG_MASTER_KEY"


class EnvVarConfig(BaseModel):
    """Config for the environment variable secret backend.

    Attributes:
        prefix: Environment variable prefix for secret lookups.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    prefix: str = "SYNTHORG_SECRET_"


class SecretBackendConfig(BaseModel):
    """Pluggable secret storage configuration.

    Attributes:
        backend_type: Which backend to use.
        encrypted_sqlite: Settings for the default backend.
        env_var: Settings for the env-var backend.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    # Neutral, vendor-agnostic discriminators so the public config
    # surface does not embed specific vendor names. The factory maps
    # these to concrete adapters internally:
    #   - ``encrypted_sqlite``: bundled Fernet+SQLite backend (default)
    #   - ``env_var``: environment variable backend
    #   - ``secret_manager_vault``: HashiCorp Vault adapter (stub)
    #   - ``secret_manager_cloud_a``: AWS Secrets Manager adapter (stub)
    #   - ``secret_manager_cloud_b``: Azure Key Vault adapter (stub)
    backend_type: Literal[
        "encrypted_sqlite",
        "env_var",
        "secret_manager_vault",
        "secret_manager_cloud_a",
        "secret_manager_cloud_b",
    ] = "encrypted_sqlite"
    encrypted_sqlite: EncryptedSqliteConfig = Field(
        default_factory=EncryptedSqliteConfig,
    )
    env_var: EnvVarConfig = Field(
        default_factory=EnvVarConfig,
    )


class OAuthConfig(BaseModel):
    """OAuth 2.1 subsystem configuration.

    Attributes:
        redirect_uri_base: Base URL for OAuth callbacks.
        state_expiry_seconds: How long OAuth state tokens live.
        pkce_required: Require PKCE for authorization code flows.
        device_flow_poll_interval_seconds: Polling interval for device flow.
        device_flow_timeout_seconds: Max wait for device flow user grant.
        auto_refresh_threshold_seconds: Refresh tokens expiring within
            this window.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    redirect_uri_base: str = ""
    state_expiry_seconds: int = Field(default=3600, gt=0)
    pkce_required: bool = True
    device_flow_poll_interval_seconds: int = Field(default=5, gt=0)
    device_flow_timeout_seconds: int = Field(default=600, gt=0)
    auto_refresh_threshold_seconds: int = Field(default=300, gt=0)


class WebhooksConfig(BaseModel):
    """Webhook receiver configuration.

    Attributes:
        rate_limit_rpm: Max webhook requests per minute per connection.
        replay_window_seconds: Nonce/timestamp dedup window.
        max_payload_bytes: Maximum webhook body size.
        verify_signatures: Require signature verification.
        receipt_retention_days: How long to keep webhook receipts.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    rate_limit_rpm: int = Field(default=100, ge=0)
    replay_window_seconds: int = Field(default=300, gt=0)
    max_payload_bytes: int = Field(default=1_000_000, gt=0)
    verify_signatures: bool = True
    receipt_retention_days: int = Field(default=7, ge=1)


class IntegrationHealthConfig(BaseModel):
    """Health monitoring configuration.

    Attributes:
        check_interval_seconds: Background probe interval.
        unhealthy_threshold: Consecutive failures before ``unhealthy``.
        degraded_threshold: Consecutive failures before ``degraded``.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    check_interval_seconds: int = Field(default=300, gt=0)
    unhealthy_threshold: int = Field(default=3, ge=1)
    degraded_threshold: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate_thresholds(self) -> Self:
        """Ensure ``degraded_threshold`` is not above ``unhealthy_threshold``."""
        if self.degraded_threshold > self.unhealthy_threshold:
            msg = (
                "IntegrationHealthConfig.degraded_threshold "
                f"({self.degraded_threshold}) must be <= "
                f"unhealthy_threshold ({self.unhealthy_threshold})"
            )
            raise ValueError(msg)
        return self


class TunnelConfig(BaseModel):
    """Tunnel configuration for local webhook development.

    Attributes:
        enabled: Whether the tunnel is available.
        auth_token_env: Env var holding the ngrok auth token.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = False
    auth_token_env: str = "NGROK_AUTHTOKEN"  # noqa: S105


class McpCatalogConfig(BaseModel):
    """Bundled MCP server catalog configuration.

    Attributes:
        enabled: Whether the catalog is available.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = True


class IntegrationsConfig(BaseModel):
    """Root integrations subsystem configuration.

    Attributes:
        enabled: Master switch for the integrations layer.
        connections: Connection catalog settings.
        secret_backend: Secret storage backend settings.
        oauth: OAuth 2.1 flow settings.
        webhooks: Webhook receiver settings.
        health: Connection health monitoring settings.
        tunnel: Local-dev tunnel settings.
        mcp_catalog: Bundled MCP server catalog settings.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = True
    connections: ConnectionsConfig = Field(
        default_factory=ConnectionsConfig,
    )
    secret_backend: SecretBackendConfig = Field(
        default_factory=SecretBackendConfig,
    )
    oauth: OAuthConfig = Field(
        default_factory=OAuthConfig,
    )
    webhooks: WebhooksConfig = Field(
        default_factory=WebhooksConfig,
    )
    health: IntegrationHealthConfig = Field(
        default_factory=IntegrationHealthConfig,
    )
    tunnel: TunnelConfig = Field(
        default_factory=TunnelConfig,
    )
    mcp_catalog: McpCatalogConfig = Field(
        default_factory=McpCatalogConfig,
    )
