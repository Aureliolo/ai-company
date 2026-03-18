"""Backup error hierarchy.

All backup-related errors inherit from ``BackupError`` so callers
can catch the entire family with a single except clause.
"""


class BackupError(Exception):
    """Base exception for all backup operations."""


class BackupInProgressError(BackupError):
    """Raised when a backup is attempted while another is in progress."""


class RestoreError(BackupError):
    """Raised when a restore operation fails."""


class ManifestError(BackupError):
    """Raised when a backup manifest is invalid or corrupt."""


class ComponentBackupError(BackupError):
    """Raised when a per-component backup or restore step fails."""


class RetentionError(BackupError):
    """Raised when backup pruning fails."""


class BackupNotFoundError(BackupError):
    """Raised when a requested backup ID does not exist."""
