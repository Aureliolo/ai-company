"""Company namespace setting definitions."""

from synthorg.core.enums import AutonomyLevel
from synthorg.security.autonomy.models import AutonomyConfig
from synthorg.settings.enums import SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

# Safety net: the SettingDefinition default below and
# :attr:`AutonomyConfig.level`'s default must agree, otherwise a fresh
# install resolves autonomy differently depending on which side read the
# value first.  Fail loudly at import time if the two ever drift.
_AUTONOMY_DEFAULT_STR = AutonomyConfig.model_fields["level"].default
assert isinstance(_AUTONOMY_DEFAULT_STR, AutonomyLevel), (  # noqa: S101
    "AutonomyConfig.level default must be an AutonomyLevel enum"
)
_EXPECTED_AUTONOMY_DEFAULT = _AUTONOMY_DEFAULT_STR.value

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

assert _EXPECTED_AUTONOMY_DEFAULT == "supervised", (  # noqa: S101
    "AutonomyConfig.level default drifted from the 'autonomy_level' "
    "SettingDefinition default; update both in lockstep."
)
_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COMPANY,
        key="autonomy_level",
        type=SettingType.ENUM,
        default=_EXPECTED_AUTONOMY_DEFAULT,
        description=(
            "Default company-wide autonomy level. Fresh installs ship with"
            " 'supervised' so most state-mutating agent actions queue for"
            " approval before execution; raise to 'semi' or 'full' once"
            " operators trust the organization. Rank: full > semi >"
            " supervised > locked."
        ),
        group="General",
        enum_values=tuple(level.value for level in AutonomyLevel),
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
