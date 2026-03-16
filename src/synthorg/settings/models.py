"""Domain models for the settings persistence layer."""

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.settings.enums import (
    SettingLevel,
    SettingNamespace,
    SettingSource,
    SettingType,
)


class SettingDefinition(BaseModel):
    """Metadata for a single registered setting.

    Drives validation, UI generation, and schema introspection.
    All values are stored as strings; ``type`` controls coercion.

    Attributes:
        namespace: Setting namespace (subsystem grouping).
        key: Setting key within the namespace.
        type: Data type for validation and coercion.
        default: Default value serialised as a string, or ``None``.
        description: Human-readable description.
        group: UI grouping label (e.g. ``"Limits"``).
        level: Visibility level for progressive disclosure.
        sensitive: Whether the value should be encrypted at rest.
        restart_required: Whether changes require a restart.
        enum_values: Allowed values when ``type`` is ``ENUM``.
        validator_pattern: Regex pattern for string validation.
        min_value: Minimum for numeric types (inclusive).
        max_value: Maximum for numeric types (inclusive).
        yaml_path: Dotted path into ``RootConfig`` for YAML resolution.
    """

    model_config = ConfigDict(frozen=True)

    namespace: SettingNamespace = Field(description="Setting namespace")
    key: NotBlankStr = Field(description="Setting key within namespace")
    type: SettingType = Field(description="Value data type")
    default: str | None = Field(
        default=None,
        description="Default value as string",
    )
    description: NotBlankStr = Field(description="Human-readable description")
    group: NotBlankStr = Field(description="UI grouping label")
    level: SettingLevel = Field(
        default=SettingLevel.BASIC,
        description="Visibility level",
    )
    sensitive: bool = Field(
        default=False,
        description="Encrypt at rest and mask in UI",
    )
    restart_required: bool = Field(
        default=False,
        description="Change takes effect after restart",
    )
    enum_values: tuple[str, ...] = Field(
        default=(),
        description="Allowed values for ENUM type",
    )
    validator_pattern: NotBlankStr | None = Field(
        default=None,
        description="Regex pattern for string validation",
    )
    min_value: float | None = Field(
        default=None,
        description="Minimum value for numeric types",
    )
    max_value: float | None = Field(
        default=None,
        description="Maximum value for numeric types",
    )
    yaml_path: NotBlankStr | None = Field(
        default=None,
        description="Dotted path into RootConfig for YAML resolution",
    )

    @model_validator(mode="after")
    def _check_cross_field_constraints(self) -> SettingDefinition:
        """Validate cross-field invariants at construction time."""
        if self.type == SettingType.ENUM and not self.enum_values:
            msg = (
                f"ENUM setting {self.namespace}/{self.key}"
                f" requires non-empty enum_values"
            )
            raise ValueError(msg)
        if self.min_value is not None and self.type not in (
            SettingType.INTEGER,
            SettingType.FLOAT,
        ):
            msg = f"min_value is only valid for INTEGER/FLOAT, not {self.type}"
            raise ValueError(msg)
        if self.max_value is not None and self.type not in (
            SettingType.INTEGER,
            SettingType.FLOAT,
        ):
            msg = f"max_value is only valid for INTEGER/FLOAT, not {self.type}"
            raise ValueError(msg)
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            msg = f"min_value ({self.min_value}) exceeds max_value ({self.max_value})"
            raise ValueError(msg)
        if self.validator_pattern is not None:
            try:
                re.compile(self.validator_pattern)
            except re.error as exc:
                msg = f"Invalid validator_pattern: {exc}"
                raise ValueError(msg) from exc
        return self


class SettingValue(BaseModel):
    """A resolved setting value with its origin.

    Attributes:
        namespace: Setting namespace.
        key: Setting key.
        value: Resolved value as a string.
        source: Where the value came from.
        updated_at: ISO 8601 timestamp for DB-sourced values.
    """

    model_config = ConfigDict(frozen=True)

    namespace: SettingNamespace = Field(description="Setting namespace")
    key: NotBlankStr = Field(description="Setting key")
    value: str = Field(description="Resolved value as string")
    source: SettingSource = Field(description="Value origin")
    updated_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp (DB values only)",
    )


class SettingEntry(BaseModel):
    """Combined view of a setting definition and its resolved value.

    Used by the API to return full setting information in a
    single response object.

    Attributes:
        definition: Setting metadata.
        value: Resolved value as a string.
        source: Where the value came from.
        updated_at: ISO 8601 timestamp for DB-sourced values.
    """

    model_config = ConfigDict(frozen=True)

    definition: SettingDefinition = Field(description="Setting metadata")
    value: str = Field(description="Resolved value as string")
    source: SettingSource = Field(description="Value origin")
    updated_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp (DB values only)",
    )
