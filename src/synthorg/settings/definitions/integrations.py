"""Integrations namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.INTEGRATIONS,
        key="health_check_interval_seconds",
        type=SettingType.INTEGER,
        default="300",
        description="Background health check interval in seconds",
        group="Health",
        level=SettingLevel.ADVANCED,
        min_value=30,
        max_value=3600,
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.INTEGRATIONS,
        key="webhook_rate_limit_rpm",
        type=SettingType.INTEGER,
        default="100",
        description="Maximum webhook requests per minute per connection",
        group="Webhooks",
        level=SettingLevel.ADVANCED,
        min_value=0,
        max_value=10000,
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.INTEGRATIONS,
        key="webhook_replay_window_seconds",
        type=SettingType.INTEGER,
        default="300",
        description="Webhook replay protection window in seconds",
        group="Webhooks",
        level=SettingLevel.ADVANCED,
        min_value=60,
        max_value=3600,
    )
)
