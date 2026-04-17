"""Engine namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
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

# ── Approval gate ────────────────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.ENGINE,
        key="approval_interrupt_timeout_seconds",
        type=SettingType.FLOAT,
        default="300.0",
        description=(
            "How long an approval gate waits for a human decision before"
            " the task is interrupted"
        ),
        group="Approval Gate",
        level=SettingLevel.ADVANCED,
        min_value=30.0,
        max_value=3600.0,
        yaml_path="engine.approval_interrupt_timeout_seconds",
    )
)

# ── Health judge ────────────────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.ENGINE,
        key="health_quality_degradation_threshold",
        type=SettingType.INTEGER,
        default="3",
        description=(
            "Number of consecutive INCORRECT steps before the health judge"
            " escalates a quality-degradation signal"
        ),
        group="Health",
        level=SettingLevel.ADVANCED,
        min_value=1,
        max_value=10,
        yaml_path="engine.health_quality_degradation_threshold",
    )
)
