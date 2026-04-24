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
SETTINGS_VERSION_CONFLICT: Final[str] = "settings.version_conflict"
SETTINGS_REGISTRY_DUPLICATE: Final[str] = "settings.registry.duplicate"
SETTINGS_CONFIG_PATH_MISS: Final[str] = "settings.config_bridge.path_miss"
SETTINGS_DEFAULT_DRIFT: Final[str] = "settings.default.drift"

# ── Dispatcher & subscriber events ────────────────────────────────

SETTINGS_DISPATCHER_STARTED: Final[str] = "settings.dispatcher.started"
SETTINGS_DISPATCHER_STOPPED: Final[str] = "settings.dispatcher.stopped"
SETTINGS_DISPATCHER_POLL_ERROR: Final[str] = "settings.dispatcher.poll_error"
SETTINGS_DISPATCHER_CHANNEL_DEAD: Final[str] = "settings.dispatcher.channel_dead"
SETTINGS_SUBSCRIBER_NOTIFIED: Final[str] = "settings.subscriber.notified"
SETTINGS_SUBSCRIBER_ERROR: Final[str] = "settings.subscriber.error"
SETTINGS_SUBSCRIBER_RESTART_REQUIRED: Final[str] = (
    "settings.subscriber.restart_required"
)
SETTINGS_SERVICE_SWAPPED: Final[str] = "settings.service.swapped"
SETTINGS_SERVICE_SWAP_FAILED: Final[str] = "settings.service.swap_failed"
SETTINGS_CHANNEL_CREATED: Final[str] = "settings.channel.created"

# ── Observability subscriber events ──────────────────────────────

SETTINGS_OBSERVABILITY_PIPELINE_REBUILT: Final[str] = (
    "settings.observability.pipeline_rebuilt"
)
SETTINGS_OBSERVABILITY_REBUILD_FAILED: Final[str] = (
    "settings.observability.rebuild_failed"
)
SETTINGS_OBSERVABILITY_VALIDATION_FAILED: Final[str] = (
    "settings.observability.validation_failed"
)
