"""Tests for the backup error hierarchy."""

import pytest

from synthorg.backup.errors import (
    BackupError,
    BackupInProgressError,
    BackupNotFoundError,
    ComponentBackupError,
    ManifestError,
    RestoreError,
    RetentionError,
)


@pytest.mark.unit
class TestBackupErrorHierarchy:
    """Every backup error must inherit from BackupError."""

    @pytest.mark.parametrize(
        "error_cls",
        [
            BackupInProgressError,
            RestoreError,
            ManifestError,
            ComponentBackupError,
            RetentionError,
            BackupNotFoundError,
        ],
    )
    def test_is_subclass_of_backup_error(self, error_cls: type[BackupError]) -> None:
        assert issubclass(error_cls, BackupError)

    def test_backup_error_is_subclass_of_exception(self) -> None:
        assert issubclass(BackupError, Exception)

    @pytest.mark.parametrize(
        "error_cls",
        [
            BackupError,
            BackupInProgressError,
            RestoreError,
            ManifestError,
            ComponentBackupError,
            RetentionError,
            BackupNotFoundError,
        ],
    )
    def test_is_subclass_of_exception(self, error_cls: type[Exception]) -> None:
        assert issubclass(error_cls, Exception)


@pytest.mark.unit
class TestBackupErrorMessages:
    """Error messages should be preserved when raising."""

    @pytest.mark.parametrize(
        ("error_cls", "msg"),
        [
            (BackupError, "generic backup failure"),
            (BackupInProgressError, "backup already running"),
            (RestoreError, "restore failed for component"),
            (ManifestError, "manifest checksum mismatch"),
            (ComponentBackupError, "could not back up persistence"),
            (RetentionError, "pruning failed -- disk full"),
            (BackupNotFoundError, "backup-999 does not exist"),
        ],
    )
    def test_message_preserved(self, error_cls: type[BackupError], msg: str) -> None:
        err = error_cls(msg)
        assert str(err) == msg

    @pytest.mark.parametrize(
        "error_cls",
        [
            BackupInProgressError,
            RestoreError,
            ManifestError,
            ComponentBackupError,
            RetentionError,
            BackupNotFoundError,
        ],
    )
    def test_catchable_as_backup_error(self, error_cls: type[BackupError]) -> None:
        with pytest.raises(BackupError):
            raise error_cls("test error")  # noqa: EM101, TRY003

    @pytest.mark.parametrize(
        "error_cls",
        [
            BackupInProgressError,
            RestoreError,
            ManifestError,
            ComponentBackupError,
            RetentionError,
            BackupNotFoundError,
        ],
    )
    def test_catchable_as_own_type(self, error_cls: type[BackupError]) -> None:
        with pytest.raises(error_cls):
            raise error_cls("specific catch")  # noqa: EM101, TRY003
