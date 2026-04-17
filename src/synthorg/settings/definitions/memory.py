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
        enum_values=("none", "session", "project", "persistent"),
        yaml_path="memory.level",
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
        enum_values=("hourly", "daily", "weekly", "never"),
        yaml_path="memory.consolidation_interval",
    )
)

# ── Embedding overrides (advanced) ───────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.MEMORY,
        key="embedder_provider",
        type=SettingType.STRING,
        default=None,
        description="Override embedding provider (advanced)",
        group="Embedding",
        level=SettingLevel.ADVANCED,
        yaml_path="memory.embedder.provider",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.MEMORY,
        key="embedder_model",
        type=SettingType.STRING,
        default=None,
        description="Override embedding model (advanced)",
        group="Embedding",
        level=SettingLevel.ADVANCED,
        yaml_path="memory.embedder.model",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.MEMORY,
        key="embedder_dims",
        type=SettingType.INTEGER,
        default=None,
        description="Override embedding vector dimensions (advanced)",
        group="Embedding",
        level=SettingLevel.ADVANCED,
        min_value=1,
        yaml_path="memory.embedder.dims",
    )
)

# ── Consolidation batch size ─────────────────────────────────────

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.MEMORY,
        key="consolidation_enforce_batch_size",
        type=SettingType.INTEGER,
        default="1000",
        description=(
            "Number of memory records evicted per batch when enforcing"
            " the max-memories cap during consolidation"
        ),
        group="Maintenance",
        level=SettingLevel.ADVANCED,
        min_value=100,
        max_value=10_000,
        yaml_path="memory.consolidation_enforce_batch_size",
    )
)
