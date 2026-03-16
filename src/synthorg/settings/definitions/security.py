"""Security namespace setting definitions."""

from synthorg.settings.enums import SettingLevel, SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.SECURITY,
        key="enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description="Master switch for the security subsystem",
        group="General",
        yaml_path="security.enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.SECURITY,
        key="audit_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description="Whether to record security audit entries",
        group="General",
        yaml_path="security.audit_enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.SECURITY,
        key="post_tool_scanning_enabled",
        type=SettingType.BOOLEAN,
        default="true",
        description="Scan tool output for secrets and sensitive data",
        group="Output Scanning",
        level=SettingLevel.ADVANCED,
        yaml_path="security.post_tool_scanning_enabled",
    )
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.SECURITY,
        key="output_scan_policy_type",
        type=SettingType.ENUM,
        default="autonomy_tiered",
        description="Response policy when output scan detects sensitive content",
        group="Output Scanning",
        level=SettingLevel.ADVANCED,
        enum_values=("redact", "withhold", "log_only", "autonomy_tiered"),
        yaml_path="security.output_scan_policy_type",
    )
)
