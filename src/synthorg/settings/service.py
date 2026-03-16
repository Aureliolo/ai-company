"""Settings service — resolution, validation, caching, and notifications.

Provides the central service layer that merges setting values from
four sources in priority order: DB > env > YAML > code defaults.
"""

import json
import os
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.communication.enums import MessageType
from synthorg.communication.message import Message, MessageMetadata
from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.settings import (
    SETTINGS_CACHE_INVALIDATED,
    SETTINGS_ENCRYPTION_ERROR,
    SETTINGS_NOTIFICATION_FAILED,
    SETTINGS_NOTIFICATION_PUBLISHED,
    SETTINGS_VALIDATION_FAILED,
    SETTINGS_VALUE_DELETED,
    SETTINGS_VALUE_RESOLVED,
    SETTINGS_VALUE_SET,
)
from synthorg.settings.config_bridge import extract_from_config
from synthorg.settings.enums import SettingSource, SettingType
from synthorg.settings.errors import (
    SettingNotFoundError,
    SettingsEncryptionError,
    SettingValidationError,
)
from synthorg.settings.models import SettingDefinition, SettingEntry, SettingValue

if TYPE_CHECKING:
    from synthorg.communication.bus_protocol import MessageBus
    from synthorg.persistence.repositories import SettingsRepository
    from synthorg.settings.encryption import SettingsEncryptor
    from synthorg.settings.registry import SettingsRegistry

logger = get_logger(__name__)

_SENSITIVE_MASK = "********"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _env_var_name(namespace: str, key: str) -> str:
    """Build env var name: ``SYNTHORG_{NAMESPACE}_{KEY}`` (uppercased)."""
    return f"SYNTHORG_{namespace.upper()}_{key.upper()}"


def _validate_value(definition: SettingDefinition, value: str) -> None:
    """Validate a value against its definition.

    For sensitive settings, error messages mask the actual value
    to prevent secret leakage through validation errors.

    Raises:
        SettingValidationError: If validation fails.
    """
    _validate_by_type(definition, value)

    if definition.validator_pattern is not None and not re.fullmatch(
        definition.validator_pattern, value
    ):
        display = _SENSITIVE_MASK if definition.sensitive else repr(value)
        msg = f"Value {display} does not match pattern {definition.validator_pattern!r}"
        raise SettingValidationError(msg)


def _validate_by_type(definition: SettingDefinition, value: str) -> None:
    """Type-specific validation dispatch."""
    setting_type = definition.type

    if setting_type == SettingType.INTEGER:
        _validate_integer(definition, value)
    elif setting_type == SettingType.FLOAT:
        _validate_float(definition, value)
    elif setting_type == SettingType.BOOLEAN:
        _validate_boolean(definition, value)
    elif setting_type == SettingType.ENUM:
        _validate_enum(definition, value)
    elif setting_type == SettingType.JSON:
        _validate_json(value)


def _validate_integer(definition: SettingDefinition, value: str) -> None:
    try:
        int_val = int(value)
    except ValueError as exc:
        display = _SENSITIVE_MASK if definition.sensitive else repr(value)
        msg = f"Expected integer, got {display}"
        raise SettingValidationError(msg) from exc
    _check_range(definition, float(int_val))


def _validate_float(definition: SettingDefinition, value: str) -> None:
    try:
        float_val = float(value)
    except ValueError as exc:
        display = _SENSITIVE_MASK if definition.sensitive else repr(value)
        msg = f"Expected float, got {display}"
        raise SettingValidationError(msg) from exc
    _check_range(definition, float_val)


def _validate_boolean(definition: SettingDefinition, value: str) -> None:
    if value.lower() not in ("true", "false", "1", "0"):
        display = _SENSITIVE_MASK if definition.sensitive else repr(value)
        msg = f"Expected boolean, got {display}"
        raise SettingValidationError(msg)


def _validate_enum(definition: SettingDefinition, value: str) -> None:
    if value not in definition.enum_values:
        display = _SENSITIVE_MASK if definition.sensitive else repr(value)
        msg = f"Invalid enum value {display}. Allowed: {definition.enum_values}"
        raise SettingValidationError(msg)


def _validate_json(value: str) -> None:
    try:
        json.loads(value)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON: {exc}"
        raise SettingValidationError(msg) from exc


def _check_range(definition: SettingDefinition, value: float) -> None:
    """Check numeric range constraints."""
    if definition.min_value is not None and value < definition.min_value:
        msg = f"Value {value} below minimum {definition.min_value}"
        raise SettingValidationError(msg)
    if definition.max_value is not None and value > definition.max_value:
        msg = f"Value {value} above maximum {definition.max_value}"
        raise SettingValidationError(msg)


class SettingsService:
    """Central settings service with resolution, cache, and notifications.

    Resolution order (highest priority first):
    1. Database overrides (user-set via API/UI)
    2. Environment variables (``SYNTHORG_{NAMESPACE}_{KEY}``)
    3. YAML defaults (from ``RootConfig``)
    4. Code defaults (from ``SettingDefinition.default``)

    The cache stores only non-sensitive DB values.  Sensitive values
    are decrypted on every read to avoid holding plaintext secrets
    in memory.

    Args:
        repository: Persistence repository for DB settings.
        registry: Setting metadata registry.
        config: Root company configuration for YAML resolution.
        encryptor: Optional encryptor for sensitive settings.
        message_bus: Optional message bus for change notifications.
    """

    def __init__(
        self,
        *,
        repository: SettingsRepository,
        registry: SettingsRegistry,
        config: object,
        encryptor: SettingsEncryptor | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._config = config
        self._encryptor = encryptor
        self._message_bus = message_bus
        self._cache: dict[tuple[str, str], SettingValue] = {}

    async def get(self, namespace: str, key: str) -> SettingValue:
        """Resolve a setting value through the priority chain.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            Resolved setting value with source information.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
        """
        definition = self._registry.get(namespace, key)
        if definition is None:
            msg = f"Unknown setting: {namespace}/{key}"
            raise SettingNotFoundError(msg)

        # 1. Cache check (sensitive values are never cached)
        cache_key = (namespace, key)
        if not definition.sensitive:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        # 2. DB lookup
        result = await self._repository.get(
            NotBlankStr(namespace),
            NotBlankStr(key),
        )
        if result is not None:
            raw_value, updated_at = result
            value = raw_value
            if definition.sensitive and self._encryptor is not None:
                value = self._encryptor.decrypt(raw_value)
            setting_value = SettingValue(
                namespace=definition.namespace,
                key=key,
                value=value,
                source=SettingSource.DATABASE,
                updated_at=updated_at,
            )
            # Cache only non-sensitive values to avoid holding
            # plaintext secrets in memory.
            if not definition.sensitive:
                self._cache = {**self._cache, cache_key: setting_value}
            logger.debug(
                SETTINGS_VALUE_RESOLVED,
                namespace=namespace,
                key=key,
                source="db",
            )
            return setting_value

        # 3. Environment variable (env vars are protected by OS-level
        # isolation — no encryption needed for env-sourced values)
        env_name = _env_var_name(namespace, key)
        env_val = os.environ.get(env_name)
        if env_val is not None:
            logger.debug(
                SETTINGS_VALUE_RESOLVED,
                namespace=namespace,
                key=key,
                source="env",
            )
            return SettingValue(
                namespace=definition.namespace,
                key=key,
                value=env_val,
                source=SettingSource.ENVIRONMENT,
            )

        # 4. YAML config bridge
        if definition.yaml_path is not None:
            yaml_val = extract_from_config(self._config, definition.yaml_path)
            if yaml_val is not None:
                logger.debug(
                    SETTINGS_VALUE_RESOLVED,
                    namespace=namespace,
                    key=key,
                    source="yaml",
                )
                return SettingValue(
                    namespace=definition.namespace,
                    key=key,
                    value=yaml_val,
                    source=SettingSource.YAML,
                )

        # 5. Code default
        default = definition.default if definition.default is not None else ""
        logger.debug(
            SETTINGS_VALUE_RESOLVED,
            namespace=namespace,
            key=key,
            source="default",
        )
        return SettingValue(
            namespace=definition.namespace,
            key=key,
            value=default,
            source=SettingSource.DEFAULT,
        )

    async def get_entry(self, namespace: str, key: str) -> SettingEntry:
        """Resolve a setting and return it with its definition.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            Combined entry with definition, value, and source.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
        """
        # get() performs the registry check and raises SettingNotFoundError
        value = await self.get(namespace, key)
        definition = self._registry.get(namespace, key)
        assert definition is not None  # noqa: S101 — get() guarantees
        display_value = _SENSITIVE_MASK if definition.sensitive else value.value
        return SettingEntry(
            definition=definition,
            value=display_value,
            source=value.source,
            updated_at=value.updated_at,
        )

    async def get_namespace(self, namespace: str) -> tuple[SettingEntry, ...]:
        """Resolve all settings in a namespace.

        Uses the repository's batch method to avoid N+1 DB queries.

        Args:
            namespace: Setting namespace.

        Returns:
            All setting entries in the namespace, sorted by key.
        """
        definitions = self._registry.list_namespace(namespace)
        if not definitions:
            return ()

        # Batch-fetch all DB values for this namespace in one query.
        db_rows = await self._repository.get_namespace(
            NotBlankStr(namespace),
        )
        db_lookup: dict[str, tuple[str, str]] = {k: (v, ts) for k, v, ts in db_rows}

        entries: list[SettingEntry] = []
        for defn in definitions:
            entry = self._resolve_with_db_lookup(defn, db_lookup.get(defn.key))
            entries.append(entry)
        return tuple(entries)

    async def get_all(self) -> tuple[SettingEntry, ...]:
        """Resolve all settings across all namespaces.

        Uses the repository's batch method to avoid N+1 DB queries.

        Returns:
            All setting entries, sorted by namespace then key.
        """
        definitions = self._registry.list_all()
        if not definitions:
            return ()

        # Batch-fetch all DB values in one query.
        db_rows = await self._repository.get_all()
        db_lookup: dict[tuple[str, str], tuple[str, str]] = {
            (ns, k): (v, ts) for ns, k, v, ts in db_rows
        }

        entries: list[SettingEntry] = []
        for defn in definitions:
            db_hit = db_lookup.get((defn.namespace, defn.key))
            entry = self._resolve_with_db_lookup(defn, db_hit)
            entries.append(entry)
        return tuple(entries)

    def _resolve_with_db_lookup(
        self,
        definition: SettingDefinition,
        db_hit: tuple[str, str] | None,
    ) -> SettingEntry:
        """Resolve a single setting entry using a pre-fetched DB value.

        This is a synchronous helper for batch operations.  It does
        not check the cache (batch callers skip the cache).  For the
        env/YAML/default fallback layers it performs the same logic
        as ``get()`` but without the async DB call.
        """
        ns = definition.namespace
        key = definition.key

        # DB value (pre-fetched)
        if db_hit is not None:
            raw_value, updated_at = db_hit
            value = raw_value
            if definition.sensitive and self._encryptor is not None:
                value = self._encryptor.decrypt(raw_value)
            display = _SENSITIVE_MASK if definition.sensitive else value
            return SettingEntry(
                definition=definition,
                value=display,
                source=SettingSource.DATABASE,
                updated_at=updated_at,
            )

        # Environment variable
        env_name = _env_var_name(ns, key)
        env_val = os.environ.get(env_name)
        if env_val is not None:
            display = _SENSITIVE_MASK if definition.sensitive else env_val
            return SettingEntry(
                definition=definition,
                value=display,
                source=SettingSource.ENVIRONMENT,
            )

        # YAML config bridge
        if definition.yaml_path is not None:
            yaml_val = extract_from_config(self._config, definition.yaml_path)
            if yaml_val is not None:
                display = _SENSITIVE_MASK if definition.sensitive else yaml_val
                return SettingEntry(
                    definition=definition,
                    value=display,
                    source=SettingSource.YAML,
                )

        # Code default
        default = definition.default if definition.default is not None else ""
        display = _SENSITIVE_MASK if definition.sensitive else default
        return SettingEntry(
            definition=definition,
            value=display,
            source=SettingSource.DEFAULT,
        )

    async def set(self, namespace: str, key: str, value: str) -> SettingEntry:
        """Validate and persist a setting value.

        Args:
            namespace: Setting namespace.
            key: Setting key.
            value: New value as a string.

        Returns:
            The updated setting entry.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
            SettingValidationError: If the value fails validation.
            SettingsEncryptionError: If the setting is sensitive and
                no encryptor is available.
        """
        definition = self._registry.get(namespace, key)
        if definition is None:
            msg = f"Unknown setting: {namespace}/{key}"
            raise SettingNotFoundError(msg)

        # Validate
        try:
            _validate_value(definition, value)
        except SettingValidationError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
            )
            raise

        # Encrypt if sensitive
        store_value = value
        if definition.sensitive:
            if self._encryptor is None:
                logger.error(
                    SETTINGS_ENCRYPTION_ERROR,
                    namespace=namespace,
                    key=key,
                    reason="no_encryptor",
                )
                msg = (
                    f"Cannot store sensitive setting {namespace}/{key} "
                    f"without encryption key"
                )
                raise SettingsEncryptionError(msg)
            store_value = self._encryptor.encrypt(value)

        # Persist
        updated_at = _now_iso()
        await self._repository.set(
            NotBlankStr(namespace),
            NotBlankStr(key),
            store_value,
            updated_at,
        )

        # Invalidate cache
        cache_key = (namespace, key)
        self._cache = {k: v for k, v in self._cache.items() if k != cache_key}
        logger.debug(
            SETTINGS_CACHE_INVALIDATED,
            namespace=namespace,
            key=key,
        )

        logger.info(
            SETTINGS_VALUE_SET,
            namespace=namespace,
            key=key,
        )

        # Notify
        await self._publish_change(namespace, key, definition)

        # Return the entry with the display value
        display_value = _SENSITIVE_MASK if definition.sensitive else value
        return SettingEntry(
            definition=definition,
            value=display_value,
            source=SettingSource.DATABASE,
            updated_at=updated_at,
        )

    async def delete(self, namespace: str, key: str) -> None:
        """Delete a DB override, reverting to the next source in chain.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
        """
        definition = self._registry.get(namespace, key)
        if definition is None:
            msg = f"Unknown setting: {namespace}/{key}"
            raise SettingNotFoundError(msg)

        await self._repository.delete(NotBlankStr(namespace), NotBlankStr(key))

        # Invalidate cache
        cache_key = (namespace, key)
        self._cache = {k: v for k, v in self._cache.items() if k != cache_key}
        logger.debug(
            SETTINGS_CACHE_INVALIDATED,
            namespace=namespace,
            key=key,
        )

        logger.info(
            SETTINGS_VALUE_DELETED,
            namespace=namespace,
            key=key,
        )

        await self._publish_change(namespace, key, definition)

    def get_schema(self, namespace: str | None = None) -> tuple[SettingDefinition, ...]:
        """Return setting definitions for schema introspection.

        Args:
            namespace: Optional namespace filter. If ``None``,
                returns all definitions.

        Returns:
            Matching definitions sorted by namespace then key.
        """
        if namespace is not None:
            return self._registry.list_namespace(namespace)
        return self._registry.list_all()

    async def _publish_change(
        self,
        namespace: str,
        key: str,
        definition: SettingDefinition,
    ) -> None:
        """Publish a change notification to the message bus."""
        if self._message_bus is None:
            return

        if not self._message_bus.is_running:
            return

        try:
            message = Message(
                timestamp=datetime.now(UTC),
                sender="system",
                to="#settings",
                type=MessageType.ANNOUNCEMENT,
                channel="#settings",
                content=f"Setting changed: {namespace}/{key}",
                metadata=MessageMetadata(
                    extra=(
                        ("namespace", namespace),
                        ("key", key),
                        (
                            "restart_required",
                            str(definition.restart_required),
                        ),
                    ),
                ),
            )
            await self._message_bus.publish(message)
            logger.debug(
                SETTINGS_NOTIFICATION_PUBLISHED,
                namespace=namespace,
                key=key,
            )
        except Exception:
            # Notification failure should not break settings writes.
            logger.warning(
                SETTINGS_NOTIFICATION_FAILED,
                namespace=namespace,
                key=key,
            )
