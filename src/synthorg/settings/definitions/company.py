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
        key="description",
        type=SettingType.STRING,
        default=None,
        description="Company description",
        group="General",
        yaml_path="description",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="autonomy_level",
        type=SettingType.ENUM,
        default="supervised",
        description=(
            "Default company-wide autonomy level. Fresh installs ship with"
            " 'supervised' so most state-mutating agent actions queue for"
            " approval before execution; raise to 'semi' or 'full' once"
            " operators trust the organization. Rank: full > semi >"
            " supervised > locked."
        ),
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

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="name_locales",
        type=SettingType.JSON,
        default='["__all__"]',
        description=(
            "Faker locales for agent name generation. "
            'Use ["__all__"] for all Latin-script locales or a list of '
            'locale codes (e.g. ["en_US", "fr_FR", "de_DE"]).'
        ),
        group="Names",
        yaml_path="name_locales",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="agents",
        type=SettingType.JSON,
        default=None,
        description="Agent configurations (JSON array of AgentConfig objects)",
        group="Structure",
        yaml_path="agents",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="departments",
        type=SettingType.JSON,
        default=None,
        description="Department hierarchy (JSON array of Department objects)",
        group="Structure",
        yaml_path="departments",
    )
)
