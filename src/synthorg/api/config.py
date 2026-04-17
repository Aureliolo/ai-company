"""API configuration models.

Frozen Pydantic models for CORS, rate limiting, server,
authentication, and the top-level ``ApiConfig`` that aggregates
them all.
"""

import ipaddress
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.api.auth.config import AuthConfig
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_NETWORK_EXPOSURE_WARNING,
)

logger = get_logger(__name__)


class CorsConfig(BaseModel):
    """CORS configuration for the API.

    Attributes:
        allowed_origins: Origins permitted to make cross-origin requests.
        allow_methods: HTTP methods permitted in cross-origin requests.
        allow_headers: Headers permitted in cross-origin requests.
        allow_credentials: Whether credentials (cookies, auth) are
            allowed in cross-origin requests.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    # Default targets the Vite dev server; production deployments
    # override via the settings registry (``api.cors_allowed_origins``
    # in ``src/synthorg/settings/definitions/api.py``).
    allowed_origins: tuple[str, ...] = Field(
        default=("http://localhost:5173",),
        description="Origins permitted to make cross-origin requests",
    )
    allow_methods: tuple[str, ...] = Field(
        default=("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"),
        description="HTTP methods permitted in cross-origin requests",
    )
    allow_headers: tuple[str, ...] = Field(
        default=("Content-Type", "Authorization", "X-CSRF-Token"),
        description="Headers permitted in cross-origin requests",
    )
    allow_credentials: bool = Field(
        default=True,
        description="Whether credentials (cookies) are allowed",
    )

    @model_validator(mode="after")
    def _validate_wildcard_credentials(self) -> Self:
        """Reject ``*`` origin with ``allow_credentials=True``.

        Browsers reject ``Access-Control-Allow-Origin: *`` combined
        with ``Access-Control-Allow-Credentials: true``.
        """
        if self.allow_credentials and "*" in self.allowed_origins:
            msg = (
                "allow_credentials=True is incompatible with "
                "allowed_origins containing '*'"
            )
            raise ValueError(msg)
        return self


class RateLimitTimeUnit(StrEnum):
    """Valid time windows for rate limiting."""

    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class RateLimitConfig(BaseModel):
    """API rate limiting configuration.

    Supports two tiers stacked around the auth middleware:

    - **Unauthenticated**: applied before auth, keyed by client IP.
    - **Authenticated**: applied after auth, keyed by user ID.

    This prevents multi-user deployments behind a shared gateway
    from collectively exhausting a single per-IP budget.

    Attributes:
        unauth_max_requests: Maximum unauthenticated requests per
            time window (by IP).
        auth_max_requests: Maximum authenticated requests per time
            window (by user ID).
        time_unit: Time window (``second``, ``minute``, ``hour``,
            ``day``).
        exclude_paths: Paths excluded from rate limiting.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    unauth_max_requests: int = Field(
        default=20,
        ge=1,
        description="Maximum unauthenticated requests per time window (by IP)",
    )
    auth_max_requests: int = Field(
        default=6000,
        ge=1,
        description="Maximum authenticated requests per time window (by user ID)",
    )
    time_unit: RateLimitTimeUnit = Field(
        default=RateLimitTimeUnit.MINUTE,
        description="Time window (second, minute, hour, day)",
    )
    exclude_paths: tuple[str, ...] = Field(
        default=("/api/v1/health",),
        description="Paths excluded from rate limiting",
    )
    max_rpm_default: int = Field(
        default=60,
        ge=1,
        le=100_000,
        description=(
            "Fallback requests-per-minute applied to per-connection"
            " coordinators when the catalog does not provide a limiter"
            " (mirrors the api.max_rpm_default setting; restart required)"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_max_requests(cls, data: Any) -> Any:
        """Reject the removed ``max_requests`` field with guidance."""
        if isinstance(data, dict) and "max_requests" in data:
            msg = (
                "'max_requests' was replaced by 'unauth_max_requests' "
                "and 'auth_max_requests' in v0.6.3"
            )
            raise ValueError(msg)
        return data


class ServerConfig(BaseModel):
    """Uvicorn server configuration.

    Attributes:
        host: Bind address.
        port: Bind port.
        reload: Enable auto-reload for development.
        workers: Number of worker processes.
        ws_ping_interval: WebSocket ping interval in seconds
            (0 to disable).
        ws_ping_timeout: WebSocket pong timeout in seconds.
        ssl_certfile: Path to SSL certificate file (PEM format).
        ssl_keyfile: Path to SSL private key file (PEM format).
        ssl_ca_certs: Path to CA bundle for client cert
            verification.
        trusted_proxies: IP addresses/CIDRs trusted as reverse
            proxies for ``X-Forwarded-For``/``X-Forwarded-Proto``
            header processing.
        compression_minimum_size_bytes: Minimum response body size
            in bytes before brotli compression kicks in. Mirrors the
            ``api.compression_minimum_size_bytes`` setting (restart
            required); the API startup hook resolves the current
            value and threads it in here so operator tuning via the
            settings database takes effect on next boot.
        request_max_body_size_bytes: Maximum accepted HTTP request
            body size in bytes. Mirrors the
            ``api.request_max_body_size_bytes`` setting (restart
            required); populated the same way as
            ``compression_minimum_size_bytes``.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    host: str = Field(
        default="127.0.0.1",
        description="Bind address",
    )
    port: int = Field(
        default=3001,
        ge=1,
        le=65535,
        description="Bind port",
    )
    reload: bool = Field(
        default=False,
        description="Enable auto-reload for development",
    )
    workers: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Number of worker processes",
    )
    ws_ping_interval: float = Field(
        default=20.0,
        ge=0,
        description="WebSocket ping interval in seconds (0 to disable)",
    )
    ws_ping_timeout: float = Field(
        default=20.0,
        ge=0,
        description="WebSocket pong timeout in seconds",
    )
    ssl_certfile: str | None = Field(
        default=None,
        description="Path to SSL certificate file (PEM format)",
    )
    ssl_keyfile: str | None = Field(
        default=None,
        description="Path to SSL private key file (PEM format)",
    )
    ssl_ca_certs: str | None = Field(
        default=None,
        description=("Path to CA bundle for client certificate verification"),
    )
    trusted_proxies: tuple[str, ...] = Field(
        default=(),
        description=(
            "IP addresses/CIDRs trusted as reverse proxies "
            "for X-Forwarded-For/Proto header processing"
        ),
    )
    compression_minimum_size_bytes: int = Field(
        default=1000,
        ge=100,
        le=10_000,
        description=(
            "Minimum response body size in bytes before brotli compression"
            " is applied (mirrors the api.compression_minimum_size_bytes"
            " setting; restart required)"
        ),
    )
    request_max_body_size_bytes: int = Field(
        default=52_428_800,
        ge=1_000_000,
        le=536_870_912,
        description=(
            "Maximum accepted HTTP request body size in bytes (mirrors"
            " the api.request_max_body_size_bytes setting; restart"
            " required)"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_empty_tls(cls, data: dict[str, object]) -> dict[str, object]:
        """Normalize empty-string TLS paths to ``None``."""
        if isinstance(data, dict):
            for key in ("ssl_certfile", "ssl_keyfile", "ssl_ca_certs"):
                val = data.get(key)
                if isinstance(val, str) and not val.strip():
                    data[key] = None
        return data

    @model_validator(mode="after")
    def _validate_tls_pair(self) -> Self:
        """Require both cert and key when either is set."""
        has_cert = self.ssl_certfile is not None
        has_key = self.ssl_keyfile is not None
        has_ca = self.ssl_ca_certs is not None

        if has_cert and not has_key:
            msg = "ssl_keyfile is required when ssl_certfile is set"
            raise ValueError(msg)
        if has_key and not has_cert:
            msg = "ssl_certfile is required when ssl_keyfile is set"
            raise ValueError(msg)
        if has_ca and not has_cert:
            msg = "ssl_certfile is required when ssl_ca_certs is set"
            raise ValueError(msg)

        # Validate trusted_proxies as valid IP/CIDR entries.
        for entry in self.trusted_proxies:
            try:
                network = ipaddress.ip_network(entry, strict=False)
            except ValueError:
                msg = (
                    f"Invalid trusted_proxies entry: {entry!r} "
                    f"(must be an IP address or CIDR notation)"
                )
                raise ValueError(msg) from None
            if network.prefixlen == 0:
                msg = (
                    f"Overly broad trusted_proxies entry: {entry!r} "
                    f"trusts all addresses -- use specific IPs/CIDRs"
                )
                raise ValueError(msg)

        _wildcard_hosts = {"0.0.0.0", "::"}  # noqa: S104
        if self.host in _wildcard_hosts and not has_cert and not self.trusted_proxies:
            logger.warning(
                API_NETWORK_EXPOSURE_WARNING,
                host=self.host,
                note=(
                    "Server binds to all interfaces without TLS "
                    "or trusted proxy configuration"
                ),
            )

        return self


class ApiConfig(BaseModel):
    """Top-level API configuration aggregating all sub-configs.

    Attributes:
        cors: CORS configuration.
        rate_limit: Rate limiting configuration.
        server: Uvicorn server configuration.
        auth: Authentication configuration.
        api_prefix: URL prefix for all API routes.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    cors: CorsConfig = Field(
        default_factory=CorsConfig,
        description="CORS configuration",
    )
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting configuration",
    )
    server: ServerConfig = Field(
        default_factory=ServerConfig,
        description="Uvicorn server configuration",
    )
    auth: AuthConfig = Field(
        default_factory=AuthConfig,
        description="Authentication configuration",
    )
    api_prefix: NotBlankStr = Field(
        default="/api/v1",
        description="URL prefix for all API routes",
    )
