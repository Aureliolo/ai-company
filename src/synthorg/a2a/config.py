"""A2A external gateway configuration."""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class A2AAuthConfig(BaseModel):
    """Authentication configuration for A2A inbound/outbound.

    Credentials themselves are stored in the connection catalog
    via ``a2a_peer`` connections.  This config controls *which*
    scheme is used by default.

    Attributes:
        inbound_scheme: Default auth scheme for inbound requests.
        outbound_scheme: Default auth scheme for outbound requests.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    inbound_scheme: str = Field(
        default="api_key",
        description=(
            "Default inbound auth scheme (api_key, oauth2, bearer, mtls, none)"
        ),
    )
    outbound_scheme: str = Field(
        default="bearer",
        description=("Default outbound auth scheme (api_key, oauth2, bearer, mtls)"),
    )


class A2APushConfig(BaseModel):
    """Push notification configuration.

    Push events arrive at the unified webhook receiver
    (``/api/v1/webhooks/{connection_name}/a2a_push``).

    Attributes:
        enabled: Whether push notifications are accepted.
        signature_algorithm: HMAC algorithm for push signature
            verification.
        clock_skew_seconds: Maximum clock skew tolerance for
            timestamp validation.
        replay_window_seconds: Deduplication window for replay
            protection.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = False
    signature_algorithm: str = Field(
        default="hmac-sha256",
        description="HMAC algorithm for push signature verification",
    )
    clock_skew_seconds: int = Field(
        default=300,
        ge=0,
        description="Maximum clock skew tolerance in seconds",
    )
    replay_window_seconds: int = Field(
        default=60,
        ge=0,
        description="Deduplication window for replay protection",
    )


class A2AAgentCardVerificationConfig(BaseModel):
    """Agent Card signature verification configuration.

    Attributes:
        enabled: Whether to verify Agent Card signatures.
        require_signatures: Reject unsigned cards when enabled.
        trusted_jwks_urls: JWKS endpoints for signature key
            discovery.
        trusted_public_keys: PEM-encoded public keys for direct
            verification.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = False
    require_signatures: bool = False
    trusted_jwks_urls: tuple[str, ...] = ()
    trusted_public_keys: tuple[str, ...] = ()


class A2AConfig(BaseModel):
    """Top-level A2A external gateway configuration.

    The gateway is disabled by default (``enabled = False``).
    When disabled, no routes are mounted and zero overhead is
    incurred.

    Attributes:
        enabled: Master switch for the A2A gateway.
        allowed_peers: Explicit peer allowlist.  Inbound requests
            from peers not in this list are rejected.  Empty tuple
            means no peers are allowed (even when enabled).
        rate_limit_per_peer_rpm: Maximum requests per minute per
            a2a_peer connection.
        sse_idle_timeout_seconds: SSE stream idle timeout before
            automatic disconnect.
        max_request_body_bytes: Maximum inbound JSON-RPC request
            body size.
        agent_card_cache_ttl_seconds: TTL for cached Agent Cards
            (0 disables caching).
        auth: Authentication scheme configuration.
        push: Push notification configuration.
        agent_card_verification: Agent Card signature verification.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = False
    allowed_peers: tuple[NotBlankStr, ...] = ()
    rate_limit_per_peer_rpm: int = Field(
        default=100,
        ge=1,
        description="Maximum requests per minute per a2a_peer",
    )
    sse_idle_timeout_seconds: int = Field(
        default=300,
        ge=30,
        description="SSE stream idle timeout in seconds",
    )
    max_request_body_bytes: int = Field(
        default=1_048_576,
        ge=1024,
        description="Maximum inbound request body size (bytes)",
    )
    agent_card_cache_ttl_seconds: int = Field(
        default=60,
        ge=0,
        description="Agent Card cache TTL (0 = no caching)",
    )
    auth: A2AAuthConfig = Field(
        default_factory=A2AAuthConfig,
        description="Authentication scheme configuration",
    )
    push: A2APushConfig = Field(
        default_factory=A2APushConfig,
        description="Push notification configuration",
    )
    agent_card_verification: A2AAgentCardVerificationConfig = Field(
        default_factory=A2AAgentCardVerificationConfig,
        description="Agent Card signature verification",
    )
