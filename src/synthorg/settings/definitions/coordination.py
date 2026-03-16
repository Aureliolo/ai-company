"""Coordination namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COORDINATION,
        key="default_topology",
        type=SettingType.ENUM,
        default="auto",
        description="Default coordination topology for multi-agent tasks",
        group="General",
        enum_values=(
            "auto",
            "single_agent_sequential",
            "centralized",
            "decentralized",
            "context_dependent",
        ),
        yaml_path="coordination.default_topology",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COORDINATION,
        key="max_wave_size",
        type=SettingType.INTEGER,
        default="5",
        description="Maximum number of agents in a single execution wave",
        group="General",
        level=SettingLevel.ADVANCED,
        min_value=1,
        max_value=50,
        yaml_path="coordination.max_wave_size",
    )
)
