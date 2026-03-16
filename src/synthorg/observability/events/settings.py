"""Observability event constants for the settings persistence layer."""

from typing import Final

SETTINGS_VALUE_SET: Final[str] = "settings.value.set"
SETTINGS_VALUE_DELETED: Final[str] = "settings.value.deleted"
SETTINGS_VALUE_RESOLVED: Final[str] = "settings.value.resolved"
SETTINGS_CACHE_INVALIDATED: Final[str] = "settings.cache.invalidated"
SETTINGS_ENCRYPTION_ERROR: Final[str] = "settings.encryption.error"
SETTINGS_VALIDATION_FAILED: Final[str] = "settings.validation.failed"
SETTINGS_NOTIFICATION_PUBLISHED: Final[str] = "settings.notification.published"
SETTINGS_NOTIFICATION_FAILED: Final[str] = "settings.notification.failed"
SETTINGS_FETCH_FAILED: Final[str] = "settings.fetch.failed"
SETTINGS_SET_FAILED: Final[str] = "settings.set.failed"
SETTINGS_DELETE_FAILED: Final[str] = "settings.delete.failed"
SETTINGS_NOT_FOUND: Final[str] = "settings.not_found"
SETTINGS_REGISTRY_DUPLICATE: Final[str] = "settings.registry.duplicate"
SETTINGS_CONFIG_PATH_MISS: Final[str] = "settings.config_bridge.path_miss"
