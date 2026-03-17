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
        yaml_path="coordination.topology",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COORDINATION,
        key="max_concurrency_per_wave",
        type=SettingType.INTEGER,
        default="5",
        description="Maximum number of agents in a single execution wave",
        group="General",
        level=SettingLevel.ADVANCED,
        min_value=1,
        max_value=50,
        yaml_path="coordination.max_concurrency_per_wave",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COORDINATION,
        key="fail_fast",
        type=SettingType.BOOLEAN,
        default="false",
        description="Stop on first wave failure instead of continuing",
        group="General",
        yaml_path="coordination.fail_fast",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COORDINATION,
        key="enable_workspace_isolation",
        type=SettingType.BOOLEAN,
        default="true",
        description="Create isolated workspaces for multi-agent execution",
        group="General",
        yaml_path="coordination.enable_workspace_isolation",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.COORDINATION,
        key="base_branch",
        type=SettingType.STRING,
        default="main",
        description="Git branch for workspace isolation",
        group="General",
        yaml_path="coordination.base_branch",
    )
)
