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

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="schedule_hours",
        type=SettingType.INTEGER,
        default="6",
        description="Interval between scheduled backups in hours",
        group="Schedule",
        min_value=1,
        max_value=168,
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="path",
        type=SettingType.STRING,
        default="/data/backups",
        description="Directory path for storing backups",
        group="General",
        level=SettingLevel.ADVANCED,
        restart_required=True,
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="compression",
        type=SettingType.BOOLEAN,
        default="true",
        description="Compress backups as tar.gz archives",
        group="General",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="on_shutdown",
        type=SettingType.BOOLEAN,
        default="true",
        description="Create a backup on graceful shutdown",
        group="Triggers",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.BACKUP,
        key="on_startup",
        type=SettingType.BOOLEAN,
        default="true",
        description="Create a backup on startup",
        group="Triggers",
    )
)
