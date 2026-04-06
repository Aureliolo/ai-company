"""API namespace setting definitions.

Registers 16 settings covering server, TLS, CORS, rate limiting,
authentication, and setup.  Three are runtime-editable; thirteen are
bootstrap-only (``restart_required=True``) because Litestar bakes
middleware, rate-limit budgets, and CORS into the application at
construction time.
"""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

# ── Server (bootstrap-only) ──────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="server_host",
        type=SettingType.STRING,
        default="127.0.0.1",
        description="Server bind address",
        group="Server",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.server.host",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="server_port",
        type=SettingType.INTEGER,
        default="3001",
        description="Server bind port",
        group="Server",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=1,
        max_value=65535,
        yaml_path="api.server.port",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="api_prefix",
        type=SettingType.STRING,
        default="/api/v1",
        description="URL prefix for all API routes",
        group="Server",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.api_prefix",
    )
)

# ── TLS (bootstrap-only) ────────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="ssl_certfile",
        type=SettingType.STRING,
        default="",
        description="Path to SSL certificate file (PEM format)",
        group="Server",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.server.ssl_certfile",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="ssl_keyfile",
        type=SettingType.STRING,
        default="",
        description="Path to SSL private key file (PEM format)",
        group="Server",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        sensitive=True,
        yaml_path="api.server.ssl_keyfile",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="ssl_ca_certs",
        type=SettingType.STRING,
        default="",
        description="Path to CA bundle for client certificate verification",
        group="Server",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.server.ssl_ca_certs",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="trusted_proxies",
        type=SettingType.JSON,
        default="[]",
        description=(
            "IP addresses/CIDRs trusted as reverse proxies "
            "for X-Forwarded-For/Proto header processing"
        ),
        group="Server",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.server.trusted_proxies",
    )
)

# ── CORS (bootstrap-only) ────────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="cors_allowed_origins",
        type=SettingType.JSON,
        default='["http://localhost:5173"]',
        description="Origins permitted to make cross-origin requests",
        group="CORS",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.cors.allowed_origins",
    )
)

# ── Rate Limiting (exclude_paths: bootstrap-only) ────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="rate_limit_unauth_max_requests",
        type=SettingType.INTEGER,
        default="20",
        description="Maximum unauthenticated requests per time window (by IP)",
        group="Rate Limiting",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=1,
        max_value=10000,
        yaml_path="api.rate_limit.unauth_max_requests",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="rate_limit_auth_max_requests",
        type=SettingType.INTEGER,
        default="6000",
        description="Maximum authenticated requests per time window (by user ID)",
        group="Rate Limiting",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        min_value=1,
        max_value=100000,
        yaml_path="api.rate_limit.auth_max_requests",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="rate_limit_time_unit",
        type=SettingType.ENUM,
        default="minute",
        description="Rate limit time window",
        group="Rate Limiting",
        level=SettingLevel.ADVANCED,
        enum_values=("second", "minute", "hour", "day"),
        yaml_path="api.rate_limit.time_unit",
        restart_required=True,
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="rate_limit_exclude_paths",
        type=SettingType.JSON,
        default='["/api/v1/health"]',
        description="Paths excluded from rate limiting",
        group="Rate Limiting",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.rate_limit.exclude_paths",
    )
)

# ── Authentication (exclude_paths: bootstrap-only) ───────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="jwt_expiry_minutes",
        type=SettingType.INTEGER,
        default="1440",
        description="JWT token lifetime in minutes",
        group="Authentication",
        level=SettingLevel.ADVANCED,
        min_value=1,
        max_value=10080,
        yaml_path="api.auth.jwt_expiry_minutes",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="min_password_length",
        type=SettingType.INTEGER,
        default="12",
        description="Minimum password length for setup and password change",
        group="Authentication",
        min_value=12,
        max_value=128,
        yaml_path="api.auth.min_password_length",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="auth_exclude_paths",
        type=SettingType.JSON,
        default="[]",
        description="Paths excluded from authentication middleware",
        group="Authentication",
        level=SettingLevel.ADVANCED,
        restart_required=True,
        yaml_path="api.auth.exclude_paths",
    )
)

# ── Setup ──────────────────────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.API,
        key="setup_complete",
        type=SettingType.BOOLEAN,
        default="false",
        description="Whether first-run setup has been completed",
        group="Setup",
        level=SettingLevel.ADVANCED,
    )
)
