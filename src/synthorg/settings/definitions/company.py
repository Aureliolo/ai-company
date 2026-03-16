"""Company namespace setting definitions."""

from synthorg.settings.enums import SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="company_name",
        type=SettingType.STRING,
        default=None,
        description="Company display name",
        group="General",
        yaml_path="company_name",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="autonomy_level",
        type=SettingType.ENUM,
        default="semi",
        description="Default company-wide autonomy level",
        group="General",
        enum_values=(
            "full",
            "semi",
            "supervised",
            "locked",
        ),
        yaml_path="config.autonomy.level",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="graceful_shutdown_seconds",
        type=SettingType.FLOAT,
        default="30.0",
        description="Seconds to wait for cooperative agent exit before force-cancel",
        group="Shutdown",
        min_value=1.0,
        max_value=300.0,
        yaml_path="graceful_shutdown.grace_seconds",
    )
)
