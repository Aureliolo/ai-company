"""Budget namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BUDGET,
        key="total_monthly",
        type=SettingType.FLOAT,
        default="100.0",
        description="Monthly budget in USD",
        group="Limits",
        min_value=0.0,
        yaml_path="budget.total_monthly",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BUDGET,
        key="per_task_limit",
        type=SettingType.FLOAT,
        default="5.0",
        description="Maximum USD per task",
        group="Limits",
        min_value=0.0,
        yaml_path="budget.per_task_limit",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BUDGET,
        key="per_agent_daily_limit",
        type=SettingType.FLOAT,
        default="10.0",
        description="Maximum USD per agent per day",
        group="Limits",
        min_value=0.0,
        yaml_path="budget.per_agent_daily_limit",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BUDGET,
        key="auto_downgrade_enabled",
        type=SettingType.BOOLEAN,
        default="false",
        description="Enable automatic model downgrade when budget is low",
        group="Auto-Downgrade",
        level=SettingLevel.ADVANCED,
        yaml_path="budget.auto_downgrade.enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BUDGET,
        key="auto_downgrade_threshold",
        type=SettingType.INTEGER,
        default="85",
        description="Budget usage percent that triggers model downgrade",
        group="Auto-Downgrade",
        level=SettingLevel.ADVANCED,
        min_value=0,
        max_value=100,
        yaml_path="budget.auto_downgrade.threshold",
    )
)
