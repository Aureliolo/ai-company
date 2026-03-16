"""Memory namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.MEMORY,
        key="backend",
        type=SettingType.STRING,
        default="mem0",
        description="Memory backend implementation",
        group="General",
        restart_required=True,
        yaml_path="memory.backend",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.MEMORY,
        key="default_level",
        type=SettingType.ENUM,
        default="persistent",
        description="Default memory persistence level for agents",
        group="General",
        enum_values=("none", "session", "persistent"),
        yaml_path="memory.default_level",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.MEMORY,
        key="consolidation_interval",
        type=SettingType.ENUM,
        default="daily",
        description="How often to consolidate and archive memories",
        group="Maintenance",
        level=SettingLevel.ADVANCED,
        enum_values=("hourly", "daily", "weekly"),
        yaml_path="memory.consolidation_interval",
    )
)
