"""Personality preset event constants for structured logging.

Constants follow the ``preset.<scope>.<action>`` naming convention.
"""

from typing import Final

PRESET_CUSTOM_SAVED: Final[str] = "preset.custom.saved"
PRESET_CUSTOM_DELETED: Final[str] = "preset.custom.deleted"
PRESET_CUSTOM_FETCHED: Final[str] = "preset.custom.fetched"
PRESET_CUSTOM_LISTED: Final[str] = "preset.custom.listed"
PRESET_CUSTOM_SAVE_FAILED: Final[str] = "preset.custom.save_failed"
PRESET_CUSTOM_FETCH_FAILED: Final[str] = "preset.custom.fetch_failed"
PRESET_CUSTOM_LIST_FAILED: Final[str] = "preset.custom.list_failed"
PRESET_CUSTOM_DELETE_FAILED: Final[str] = "preset.custom.delete_failed"
PRESET_CUSTOM_COUNT_FAILED: Final[str] = "preset.custom.count_failed"
