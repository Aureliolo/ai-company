"""Engine namespace setting definitions."""

from synthorg.settings.enums import SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.ENGINE,
        key="personality_trimming_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description=(
            "Enable token-based personality trimming when section exceeds budget"
        ),
        group="Personality Trimming",
        yaml_path="engine.personality_trimming_enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.ENGINE,
        key="personality_max_tokens_override",
        type=SettingType.INTEGER,
        default="0",
        description=(
            "Global override for personality section token limit "
            "(0 = use profile defaults per tier: large=500, medium=200, small=80)"
        ),
        group="Personality Trimming",
        min_value=0,
        max_value=10000,
        yaml_path="engine.personality_max_tokens_override",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.ENGINE,
        key="personality_trimming_notify",
        type=SettingType.BOOLEAN,
        default="true",
        description=(
            "Publish a WebSocket notification on the agents channel "
            "when personality trimming activates for an agent"
        ),
        group="Personality Trimming",
        yaml_path="engine.personality_trimming_notify",
    )
)
