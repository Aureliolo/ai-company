"""Error hierarchy for the settings persistence layer."""


class SettingsError(Exception):
    """Base exception for all settings-related errors."""


class SettingNotFoundError(SettingsError):
    """Raised when a setting key is not found in the registry."""


class SettingValidationError(SettingsError):
    """Raised when a setting value fails type, range, or pattern validation."""


class SettingsEncryptionError(SettingsError):
    """Raised when encryption key is unavailable or decryption fails."""
