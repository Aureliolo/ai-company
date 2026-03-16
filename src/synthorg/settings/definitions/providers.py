"""Providers namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.PROVIDERS,
        key="default_provider",
        type=SettingType.STRING,
        default=None,
        description="Default LLM provider name for new tasks",
        group="General",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.PROVIDERS,
        key="routing_strategy",
        type=SettingType.ENUM,
        default="cost_aware",
        description="Model routing strategy",
        group="Routing",
        enum_values=(
            "cost_aware",
            "latency_aware",
            "round_robin",
            "priority_chain",
            "capability_match",
        ),
        yaml_path="routing.strategy",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.PROVIDERS,
        key="retry_max_attempts",
        type=SettingType.INTEGER,
        default="3",
        description="Maximum retry attempts for transient provider errors",
        group="Resilience",
        level=SettingLevel.ADVANCED,
        min_value=1,
        max_value=10,
    )
)
