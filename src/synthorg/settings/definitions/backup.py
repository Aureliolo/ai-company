"""Backup namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="enabled",
        type=SettingType.BOOLEAN,
        default="false",
        description="Enable automatic backups",
        group="General",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="frequency",
        type=SettingType.ENUM,
        default="daily",
        description="How often to run automatic backups",
        group="Schedule",
        enum_values=("hourly", "daily", "weekly"),
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="retention_days",
        type=SettingType.INTEGER,
        default="30",
        description="Number of days to retain backups",
        group="Schedule",
        level=SettingLevel.ADVANCED,
        min_value=1,
        max_value=365,
    )
)
