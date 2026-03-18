"""Domain models for the backup system.

Includes enumerations, manifest, info summaries, and
request/response models for the restore workflow.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class BackupTrigger(StrEnum):
    """What initiated the backup."""

    SCHEDULED = "scheduled"
    MANUAL = "manual"
    SHUTDOWN = "shutdown"
    STARTUP = "startup"
    PRE_MIGRATION = "pre_migration"


class BackupComponent(StrEnum):
    """Identifiers for independently-backed-up data components."""

    PERSISTENCE = "persistence"
    MEMORY = "memory"
    CONFIG = "config"


class BackupManifest(BaseModel):
    """Full manifest written alongside each backup.

    Serialised to ``manifest.json`` inside the backup directory
    or archive.

    Attributes:
        version: Manifest schema version.
        synthorg_version: SynthOrg application version at backup time.
        timestamp: ISO 8601 timestamp of backup creation.
        trigger: What initiated the backup.
        components: Components included in this backup.
        db_schema_version: Persistence DB schema version at backup time.
        size_bytes: Total backup size in bytes.
        checksum: SHA-256 checksum of backup contents (``sha256:<hex>``).
        backup_id: Unique identifier for this backup.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    version: NotBlankStr = "1"
    synthorg_version: NotBlankStr
    timestamp: NotBlankStr
    trigger: BackupTrigger
    components: tuple[BackupComponent, ...]
    db_schema_version: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    checksum: NotBlankStr
    backup_id: NotBlankStr


class BackupInfo(BaseModel):
    """Lightweight backup summary for list endpoints.

    Attributes:
        backup_id: Unique identifier for this backup.
        timestamp: ISO 8601 timestamp of backup creation.
        trigger: What initiated the backup.
        components: Components included in this backup.
        size_bytes: Total backup size in bytes.
        compressed: Whether the backup is compressed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    backup_id: NotBlankStr
    timestamp: NotBlankStr
    trigger: BackupTrigger
    components: tuple[BackupComponent, ...]
    size_bytes: int = Field(ge=0)
    compressed: bool


class RestoreRequest(BaseModel):
    """Request body for initiating a restore operation.

    Attributes:
        backup_id: Which backup to restore from.
        components: Components to restore (``None`` = all from manifest).
        confirm: Safety gate -- must be ``True`` to proceed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    backup_id: NotBlankStr
    components: tuple[BackupComponent, ...] | None = None
    confirm: bool = False


class RestoreResponse(BaseModel):
    """Response after a successful restore operation.

    Attributes:
        manifest: Manifest of the restored backup.
        restored_components: Components that were restored.
        safety_backup_id: ID of the pre-restore safety backup.
        restart_required: Whether the application must be restarted.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    manifest: BackupManifest
    restored_components: tuple[BackupComponent, ...]
    safety_backup_id: NotBlankStr
    restart_required: bool = True
