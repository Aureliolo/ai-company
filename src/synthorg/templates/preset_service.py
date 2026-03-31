"""Service layer for personality preset discovery and CRUD.

Merges builtin presets (from code) with user-defined custom presets
(from persistence) behind a single async interface.
"""

import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from synthorg.api.errors import (
    ApiValidationError,
    ConflictError,
    NotFoundError,
)
from synthorg.core.agent import PersonalityConfig
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.preset import (
    PRESET_CONFLICT,
    PRESET_CREATED,
    PRESET_DELETED,
    PRESET_NOT_FOUND,
    PRESET_UPDATED,
    PRESET_VALIDATION_FAILED,
)
from synthorg.persistence.preset_repository import (
    PersonalityPresetRepository,  # noqa: TC001
)
from synthorg.templates.presets import PERSONALITY_PRESETS

logger = get_logger(__name__)

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class PresetEntry(BaseModel):
    """A personality preset with source metadata.

    Attributes:
        name: Lowercase preset identifier.
        source: Whether the preset is builtin or user-defined.
        config: Full personality configuration as a dict.
        description: Human-readable description.
        created_at: ISO 8601 creation timestamp (None for builtins).
        updated_at: ISO 8601 last-update timestamp (None for builtins).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: NotBlankStr
    source: Literal["builtin", "custom"]
    config: dict[str, Any]
    description: str = ""
    created_at: str | None = None
    updated_at: str | None = None


def _builtin_to_entry(name: str, preset: dict[str, Any]) -> PresetEntry:
    """Convert a builtin preset dict to a PresetEntry."""
    return PresetEntry(
        name=NotBlankStr(name),
        source="builtin",
        config=dict(preset),
        description=str(preset.get("description", "")),
    )


def _normalize_preset_name(raw: str) -> str:
    """Normalize a preset name to lowercase with whitespace stripped.

    Args:
        raw: Raw name input.

    Returns:
        Normalized lowercase name.

    Raises:
        ApiValidationError: If the name is empty or has invalid format.
    """
    name = raw.strip().lower()
    if not name:
        logger.warning(
            PRESET_VALIDATION_FAILED,
            raw_name=raw,
            reason="blank",
        )
        msg = "Preset name must not be blank"
        raise ApiValidationError(msg)
    if not _NAME_PATTERN.match(name):
        logger.warning(
            PRESET_VALIDATION_FAILED,
            raw_name=raw,
            normalized=name,
            reason="invalid_format",
        )
        msg = (
            f"Invalid preset name {name!r}. "
            "Must match [a-z][a-z0-9_]* (lowercase, underscores only)."
        )
        raise ApiValidationError(msg)
    return name


def _validate_personality_config(
    config: dict[str, Any],
) -> PersonalityConfig:
    """Validate a config dict against PersonalityConfig.

    Args:
        config: Raw personality configuration fields.

    Returns:
        Validated PersonalityConfig instance.

    Raises:
        ApiValidationError: If validation fails.
    """
    try:
        return PersonalityConfig(**config)
    except ValidationError as exc:
        logger.warning(
            PRESET_VALIDATION_FAILED,
            reason="invalid_config",
            error=str(exc),
        )
        msg = f"Invalid personality configuration: {exc}"
        raise ApiValidationError(msg) from exc


class PersonalityPresetService:
    """Merges builtin and custom presets behind one async interface.

    Args:
        repository: Persistence layer for custom presets.
    """

    def __init__(self, repository: PersonalityPresetRepository) -> None:
        self._repo = repository

    async def list_all(self) -> tuple[PresetEntry, ...]:
        """Return all presets (builtin + custom), sorted by name.

        Returns:
            Tuple of preset entries tagged with their source.
        """
        entries: dict[str, PresetEntry] = {}

        for name, preset in PERSONALITY_PRESETS.items():
            entries[name] = _builtin_to_entry(name, dict(preset))

        for (
            name,
            config_json,
            description,
            created_at,
            updated_at,
        ) in await self._repo.list_all():
            entries[name] = PresetEntry(
                name=NotBlankStr(name),
                source="custom",
                config=json.loads(config_json),
                description=description,
                created_at=created_at,
                updated_at=updated_at,
            )

        return tuple(entries[k] for k in sorted(entries))

    async def get(self, name: str) -> PresetEntry:
        """Look up a preset by name (case-insensitive).

        Checks custom presets first, then builtins.

        Args:
            name: Preset identifier.

        Returns:
            The matching preset entry.

        Raises:
            NotFoundError: If no preset with this name exists.
        """
        key = name.strip().lower()
        if not key:
            logger.warning(PRESET_NOT_FOUND, preset_name=name, reason="blank")
            msg = f"Personality preset {name!r} not found"
            raise NotFoundError(msg)

        row = await self._repo.get(NotBlankStr(key))
        if row is not None:
            config_json, description, created_at, updated_at = row
            return PresetEntry(
                name=NotBlankStr(key),
                source="custom",
                config=json.loads(config_json),
                description=description,
                created_at=created_at,
                updated_at=updated_at,
            )

        if key in PERSONALITY_PRESETS:
            return _builtin_to_entry(key, dict(PERSONALITY_PRESETS[key]))

        logger.warning(PRESET_NOT_FOUND, preset_name=key)
        msg = f"Personality preset {name!r} not found"
        raise NotFoundError(msg)

    async def create(
        self,
        name: str,
        config: dict[str, Any],
    ) -> PresetEntry:
        """Create a new custom preset.

        Args:
            name: Preset identifier (normalized to lowercase).
            config: Personality configuration fields.

        Returns:
            The created preset entry.

        Raises:
            ConflictError: If name shadows a builtin preset.
            ApiValidationError: If name format or config is invalid.
        """
        key = _normalize_preset_name(name)

        if key in PERSONALITY_PRESETS:
            logger.warning(
                PRESET_CONFLICT,
                preset_name=key,
                reason="shadows_builtin",
            )
            msg = (
                f"Cannot create custom preset {key!r}: "
                "name conflicts with a builtin preset"
            )
            raise ConflictError(msg)

        existing = await self._repo.get(NotBlankStr(key))
        if existing is not None:
            logger.warning(
                PRESET_CONFLICT,
                preset_name=key,
                reason="already_exists",
            )
            msg = f"Custom preset {key!r} already exists"
            raise ConflictError(msg)

        validated = _validate_personality_config(config)
        config_json = json.dumps(validated.model_dump(mode="json"), sort_keys=True)
        description = str(config.get("description", ""))
        now = datetime.now(UTC).isoformat()

        await self._repo.save(NotBlankStr(key), config_json, description, now, now)
        logger.info(PRESET_CREATED, preset_name=key)

        return PresetEntry(
            name=NotBlankStr(key),
            source="custom",
            config=validated.model_dump(mode="json"),
            description=description,
            created_at=now,
            updated_at=now,
        )

    async def update(
        self,
        name: str,
        config: dict[str, Any],
    ) -> PresetEntry:
        """Update an existing custom preset.

        Args:
            name: Preset identifier.
            config: Updated personality configuration fields.

        Returns:
            The updated preset entry.

        Raises:
            ConflictError: If name is a builtin preset.
            NotFoundError: If no custom preset with this name exists.
            ApiValidationError: If name or config is invalid.
        """
        key = _normalize_preset_name(name)

        if key in PERSONALITY_PRESETS:
            logger.warning(
                PRESET_CONFLICT,
                preset_name=key,
                reason="update_builtin",
            )
            msg = f"Cannot update builtin preset {key!r}"
            raise ConflictError(msg)

        existing = await self._repo.get(NotBlankStr(key))
        if existing is None:
            logger.warning(
                PRESET_NOT_FOUND,
                preset_name=key,
                operation="update",
            )
            msg = f"Custom preset {name!r} not found"
            raise NotFoundError(msg)

        validated = _validate_personality_config(config)
        config_json = json.dumps(validated.model_dump(mode="json"), sort_keys=True)
        description = str(config.get("description", ""))
        _, _, created_at, _ = existing
        now = datetime.now(UTC).isoformat()

        await self._repo.save(
            NotBlankStr(key),
            config_json,
            description,
            created_at,
            now,
        )
        logger.info(PRESET_UPDATED, preset_name=key)

        return PresetEntry(
            name=NotBlankStr(key),
            source="custom",
            config=validated.model_dump(mode="json"),
            description=description,
            created_at=created_at,
            updated_at=now,
        )

    async def delete(self, name: str) -> None:
        """Delete a custom preset.

        Args:
            name: Preset identifier.

        Raises:
            ConflictError: If name is a builtin preset.
            NotFoundError: If no custom preset with this name exists.
            ApiValidationError: If name format is invalid.
        """
        key = _normalize_preset_name(name)

        if key in PERSONALITY_PRESETS:
            logger.warning(
                PRESET_CONFLICT,
                preset_name=key,
                reason="delete_builtin",
            )
            msg = f"Cannot delete builtin preset {key!r}"
            raise ConflictError(msg)

        deleted = await self._repo.delete(NotBlankStr(key))
        if not deleted:
            logger.warning(
                PRESET_NOT_FOUND,
                preset_name=key,
                operation="delete",
            )
            msg = f"Custom preset {name!r} not found"
            raise NotFoundError(msg)

        logger.info(PRESET_DELETED, preset_name=key)

    @staticmethod
    def get_schema() -> dict[str, Any]:
        """Return the JSON Schema for PersonalityConfig.

        Returns:
            JSON Schema dict.
        """
        return PersonalityConfig.model_json_schema()
