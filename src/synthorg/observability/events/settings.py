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
SETTINGS_SERVICE_STARTED: Final[str] = "settings.service.started"
